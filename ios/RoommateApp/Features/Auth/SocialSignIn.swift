import AuthenticationServices
import CryptoKit
import SwiftUI

/// "Continue with Apple / Google / Facebook" on the start screen: for logging in and signing up
/// alike. Apple is the system sheet; Google and Facebook run their own sign-in page in a secure
/// browser sheet (no SDKs). The backend checks what they return. A new account the provider didn't
/// give enough for (a name, and an email or phone) gets a short form first. Mirrors web SocialSignIn.
struct SocialSignInButtons: View {
    @Environment(Session.self) private var session
    @Environment(\.webAuthenticationSession) private var webAuth
    @Environment(\.colorScheme) private var colorScheme
    @State private var providers: AuthProviders?
    @State private var appleNonce = ""
    @State private var busy: SocialProvider?
    @State private var error: String?
    @State private var finishing: PendingSignUp?

    var body: some View {
        VStack(spacing: 10) {
            SignInWithAppleButton(.continue) { request in
                appleNonce = Nonce.random()
                request.requestedScopes = [.fullName, .email]
                request.nonce = Nonce.sha256(appleNonce)
            } onCompletion: { result in
                Task { await apple(result) }
            }
            .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
            .frame(height: 50)
            .clipShape(Capsule())
            .id(colorScheme)  // the style only applies when the button is made

            if let clientId = providers?.google?.iosClientId {
                ProviderButton(title: "Continue with Google", busy: busy == .google, style: .google) {
                    Task { await google(clientId: clientId) }
                }
            }
            if let appId = providers?.facebook?.appId {
                ProviderButton(title: "Continue with Facebook", busy: busy == .facebook, style: .facebook) {
                    Task { await facebook(appId: appId) }
                }
            }
            ErrorBanner(message: error)
        }
        .disabled(busy != nil)
        .task { providers = try? await APIClient.shared.authProviders() }
        .sheet(item: $finishing) { pending in
            FinishProfileSheet(pending: pending)
        }
    }

    // MARK: Providers

    private func apple(_ result: Result<ASAuthorization, Error>) async {
        switch result {
        case .failure(let e):
            if (e as? ASAuthorizationError)?.code != .canceled { error = "Sign in with Apple didn't finish. Try again." }
        case .success(let auth):
            guard let credential = auth.credential as? ASAuthorizationAppleIDCredential,
                  let data = credential.identityToken, let token = String(data: data, encoding: .utf8) else {
                error = "Sign in with Apple didn't finish. Try again."
                return
            }
            // Apple shares the name only on the very first sign-in.
            await finish(.apple, token: token, nonce: Nonce.sha256(appleNonce),
                         firstName: credential.fullName?.givenName ?? "", lastName: credential.fullName?.familyName ?? "")
        }
    }

    /// Google's sign-in page with PKCE, then the code is swapped for an ID token (iOS clients have
    /// no secret). The redirect is the reversed client ID, as Google requires for iOS apps.
    private func google(clientId: String) async {
        busy = .google
        defer { busy = nil }
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
                return  // they backed out on Google's page
            }
            let idToken = try await googleIDToken(code: code, clientId: clientId, redirect: redirect, verifier: verifier)
            await finish(.google, token: idToken, nonce: nonce)
        } catch {
            if !Self.cancelled(error) { self.error = "Sign in with Google didn't finish. Try again." }
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
    private func facebook(appId: String) async {
        busy = .facebook
        defer { busy = nil }
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
            guard let token = fields?.first(where: { $0.name == "access_token" })?.value else { return }
            await finish(.facebook, token: token)
        } catch {
            if !Self.cancelled(error) { self.error = "Sign in with Facebook didn't finish. Try again." }
        }
    }

    private static func cancelled(_ error: Error) -> Bool {
        (error as? ASWebAuthenticationSessionError)?.code == .canceledLogin
    }

    // MARK: Our backend

    private func finish(_ provider: SocialProvider, token: String, nonce: String? = nil,
                        firstName: String = "", lastName: String = "") async {
        do {
            let result = try await APIClient.shared.oauth(provider, token: token, nonce: nonce, firstName: firstName, lastName: lastName)
            if let access = result.accessToken, let user = result.user {
                error = nil
                session.signIn(TokenResponse(accessToken: access, user: user))
            } else {
                finishing = PendingSignUp(provider: provider, token: token, nonce: nonce, result: result,
                                          firstName: firstName.isEmpty ? result.firstName : firstName,
                                          lastName: lastName.isEmpty ? result.lastName : lastName)
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// A provider sign-in that still needs a name and/or a contact before the account is made.
struct PendingSignUp: Identifiable {
    let provider: SocialProvider
    let token: String
    let nonce: String?
    let result: OAuthResult
    let firstName: String
    let lastName: String
    var id: String { token }
}

/// "Finish your profile": only what the provider didn't give. Sends the same token again.
private struct FinishProfileSheet: View {
    let pending: PendingSignUp
    @Environment(Session.self) private var session
    @Environment(\.dismiss) private var dismiss
    @State private var first: String
    @State private var last: String
    @State private var email: String
    @State private var phone = ""
    @State private var saving = false
    @State private var error: String?

    init(pending: PendingSignUp) {
        self.pending = pending
        _first = State(initialValue: pending.firstName)
        _last = State(initialValue: pending.lastName)
        _email = State(initialValue: pending.result.email ?? "")
    }

    private var askName: Bool { pending.result.missing.contains("name") }
    private var askContact: Bool { pending.result.missing.contains("contact") }
    private func trimmed(_ s: String) -> String { s.trimmingCharacters(in: .whitespaces) }
    private var ok: Bool {
        (!askName || !trimmed(first).isEmpty || !trimmed(last).isEmpty)
            && (!askContact || !trimmed(email).isEmpty || !trimmed(phone).isEmpty)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Your roommates need to know who you are and how to reach you.")
                        .font(.subheadline).foregroundStyle(.secondary)
                }
                .listRowBackground(Color.clear)
                if askName {
                    Section {
                        TextField("First name", text: $first).textContentType(.givenName)
                        TextField("Last name", text: $last).textContentType(.familyName)
                    } footer: {
                        Text("A first or last name is enough.")
                    }
                }
                if askContact {
                    Section {
                        TextField("Email", text: $email)
                            .textContentType(.emailAddress).keyboardType(.emailAddress)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                        TextField("or phone, e.g. +1 617 555 0100", text: $phone)
                            .textContentType(.telephoneNumber).keyboardType(.phonePad)
                    } footer: {
                        Text("One of the two is enough.")
                    }
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
            .navigationTitle("Finish your profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Back") { dismiss() } }
            }
        }
    }

    private func submit() async {
        saving = true
        defer { saving = false }
        do {
            let result = try await APIClient.shared.oauth(
                pending.provider, token: pending.token, nonce: pending.nonce,
                firstName: trimmed(first), lastName: trimmed(last),
                email: askContact && !trimmed(email).isEmpty ? trimmed(email) : nil,
                phone: askContact && !trimmed(phone).isEmpty ? trimmed(phone) : nil
            )
            if let access = result.accessToken, let user = result.user {
                dismiss()
                session.signIn(TokenResponse(accessToken: access, user: user))
            } else {
                error = "Add a name and an email or phone to continue."
            }
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// Google's and Facebook's buttons, in their own colours.
private struct ProviderButton: View {
    enum Style { case google, facebook }
    let title: String
    let busy: Bool
    let style: Style
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if busy { ProgressView().tint(style == .google ? .primary : .white) } else {
                    Text(style == .google ? "G" : "f")
                        .font(.system(size: 20, weight: .bold, design: style == .google ? .default : .rounded))
                        .foregroundStyle(style == .google ? AnyShapeStyle(Self.googleGradient) : AnyShapeStyle(.white))
                }
                Text(title).font(.headline)
            }
            .frame(maxWidth: .infinity)
            .frame(height: 50)
            .foregroundStyle(style == .google ? Color.primary : Color.white)
            .background(style == .google ? AnyShapeStyle(Color(.systemBackground)) : AnyShapeStyle(Color(red: 0.09, green: 0.47, blue: 0.95)),
                        in: Capsule())
            .overlay(Capsule().strokeBorder(style == .google ? Color.primary.opacity(0.15) : .clear))
        }
        .buttonStyle(.plain)
    }

    private static let googleGradient = LinearGradient(
        colors: [Color(red: 0.26, green: 0.52, blue: 0.96), Color(red: 0.92, green: 0.26, blue: 0.21),
                 Color(red: 0.98, green: 0.74, blue: 0.02), Color(red: 0.2, green: 0.66, blue: 0.33)],
        startPoint: .topLeading, endPoint: .bottomTrailing)
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
