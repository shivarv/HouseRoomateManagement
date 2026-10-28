import AuthenticationServices
import CryptoKit
import SwiftUI

/// How they signed in last time on this phone: that button goes first, marked "Last used", so
/// they don't make a second account with another one by mistake.
enum LastSignIn {
    private static let methodKey = "lastSignIn.method"
    private static let emailKey = "lastSignIn.email"

    /// "apple", "google", "facebook" or "email".
    static var method: String? {
        get { UserDefaults.standard.string(forKey: methodKey) }
        set { UserDefaults.standard.set(newValue, forKey: methodKey) }
    }

    /// The email they logged in with, to fill in next time.
    static var email: String? {
        get { UserDefaults.standard.string(forKey: emailKey) }
        set { UserDefaults.standard.set(newValue, forKey: emailKey) }
    }
}

/// Google or Facebook gave an email that already has a password account (and didn't vouch for
/// it): they log in with the password, then this provider is linked to that account.
struct ExistingAccount: Equatable {
    let provider: SocialProvider
    let token: String
    let nonce: String?
    let email: String
}

/// "Continue with Apple / Google / Facebook" on the start screen: for logging in and signing up
/// alike. Apple is the system sheet; Google and Facebook run their own sign-in page in a secure
/// browser sheet (no SDKs). The backend checks what they return. A new account gets a welcome step
/// (and anything the provider didn't give: a name, an email or phone). Mirrors web SocialSignIn.
struct SocialSignInButtons: View {
    /// The email already has a password account: AuthView asks for the password.
    var onExistingAccount: (ExistingAccount) -> Void = { _ in }

    @Environment(Session.self) private var session
    @Environment(\.webAuthenticationSession) private var webAuth
    @State private var providers: AuthProviders?
    @State private var apple = AppleSignIn()
    @State private var busy: SocialProvider?
    @State private var error: String?
    @State private var welcome: WelcomeStep?

    var body: some View {
        VStack(spacing: 10) {
            HStack(spacing: 28) {
                ForEach([SocialProvider.apple, .google, .facebook], id: \.self) { provider in
                    ProviderIcon(provider: provider, busy: busy == provider,
                                 lastUsed: provider.rawValue == LastSignIn.method) {
                        Task { await start(provider) }
                    }
                }
            }
            ErrorBanner(message: error)
        }
        .disabled(busy != nil)
        .task { providers = try? await APIClient.shared.authProviders() }
        .sheet(item: $welcome) { step in
            WelcomeSheet(step: step)
        }
    }

    private func start(_ provider: SocialProvider) async {
        busy = provider
        defer { busy = nil }
        error = nil
        do {
            let auth = ProviderAuth(webAuth: webAuth, apple: apple, config: providers)
            guard let signedIn = try await auth.run(provider) else { return }  // they backed out
            await finish(provider, signedIn)
        } catch {
            self.error = error.localizedDescription
        }
    }

    // MARK: Our backend

    private func finish(_ provider: SocialProvider, _ got: ProviderToken) async {
        do {
            let result = try await APIClient.shared.oauth(provider, token: got.token, nonce: got.nonce,
                                                          firstName: got.firstName, lastName: got.lastName)
            if let access = result.accessToken, let user = result.user {
                LastSignIn.method = provider.rawValue
                let signedIn = TokenResponse(accessToken: access, user: user)
                if result.created { welcome = .created(signedIn) } else { session.signIn(signedIn) }
            } else if let email = result.existingEmail {
                onExistingAccount(ExistingAccount(provider: provider, token: got.token, nonce: got.nonce, email: email))
            } else {
                welcome = .finish(PendingSignUp(provider: provider, token: got.token, nonce: got.nonce, result: result,
                                                firstName: got.firstName.isEmpty ? result.firstName : got.firstName,
                                                lastName: got.lastName.isEmpty ? result.lastName : got.lastName))
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// What a provider's sign-in gave back, for our backend to check. Apple adds the name, the first time.
struct ProviderToken {
    let token: String
    var nonce: String?
    var firstName = ""
    var lastName = ""
}

/// Runs Apple's, Google's or Facebook's own sign-in. Used to sign in (start screen) and to connect
/// one more way to sign in (Profile).
@MainActor
struct ProviderAuth {
    let webAuth: WebAuthenticationSession
    let apple: AppleSignIn
    let config: AuthProviders?

    struct Failure: LocalizedError {
        let errorDescription: String?
    }

    /// nil: they backed out.
    func run(_ provider: SocialProvider) async throws -> ProviderToken? {
        switch provider {
        case .apple:
            return try await signInWithApple()
        case .google:
            // Always shown; until the server has the provider's IDs, a tap just says so.
            guard let clientId = config?.google?.iosClientId else { throw notReady("Google") }
            return try await google(clientId: clientId)
        case .facebook:
            guard let appId = config?.facebook?.appId else { throw notReady("Facebook") }
            return try await facebook(appId: appId)
        }
    }

    private func notReady(_ name: String) -> Failure {
        Failure(errorDescription: "Sign in with \(name) is coming soon. Use Apple or your email for now.")
    }

    private func didntFinish(_ name: String) -> Failure {
        Failure(errorDescription: "Sign in with \(name) didn't finish. Try again.")
    }

    private func signInWithApple() async throws -> ProviderToken? {
        let nonce = Nonce.random()
        let auth: ASAuthorization
        do {
            auth = try await apple.start(nonce: Nonce.sha256(nonce))
        } catch {
            if (error as? ASAuthorizationError)?.code == .canceled { return nil }
            throw didntFinish("Apple")
        }
        guard let credential = auth.credential as? ASAuthorizationAppleIDCredential,
              let data = credential.identityToken, let token = String(data: data, encoding: .utf8) else {
            throw didntFinish("Apple")
        }
        // Apple shares the name only on the very first sign-in.
        return ProviderToken(token: token, nonce: Nonce.sha256(nonce),
                             firstName: credential.fullName?.givenName ?? "", lastName: credential.fullName?.familyName ?? "")
    }

    /// Google's sign-in page with PKCE, then the code is swapped for an ID token (iOS clients have
    /// no secret). The redirect is the reversed client ID, as Google requires for iOS apps.
    private func google(clientId: String) async throws -> ProviderToken? {
        let scheme = clientId.split(separator: ".").reversed().joined(separator: ".")
        let redirect = "\(scheme):/oauth2redirect"
        let verifier = Nonce.random(length: 64)
        let nonce = Nonce.random()
        var url = URLComponents(string: "https://accounts.google.com/o/oauth2/v2/auth")!
        url.queryItems = [
            .init(name: "client_id", value: clientId),
            .init(name: "redirect_uri", value: redirect),
            .init(name: "response_type", value: "code"),
            .init(name: "scope", value: "openid email profile"),
            .init(name: "code_challenge", value: Nonce.base64URL(SHA256.hash(data: Data(verifier.utf8)))),
            .init(name: "code_challenge_method", value: "S256"),
            .init(name: "nonce", value: nonce),
            .init(name: "prompt", value: "select_account"),
        ]
        do {
            let callback = try await webAuth.authenticate(using: url.url!, callbackURLScheme: scheme, preferredBrowserSession: .ephemeral)
            guard let code = URLComponents(url: callback, resolvingAgainstBaseURL: false)?.queryItems?.first(where: { $0.name == "code" })?.value else {
                return nil  // they backed out on Google's page
            }
            let idToken = try await googleIDToken(code: code, clientId: clientId, redirect: redirect, verifier: verifier)
            return ProviderToken(token: idToken, nonce: nonce)
        } catch {
            if Self.cancelled(error) { return nil }
            throw didntFinish("Google")
        }
    }

    private func googleIDToken(code: String, clientId: String, redirect: String, verifier: String) async throws -> String {
        var request = URLRequest(url: URL(string: "https://oauth2.googleapis.com/token")!)
        request.httpMethod = "POST"
        request.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        var form = URLComponents()
        form.queryItems = [
            .init(name: "code", value: code), .init(name: "client_id", value: clientId),
            .init(name: "redirect_uri", value: redirect), .init(name: "grant_type", value: "authorization_code"),
            .init(name: "code_verifier", value: verifier),
        ]
        request.httpBody = form.percentEncodedQuery?.data(using: .utf8)
        let (data, _) = try await URLSession.shared.data(for: request)
        struct Tokens: Decodable { let id_token: String }
        return try JSONDecoder().decode(Tokens.self, from: data).id_token
    }

    /// Facebook's login dialog; it hands the access token back to fb<app id>://authorize/.
    private func facebook(appId: String) async throws -> ProviderToken? {
        let scheme = "fb\(appId)"
        var url = URLComponents(string: "https://www.facebook.com/v19.0/dialog/oauth")!
        url.queryItems = [
            .init(name: "client_id", value: appId),
            .init(name: "redirect_uri", value: "\(scheme)://authorize/"),
            .init(name: "response_type", value: "token"),
            .init(name: "scope", value: "public_profile,email"),
            .init(name: "state", value: Nonce.random()),
        ]
        do {
            let callback = try await webAuth.authenticate(using: url.url!, callbackURLScheme: scheme, preferredBrowserSession: .ephemeral)
            // The token comes after "#", like a query.
            let fields = URLComponents(string: "x:?" + (callback.fragment ?? ""))?.queryItems
            guard let token = fields?.first(where: { $0.name == "access_token" })?.value else { return nil }
            return ProviderToken(token: token)
        } catch {
            if Self.cancelled(error) { return nil }
            throw didntFinish("Facebook")
        }
    }

    private static func cancelled(_ error: Error) -> Bool {
        (error as? ASWebAuthenticationSessionError)?.code == .canceledLogin
    }
}

/// A provider sign-in that still needs a name and/or a contact before the account is made.
struct PendingSignUp {
    let provider: SocialProvider
    let token: String
    let nonce: String?
    let result: OAuthResult
    let firstName: String
    let lastName: String
}

/// The first moment of a new account: made already (`created`: check the name, maybe add a phone),
/// or still needing what the provider didn't give (`finish`: the same token goes again with it).
enum WelcomeStep: Identifiable {
    case created(TokenResponse)
    case finish(PendingSignUp)

    var id: String {
        switch self {
        case .created(let signedIn): signedIn.accessToken
        case .finish(let pending): pending.token
        }
    }
}

/// "Welcome, Ann!": the name to check (it's what roommates see), and an email or phone when the
/// provider gave neither. Then on to making or joining a home.
private struct WelcomeSheet: View {
    let step: WelcomeStep
    @Environment(Session.self) private var session
    @Environment(\.dismiss) private var dismiss
    @State private var first: String
    @State private var last: String
    @State private var email: String
    @State private var phone = ""
    @State private var saving = false
    @State private var error: String?

    init(step: WelcomeStep) {
        self.step = step
        switch step {
        case .created(let signedIn):
            _first = State(initialValue: signedIn.user.firstName)
            _last = State(initialValue: signedIn.user.lastName)
            _email = State(initialValue: "")
        case .finish(let pending):
            _first = State(initialValue: pending.firstName)
            _last = State(initialValue: pending.lastName)
            _email = State(initialValue: pending.result.email ?? "")
        }
    }

    private var pending: PendingSignUp? {
        if case .finish(let pending) = step { pending } else { nil }
    }
    /// Needs an email or phone before the account can be made.
    private var askContact: Bool { pending?.result.missing.contains("contact") ?? false }
    private func trimmed(_ s: String) -> String { s.trimmingCharacters(in: .whitespaces) }
    private var ok: Bool {
        !(trimmed(first) + trimmed(last)).isEmpty && (!askContact || !trimmed(email).isEmpty || !trimmed(phone).isEmpty)
    }
    private var greeting: String {
        trimmed(first).isEmpty ? "Welcome to Roommates" : "Welcome, \(trimmed(first))!"
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(spacing: 10) {
                        AppMark(size: 56)
                        Text(greeting)
                            .font(.title2.bold())
                            .multilineTextAlignment(.center)
                        Text(askContact
                             ? "Your roommates need to know who you are and how to reach you."
                             : "This is the name your roommates will see.")
                            .font(.subheadline).foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity)
                }
                .listRowBackground(Color.clear)
                Section {
                    TextField("First name", text: $first).textContentType(.givenName)
                    TextField("Last name", text: $last).textContentType(.familyName)
                } header: {
                    Text("Your name")
                } footer: {
                    Text("A first or last name is enough.")
                }
                Section {
                    if askContact {
                        TextField("Email", text: $email)
                            .textContentType(.emailAddress).keyboardType(.emailAddress)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                    }
                    TextField(askContact ? "or phone, e.g. +1 617 555 0100" : "Phone (optional)", text: $phone)
                        .textContentType(.telephoneNumber).keyboardType(.phonePad)
                } header: {
                    Text(askContact ? "How to reach you" : "Phone")
                } footer: {
                    Text(askContact ? "One of the two is enough." : "Only your roommates see it. You can add it later in Profile.")
                }
                Section {
                    Button {
                        Task { await submit() }
                    } label: {
                        if saving { ProgressView().tint(.white) } else { Text("Continue") }
                    }
                    .buttonStyle(.brand)
                    .disabled(!ok || saving)
                } footer: {
                    ErrorBanner(message: error)
                }
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets())
            }
            .brandBackground()
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    // A made account is theirs either way: skipping just keeps the provider's name.
                    if case .created(let signedIn) = step {
                        Button("Skip") { done(signedIn) }
                    } else {
                        Button("Back") { dismiss() }
                    }
                }
            }
            .interactiveDismissDisabled(pending == nil)
        }
    }

    private func done(_ signedIn: TokenResponse) {
        dismiss()
        session.signIn(signedIn)
    }

    private func submit() async {
        saving = true
        defer { saving = false }
        do {
            switch step {
            case .created(let signedIn):
                let user = signedIn.user
                let newPhone = trimmed(phone).isEmpty ? nil : trimmed(phone)
                guard trimmed(first) != user.firstName || trimmed(last) != user.lastName || newPhone != nil else {
                    return done(signedIn)
                }
                APIClient.shared.token = signedIn.accessToken  // signed in already; the screen changes after
                let updated = try await APIClient.shared.updateProfile(firstName: trimmed(first), lastName: trimmed(last), phone: newPhone)
                done(TokenResponse(accessToken: signedIn.accessToken, user: updated))
            case .finish(let pending):
                let result = try await APIClient.shared.oauth(
                    pending.provider, token: pending.token, nonce: pending.nonce,
                    firstName: trimmed(first), lastName: trimmed(last),
                    email: askContact && !trimmed(email).isEmpty ? trimmed(email) : nil,
                    phone: !trimmed(phone).isEmpty ? trimmed(phone) : nil
                )
                if let access = result.accessToken, let user = result.user {
                    LastSignIn.method = pending.provider.rawValue
                    done(TokenResponse(accessToken: access, user: user))
                } else if let existing = result.existingEmail {
                    error = "\(existing) already has an account. Go back and log in with its password."
                } else {
                    error = "Add a name and an email or phone to continue."
                }
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// A round Apple / Google / Facebook icon in its own colours, its name underneath, and a
/// "Last used" tag on the one they signed in with last time.
private struct ProviderIcon: View {
    let provider: SocialProvider
    let busy: Bool
    let lastUsed: Bool
    let action: () -> Void
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        Button(action: action) {
            VStack(spacing: 6) {
                ZStack {
                    Circle().fill(background)
                    Circle().strokeBorder(provider == .google ? Color.primary.opacity(0.15) : .clear)
                    if busy { ProgressView().tint(provider == .google ? .primary : foreground) } else { logo }
                }
                .frame(width: 58, height: 58)
                .shadow(color: .black.opacity(0.08), radius: 8, y: 3)
                .overlay(alignment: .top) {
                    if lastUsed {
                        Text("Last used")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundStyle(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Brand.indigo, in: Capsule())
                            .fixedSize()
                            .offset(y: -9)
                    }
                }
                Text(provider.title)
                    .font(.caption.weight(.medium))
                    .foregroundStyle(.secondary)
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Continue with \(provider.title)")
    }

    @ViewBuilder private var logo: some View {
        switch provider {
        case .apple:
            Image(systemName: "apple.logo").font(.system(size: 24, weight: .medium)).foregroundStyle(foreground)
        case .google:
            Text("G").font(.system(size: 26, weight: .bold)).foregroundStyle(Self.googleGradient)
        case .facebook:
            Text("f").font(.system(size: 32, weight: .bold, design: .rounded)).foregroundStyle(.white).offset(y: 2)
        }
    }

    // Apple's is black (white in dark mode), as Apple's guidelines ask.
    private var background: Color {
        switch provider {
        case .apple: colorScheme == .dark ? .white : .black
        case .google: Color(.systemBackground)
        case .facebook: Color(red: 0.09, green: 0.47, blue: 0.95)
        }
    }

    private var foreground: Color { colorScheme == .dark ? .black : .white }

    private static let googleGradient = LinearGradient(
        colors: [Color(red: 0.26, green: 0.52, blue: 0.96), Color(red: 0.92, green: 0.26, blue: 0.21),
                 Color(red: 0.98, green: 0.74, blue: 0.02), Color(red: 0.2, green: 0.66, blue: 0.33)],
        startPoint: .topLeading, endPoint: .bottomTrailing)
}

/// Sign in with Apple from our own (icon) button: the system sheet, awaited.
@MainActor
final class AppleSignIn: NSObject, ASAuthorizationControllerDelegate, ASAuthorizationControllerPresentationContextProviding {
    private var continuation: CheckedContinuation<ASAuthorization, Error>?

    /// `nonce` is the SHA-256 of the one we keep, as Apple asks.
    func start(nonce: String) async throws -> ASAuthorization {
        let request = ASAuthorizationAppleIDProvider().createRequest()
        request.requestedScopes = [.fullName, .email]
        request.nonce = nonce
        let controller = ASAuthorizationController(authorizationRequests: [request])
        controller.delegate = self
        controller.presentationContextProvider = self
        return try await withCheckedThrowingContinuation { continuation in
            self.continuation = continuation
            controller.performRequests()
        }
    }

    nonisolated func authorizationController(controller: ASAuthorizationController, didCompleteWithAuthorization authorization: ASAuthorization) {
        MainActor.assumeIsolated {
            continuation?.resume(returning: authorization)
            continuation = nil
        }
    }

    nonisolated func authorizationController(controller: ASAuthorizationController, didCompleteWithError error: Error) {
        MainActor.assumeIsolated {
            continuation?.resume(throwing: error)
            continuation = nil
        }
    }

    nonisolated func presentationAnchor(for controller: ASAuthorizationController) -> ASPresentationAnchor {
        MainActor.assumeIsolated {
            let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            return scenes.flatMap(\.windows).first(where: \.isKeyWindow) ?? ASPresentationAnchor()
        }
    }
}

/// Random strings for nonces and PKCE, and their SHA-256.
enum Nonce {
    static func random(length: Int = 32) -> String {
        let chars = Array("0123456789ABCDEFGHIJKLMNOPQRSTUVXYZabcdefghijklmnopqrstuvwxyz-._")
        var bytes = [UInt8](repeating: 0, count: length)
        _ = SecRandomCopyBytes(kSecRandomDefault, length, &bytes)
        return String(bytes.map { chars[Int($0) % chars.count] })
    }

    static func sha256(_ input: String) -> String {
        SHA256.hash(data: Data(input.utf8)).map { String(format: "%02x", $0) }.joined()
    }

    static func base64URL(_ digest: SHA256.Digest) -> String {
        Data(digest).base64EncodedString()
            .replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}
