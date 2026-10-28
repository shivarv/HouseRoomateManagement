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
                            if let contact = user.email ?? user.phone {
                                Text(contact).font(.subheadline).foregroundStyle(.secondary)
                            }
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 4)
                    }
                    .listRowBackground(Color.clear)
                    NameSection(user: user)
                    ContactSection(user: user).id(user)  // fresh fields after a save
                    SignInMethodsSection(user: user)
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

/// Password, Google, Facebook and Apple: connect any of them and each signs in to this same
/// account. Disconnecting is refused for the last way in (the server checks too).
private struct SignInMethodsSection: View {
    let user: User
    @Environment(Session.self) private var session
    @Environment(\.webAuthenticationSession) private var webAuth
    @State private var config: AuthProviders?
    @State private var apple = AppleSignIn()
    @State private var busy: SocialProvider?
    @State private var disconnecting: SocialProvider?
    @State private var editingPassword = false
    @State private var error: String?
    @State private var note: String?

    private var ways: Int { (user.identities?.count ?? 0) + (user.hasPassword ? 1 : 0) }

    private func identity(_ provider: SocialProvider) -> User.Identity? {
        user.identities?.first { $0.provider == provider.rawValue }
    }

    var body: some View {
        Section {
            HStack {
                MethodLabel(title: "Password", systemImage: "key.fill", tint: Brand.indigo,
                            detail: user.hasPassword ? user.email : "Not set")
                Spacer()
                Button(user.hasPassword ? "Change" : "Set") { editingPassword = true }
                    .buttonStyle(.borderless)
            }
            ForEach([SocialProvider.google, .facebook, .apple], id: \.self) { provider in
                HStack {
                    MethodLabel(provider: provider, detail: identity(provider).map { $0.email ?? "Connected" } ?? "Not connected")
                    Spacer()
                    if busy == provider {
                        ProgressView()
                    } else if identity(provider) != nil {
                        Button("Disconnect", role: .destructive) { disconnecting = provider }
                            .buttonStyle(.borderless)
                            .disabled(ways <= 1)
                    } else {
                        Button("Connect") { Task { await connect(provider) } }
                            .buttonStyle(.borderless)
                    }
                }
            }
        } header: {
            Text("Ways to sign in")
        } footer: {
            VStack(alignment: .leading, spacing: 4) {
                Text("Any of these signs in to this same account. You always keep at least one.")
                if let note { Text(note).foregroundStyle(.green) }
                ErrorBanner(message: error)
            }
        }
        .disabled(busy != nil)
        .task { config = try? await APIClient.shared.authProviders() }
        .alert("Disconnect \(disconnecting?.title ?? "")?",
               isPresented: Binding(get: { disconnecting != nil }, set: { if !$0 { disconnecting = nil } }),
               presenting: disconnecting) { provider in
            Button("Disconnect", role: .destructive) { Task { await disconnect(provider) } }
            Button("Cancel", role: .cancel) {}
        } message: { provider in
            Text("You won't be able to sign in with \(provider.title) any more. You can connect it again later.")
        }
        .sheet(isPresented: $editingPassword) {
            PasswordSheet(user: user) { updated in
                session.updateUser(updated)
                note = user.hasPassword ? "Password changed." : "Password set. You can log in with your email too."
            }
        }
    }

    private func connect(_ provider: SocialProvider) async {
        busy = provider
        defer { busy = nil }
        error = nil
        note = nil
        do {
            let auth = ProviderAuth(webAuth: webAuth, apple: apple, config: config)
            guard let got = try await auth.run(provider) else { return }  // they backed out
            session.updateUser(try await APIClient.shared.linkSignIn(provider, token: got.token, nonce: got.nonce))
            note = "\(provider.title) connected. You can sign in with it now."
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func disconnect(_ provider: SocialProvider) async {
        busy = provider
        defer { busy = nil }
        error = nil
        note = nil
        do {
            session.updateUser(try await APIClient.shared.unlinkSignIn(provider))
            if LastSignIn.method == provider.rawValue { LastSignIn.method = nil }
            note = "\(provider.title) disconnected."
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// One row's icon, name and email.
private struct MethodLabel: View {
    let title: String
    let systemImage: String
    let tint: Color
    let detail: String?

    init(title: String, systemImage: String, tint: Color, detail: String?) {
        self.title = title
        self.systemImage = systemImage
        self.tint = tint
        self.detail = detail
    }

    init(provider: SocialProvider, detail: String?) {
        switch provider {
        case .google: self.init(title: "Google", systemImage: "g.circle.fill", tint: Color(red: 0.26, green: 0.52, blue: 0.96), detail: detail)
        case .facebook: self.init(title: "Facebook", systemImage: "f.circle.fill", tint: Color(red: 0.09, green: 0.47, blue: 0.95), detail: detail)
        case .apple: self.init(title: "Apple", systemImage: "apple.logo", tint: .primary, detail: detail)
        }
    }

    var body: some View {
        Label {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                if let detail { Text(detail).font(.caption).foregroundStyle(.secondary).lineLimit(1) }
            }
        } icon: {
            Image(systemName: systemImage).foregroundStyle(tint)
        }
    }
}

/// Set a first password (accounts made with Google, Apple or Facebook), or change mine.
private struct PasswordSheet: View {
    let user: User
    let onSaved: (User) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var current = ""
    @State private var new = ""
    @State private var saving = false
    @State private var error: String?

    private var ok: Bool { new.count >= 8 && (!user.hasPassword || !current.isEmpty) }

    var body: some View {
        NavigationStack {
            Form {
                if user.email == nil {
                    Section {
                        Text("Add an email in Contact first. It's what you'll log in with.")
                            .foregroundStyle(.secondary)
                    }
                } else {
                    Section {
                        if user.hasPassword {
                            SecureField("Current password", text: $current).textContentType(.password)
                        }
                        SecureField("New password (8+ characters)", text: $new).textContentType(.newPassword)
                    } footer: {
                        VStack(alignment: .leading) {
                            Text("You'll log in with \(user.email ?? "") and this password.")
                            ErrorBanner(message: error)
                        }
                    }
                }
            }
            .navigationTitle(user.hasPassword ? "Change password" : "Set a password")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    if saving { ProgressView() } else {
                        Button("Save") { Task { await save() } }.disabled(!ok || user.email == nil)
                    }
                }
            }
        }
    }

    private func save() async {
        saving = true
        defer { saving = false }
        do {
            let updated = try await APIClient.shared.setPassword(current: user.hasPassword ? current : nil, new: new)
            onSaved(updated)
            dismiss()
        } catch {
            self.error = error.localizedDescription
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

/// My email and phone: at least one. An email can be added when I don't have one (some Google,
/// Apple or Facebook sign-ups); changing an email isn't supported yet.
private struct ContactSection: View {
    let user: User
    @Environment(Session.self) private var session
    @State private var email = ""
    @State private var phone: String
    @State private var saving = false
    @State private var error: String?

    init(user: User) {
        self.user = user
        _phone = State(initialValue: user.phone ?? "")
    }

    private func trimmed(_ s: String) -> String { s.trimmingCharacters(in: .whitespaces) }
    private var changed: Bool { trimmed(phone) != (user.phone ?? "") || !trimmed(email).isEmpty }
    private var valid: Bool { user.email != nil || !trimmed(email).isEmpty || !trimmed(phone).isEmpty }

    var body: some View {
        Section {
            if let address = user.email {
                LabeledContent("Email", value: address)
                if user.emailVerified {
                    Label("Email confirmed", systemImage: "checkmark.seal.fill").foregroundStyle(.green)
                }
            } else {
                TextField("Email (optional)", text: $email)
                    .textContentType(.emailAddress).keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
            }
            TextField(user.email == nil ? "Phone" : "Phone (optional)", text: $phone)
                .textContentType(.telephoneNumber).keyboardType(.phonePad)
            if changed {
                Button(saving ? "Saving…" : "Save") { Task { await save() } }
                    .disabled(saving || !valid)
            }
        } header: {
            Text("Contact")
        } footer: {
            VStack(alignment: .leading) {
                Text("Your housemates can see these. An email or a phone is needed.")
                ErrorBanner(message: error)
            }
        }
    }

    private func save() async {
        saving = true
        defer { saving = false }
        do {
            session.updateUser(try await APIClient.shared.updateProfile(
                firstName: user.firstName, lastName: user.lastName, phone: trimmed(phone),
                email: user.email == nil && !trimmed(email).isEmpty ? trimmed(email) : nil))
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// My first and last name: a first or last name is enough. Homes that use my full name follow it.
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
            TextField("Last name", text: $last).textContentType(.familyName)
            if changed {
                Button(saving ? "Saving…" : "Save name") { Task { await save() } }
                    .disabled(saving || (first + last).trimmingCharacters(in: .whitespaces).isEmpty)
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
