import SwiftUI

@MainActor
@Observable
final class AuthViewModel {
    enum Mode: String, CaseIterable { case login = "Log in", register = "Sign up" }

    var mode: Mode = .login
    var firstName = ""
    var lastName = ""  // optional
    var email = ""
    var password = ""
    var error: String?
    var isLoading = false
    /// Signed up: waiting for them to open the link we emailed.
    var checkEmail: RegisterResponse?
    /// Logged in with the right password before confirming the email.
    var unconfirmed = false
    var resendNote: String?

    var canSubmit: Bool {
        !email.isEmpty && password.count >= (mode == .register ? 8 : 1)
            && (mode == .login || !firstName.trimmingCharacters(in: .whitespaces).isEmpty)
    }

    func submit(session: Session) async {
        isLoading = true
        error = nil
        unconfirmed = false
        resendNote = nil
        defer { isLoading = false }
        do {
            let client = APIClient.shared
            if mode == .login {
                session.signIn(try await client.login(email: email, password: password))
            } else {
                // Not signed in yet: the emailed link confirms the address, then they log in.
                checkEmail = try await client.register(firstName: firstName.trimmingCharacters(in: .whitespaces),
                                                       lastName: lastName.trimmingCharacters(in: .whitespaces),
                                                       email: email, password: password)
            }
        } catch {
            unconfirmed = (error as? APIError)?.status == 403
            self.error = error.localizedDescription
        }
    }

    func resend() async {
        do {
            try await APIClient.shared.resendVerification(email: email)
            resendNote = "Sent — check your inbox (and spam)."
        } catch {
            resendNote = error.localizedDescription
        }
    }

    /// Back to logging in once they've confirmed.
    func confirmed() {
        checkEmail = nil
        mode = .login
        error = nil
    }
}

/// The start screen: log in or sign up. Mirrors web AuthPage.tsx.
struct AuthView: View {
    @Environment(Session.self) private var session
    @State private var model = AuthViewModel()

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("", selection: $model.mode) {
                        ForEach(AuthViewModel.Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .onChange(of: model.mode) { _, _ in model.error = nil }
                } footer: {
                    Text("Chores, groceries and bills for your home, without the group-chat chaos.")
                }
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets())

                Section {
                    if model.mode == .register {
                        TextField("First name", text: $model.firstName).textContentType(.givenName)
                        TextField("Last name (optional)", text: $model.lastName).textContentType(.familyName)
                    }
                    TextField("Email", text: $model.email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField(model.mode == .register ? "Password (8+ characters)" : "Password", text: $model.password)
                        .textContentType(model.mode == .login ? .password : .newPassword)
                } footer: {
                    VStack(alignment: .leading, spacing: 4) {
                        if model.mode == .register {
                            Text("✓ Use an email you'll remember — it's how you log in on any device.")
                            Text("✓ We'll email you a link to confirm it, then you log in.")
                            Text("✓ Then you'll create your home, or join one with a code or link.")
                        }
                        ErrorBanner(message: model.error)
                        if model.unconfirmed {
                            Button("Send the confirmation link again") { Task { await model.resend() } }
                                .font(.footnote.bold())
                        }
                        if let note = model.resendNote { Text(note) }
                    }
                }

                Section {
                    Button {
                        Task { await model.submit(session: session) }
                    } label: {
                        HStack {
                            Spacer()
                            if model.isLoading { ProgressView() } else {
                                Text(model.mode == .login ? "Log in" : "Create account").bold()
                            }
                            Spacer()
                        }
                    }
                    .disabled(!model.canSubmit || model.isLoading)
                }
            }
            .navigationTitle("🏠 Roommates")
            .sheet(item: Binding(get: { model.checkEmail }, set: { if $0 == nil { model.checkEmail = nil } })) { sent in
                CheckEmailView(sent: sent, model: model)
            }
        }
    }
}

extension RegisterResponse: Identifiable {
    var id: String { email }
}

/// After signing up: open the link we emailed (it opens in the browser), then log in here.
private struct CheckEmailView: View {
    let sent: RegisterResponse
    let model: AuthViewModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("📧 Check your email").font(.title2.bold())
                        Text("We sent a link to \(sent.email). Open it to confirm your email, then come back and log in.")
                            .foregroundStyle(.secondary)
                        if !sent.emailEnabled {
                            Text("Email isn't set up on this server, so the link is in the server log.").foregroundStyle(.orange)
                        }
                    }
                    .padding(.vertical, 4)
                } footer: {
                    Text("Not there? Check spam, or send it again. The link works for 3 days.")
                }
                Section {
                    Button("I've confirmed — log in") {
                        model.confirmed()
                        dismiss()
                    }
                    .bold()
                    Button("Send the link again") { Task { await model.resend() } }
                } footer: {
                    if let note = model.resendNote { Text(note) }
                }
            }
            .navigationTitle("Almost there")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
