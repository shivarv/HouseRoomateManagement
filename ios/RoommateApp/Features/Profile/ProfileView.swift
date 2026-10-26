import SwiftUI

/// Opened from the avatar at the top right of every tab.
struct ProfileView: View {
    @Environment(Session.self) private var session
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                if let user = session.user {
                    Section {
                        VStack(spacing: 8) {
                            Avatar(name: user.name, size: 76)
                            Text(user.name).font(.title2.bold())
                            Text(user.email).font(.subheadline).foregroundStyle(.secondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 4)
                    }
                    .listRowBackground(Color.clear)
                    NameSection(user: user)
                    Section("Account") {
                        LabeledContent("Email", value: user.email)
                        if user.emailVerified {
                            Label("Email confirmed", systemImage: "checkmark.seal.fill").foregroundStyle(.green)
                        }
                    }
                }
                Section {
                    Button("Sign out", role: .destructive) { session.signOut() }
                }
                AdminSettingsLinks()
            }
            .brandBackground()
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
            }
        }
    }
}

/// My first and last name (the last one is optional). Homes that use my full name follow it.
private struct NameSection: View {
    let user: User
    @Environment(Session.self) private var session
    @State private var first: String
    @State private var last: String
    @State private var saving = false
    @State private var error: String?

    init(user: User) {
        self.user = user
        _first = State(initialValue: user.firstName)
        _last = State(initialValue: user.lastName)
    }

    private var changed: Bool {
        first.trimmingCharacters(in: .whitespaces) != user.firstName || last.trimmingCharacters(in: .whitespaces) != user.lastName
    }

    var body: some View {
        Section {
            TextField("First name", text: $first).textContentType(.givenName)
            TextField("Last name (optional)", text: $last).textContentType(.familyName)
            if changed {
                Button(saving ? "Saving…" : "Save name") { Task { await save() } }
                    .disabled(saving || first.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        } header: {
            Text("Your name")
        } footer: {
            VStack(alignment: .leading) {
                Text("If a home renamed you (e.g. a nickname), that stays.")
                ErrorBanner(message: error)
            }
        }
    }

    private func save() async {
        saving = true
        defer { saving = false }
        do {
            session.updateUser(try await APIClient.shared.updateProfile(
                firstName: first.trimmingCharacters(in: .whitespaces), lastName: last.trimmingCharacters(in: .whitespaces)))
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}
