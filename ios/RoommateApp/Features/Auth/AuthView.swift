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
            ScrollView {
                VStack(spacing: 22) {
                    VStack(spacing: 12) {
                        AppMark(size: 72)
                        Text("Roommates")
                            .font(.system(size: 38, weight: .heavy, design: .rounded))
                            .foregroundStyle(Brand.textGradient)
                        Text("Chores, groceries and bills for your home, without the group-chat chaos.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, 36)

                    Picker("", selection: $model.mode.animation(.snappy)) {
                        ForEach(AuthViewModel.Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .onChange(of: model.mode) { _, _ in model.error = nil }

                    VStack(spacing: 0) {
                        if model.mode == .register {
                            AuthField(systemImage: "person") {
                                TextField("First name", text: $model.firstName).textContentType(.givenName)
                            }
                            Divider().padding(.leading, 48)
                            AuthField(systemImage: "person.2") {
                                TextField("Last name (optional)", text: $model.lastName).textContentType(.familyName)
                            }
                            Divider().padding(.leading, 48)
                        }
                        AuthField(systemImage: "envelope") {
                            TextField("Email", text: $model.email)
                                .textContentType(.emailAddress)
                                .keyboardType(.emailAddress)
                                .textInputAutocapitalization(.never)
                                .autocorrectionDisabled()
                        }
                        Divider().padding(.leading, 48)
                        AuthField(systemImage: "lock") {
                            SecureField(model.mode == .register ? "Password (8+ characters)" : "Password", text: $model.password)
                                .textContentType(model.mode == .login ? .password : .newPassword)
                                .onSubmit { if model.canSubmit { Task { await model.submit(session: session) } } }
                        }
                    }
                    .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 20))
                    .shadow(color: Brand.indigo.opacity(0.08), radius: 16, y: 6)

                    if model.mode == .register || model.error != nil || model.resendNote != nil {
                        VStack(alignment: .leading, spacing: 6) {
                            if model.mode == .register {
                                Label("Use an email you'll remember — it's how you log in on any device.", systemImage: "checkmark.circle.fill")
                                Label("We'll email you a link to confirm it, then you log in.", systemImage: "checkmark.circle.fill")
                                Label("Then you'll create your home, or join one with a code or link.", systemImage: "checkmark.circle.fill")
                            }
                            ErrorBanner(message: model.error)
                            if model.unconfirmed {
                                Button("Send the confirmation link again") { Task { await model.resend() } }
                                    .font(.footnote.bold())
                            }
                            if let note = model.resendNote { Text(note) }
                        }
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .symbolRenderingMode(.hierarchical)
                        .tint(Brand.indigo)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }

                    Button {
                        Task { await model.submit(session: session) }
                    } label: {
                        if model.isLoading { ProgressView().tint(.white) } else {
                            Text(model.mode == .login ? "Log in" : "Create account")
                        }
                    }
                    .buttonStyle(.brand)
                    .disabled(!model.canSubmit || model.isLoading)
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 24)
            }
            .scrollDismissesKeyboard(.interactively)
            .background { BrandBackground() }
            .toolbar(.hidden, for: .navigationBar)
            .sheet(item: Binding(get: { model.checkEmail }, set: { if $0 == nil { model.checkEmail = nil } })) { sent in
                CheckEmailView(sent: sent, model: model)
            }
        }
    }
}

/// One row of the login card: a tinted icon, then the field.
private struct AuthField<Field: View>: View {
    let systemImage: String
    @ViewBuilder let field: Field

    var body: some View {
        HStack(spacing: 14) {
            Image(systemName: systemImage)
                .font(.body.weight(.medium))
                .foregroundStyle(Brand.indigo)
                .frame(width: 22)
            field
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 15)
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
