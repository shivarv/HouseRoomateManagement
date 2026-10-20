import SwiftUI

@MainActor
@Observable
final class AuthViewModel {
    enum Mode { case login, register }

    var mode: Mode = .login
    var name = ""
    var email = ""
    var password = ""
    var error: String?
    var isLoading = false

    var canSubmit: Bool {
        !email.isEmpty && password.count >= (mode == .register ? 8 : 1) && (mode == .login || !name.isEmpty)
    }

    func submit(session: Session) async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            let client = APIClient.shared
            let response = mode == .login
                ? try await client.login(email: email, password: password)
                : try await client.register(name: name, email: email, password: password)
            session.signIn(response)
        } catch {
            self.error = error.localizedDescription
        }
    }
}

struct AuthView: View {
    @Environment(Session.self) private var session
    @State private var model = AuthViewModel()

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    if model.mode == .register {
                        TextField("Name", text: $model.name)
                            .textContentType(.name)
                    }
                    TextField("Email", text: $model.email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    SecureField(model.mode == .register ? "Password (8+ characters)" : "Password", text: $model.password)
                        .textContentType(model.mode == .login ? .password : .newPassword)
                } footer: {
                    ErrorBanner(message: model.error)
                }

                Section {
                    Button {
                        Task { await model.submit(session: session) }
                    } label: {
                        HStack {
                            Spacer()
                            if model.isLoading { ProgressView() } else {
                                Text(model.mode == .login ? "Sign in" : "Create account").bold()
                            }
                            Spacer()
                        }
                    }
                    .disabled(!model.canSubmit || model.isLoading)
                }

                Section {
                    Button(model.mode == .login ? "New here? Create an account" : "Have an account? Sign in") {
                        model.mode = model.mode == .login ? .register : .login
                        model.error = nil
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .navigationTitle("🏠 Roommates")
        }
    }
}
