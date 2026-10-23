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

    var canSubmit: Bool {
        !email.isEmpty && password.count >= (mode == .register ? 8 : 1)
            && (mode == .login || !firstName.trimmingCharacters(in: .whitespaces).isEmpty)
    }

    func submit(session: Session) async {
        isLoading = true
        error = nil
        defer { isLoading = false }
        do {
            let client = APIClient.shared
            let response = mode == .login
                ? try await client.login(email: email, password: password)
                : try await client.register(firstName: firstName.trimmingCharacters(in: .whitespaces),
                                            lastName: lastName.trimmingCharacters(in: .whitespaces),
                                            email: email, password: password)
            session.signIn(response)
        } catch {
            self.error = error.localizedDescription
        }
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
                            Text("✓ Next you'll create your home, or join one with a code or link.")
                        }
                        ErrorBanner(message: model.error)
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
        }
    }
}
