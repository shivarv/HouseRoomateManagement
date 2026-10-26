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
                Section("Help") {
                    Link(destination: WebLink.url("/support")) {
                        Label("Help & support", systemImage: "questionmark.circle")
                    }
                    Link(destination: WebLink.url("/privacy")) {
                        Label("Privacy policy", systemImage: "hand.raised.circle")
                    }
                }
                Section {
                    Button("Sign out", role: .destructive) { session.signOut() }
                }
                AdminSettingsLinks()
                DeleteAccountSection()
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

/// Deleting my account, for good, after a confirmation that says what happens to my homes.
private struct DeleteAccountSection: View {
    @Environment(Session.self) private var session
    @State private var confirming = false
    @State private var deleting = false
    @State private var error: String?

    var body: some View {
        Section {
            Button(role: .destructive) { confirming = true } label: {
                if deleting { ProgressView() } else { Text("Delete account") }
            }
            .disabled(deleting)
        } footer: {
            VStack(alignment: .leading) {
                Text("Removes your account and email for good. Homes where you're the only one are deleted; in shared homes your past turns and payments stay under your name.")
                ErrorBanner(message: error)
            }
        }
        .alert("Delete your account?", isPresented: $confirming) {
            Button("Delete account", role: .destructive) { Task { await delete() } }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This can't be undone. If you're the only admin of a shared home, the roommate who joined first becomes its admin.")
        }
    }

    private func delete() async {
        deleting = true
        defer { deleting = false }
        do {
            try await APIClient.shared.deleteAccount()
            session.signOut()
        } catch {
            self.error = error.localizedDescription
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
