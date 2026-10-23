import SwiftUI

struct ProfileView: View {
    @Environment(Session.self) private var session
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        NavigationStack {
            List {
                if let user = session.user {
                    NameSection(user: user)
                    Section("Account") {
                        LabeledContent("Email", value: user.email)
                        if user.emailVerified {
                            Label("Email confirmed", systemImage: "checkmark.seal.fill").foregroundStyle(.green)
                        }
                    }
                    if !user.emailVerified { VerifyEmailSection(email: user.email) }
                }
                Section("Server") {
                    Text(APIClient.shared.baseURL)
                        .font(.footnote.monospaced())
                        .foregroundStyle(.secondary)
                }
                Section {
                    Button("Sign out", role: .destructive) { session.signOut() }
                }
                AdminSettingsLinks()
            }
            .navigationTitle("Profile")
            // Opened the link in the browser? Pick it up when coming back.
            .task { await refreshUser() }
            .refreshable { await refreshUser() }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { Task { await refreshUser() } }
            }
        }
    }
}

private extension ProfileView {
    func refreshUser() async {
        if let me = try? await APIClient.shared.me() { session.updateUser(me) }
    }
}

/// Until I open the link we emailed: what to do, and a way to get the email again. Mirrors web VerifyEmailBanner.tsx.
private struct VerifyEmailSection: View {
    let email: String
    @Environment(Session.self) private var session
    @State private var note: String?
    @State private var sending = false

    var body: some View {
        Section {
            Label("Confirm your email: open the link we sent to \(email).", systemImage: "envelope.badge")
                .foregroundStyle(.orange)
            Button(sending ? "Sending…" : "Send it again") { Task { await resend() } }
                .disabled(sending)
            Button("I've done it") {
                Task { if let me = try? await APIClient.shared.me() { session.updateUser(me) } }
            }
        } footer: {
            if let note { Text(note) }
        }
    }

    private func resend() async {
        sending = true
        defer { sending = false }
        do {
            let r = try await APIClient.shared.resendVerification()
            note = r.sent ? "Sent again — check your inbox (and spam)."
                : r.alreadyVerified ? "Already confirmed."
                : r.emailEnabled ? "Couldn't send it — try again in a bit."
                : "Email isn't set up on this server yet, so nothing was sent."
        } catch {
            note = error.localizedDescription
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
