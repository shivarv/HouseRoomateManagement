import SwiftUI

extension View {
    /// Opens website links in the app (universal links): an invite opens the join sheet once I'm
    /// signed in, and the email confirmation confirms (and signs in) right away. Mirrors web
    /// JoinPage, InviteLinkPage and VerifyEmailPage.
    func handlesAppLinks() -> some View {
        modifier(AppLinkHandler())
    }
}

private struct AppLinkHandler: ViewModifier {
    @Environment(Session.self) private var session
    @State private var joining: String?  // invite code
    @State private var invite: String?  // private invite token
    @State private var notice: Notice?

    struct Notice: Identifiable {
        let title: String
        let message: String
        var id: String { title + message }
    }

    func body(content: Content) -> some View {
        content
            .onOpenURL { session.open($0) }
            .onContinueUserActivity(NSUserActivityTypeBrowsingWeb) { activity in
                if let url = activity.webpageURL { session.open(url) }
            }
            // A link that came in while signed out waits until I'm in.
            .task(id: TaskKey(link: session.pendingLink, signedIn: session.user != nil, restoring: session.isRestoring)) { await handle() }
            .sheet(item: Binding(get: { joining.map(Token.init) }, set: { joining = $0?.value })) { code in
                JoinHouseholdSheet(initialCode: code.value) {}
            }
            .sheet(item: Binding(get: { invite.map(Token.init) }, set: { invite = $0?.value })) { token in
                InviteLinkSheet(token: token.value)
            }
            .alert(item: $notice) { n in
                Alert(title: Text(n.title), message: Text(n.message))
            }
    }

    private struct TaskKey: Equatable {
        let link: AppLink?
        let signedIn: Bool
        let restoring: Bool
    }

    private struct Token: Identifiable {
        let value: String
        var id: String { value }
    }

    private func handle() async {
        guard let link = session.pendingLink, !session.isRestoring else { return }
        switch link {
        case .verifyEmail(let token):
            session.pendingLink = nil
            do {
                let result = try await APIClient.shared.verifyEmail(token: token)
                if let access = result.accessToken, session.user == nil {
                    session.signIn(TokenResponse(accessToken: access, user: result.user))
                }
                notice = Notice(title: "Email confirmed ✓",
                                message: session.user == nil ? "You can log in now." : "You're all set.")
            } catch {
                notice = Notice(title: "Couldn't confirm your email", message: error.localizedDescription)
            }
        case .join(let code):
            guard session.user != nil else { return }  // AuthView says "log in to open your invite"
            session.pendingLink = nil
            joining = code
        case .invite(let token):
            guard session.user != nil else { return }
            session.pendingLink = nil
            invite = token
        }
    }
}

/// A private invite from an email: which house, then Join. Only the invited email can use it.
private struct InviteLinkSheet: View {
    let token: String
    @Environment(Session.self) private var session
    @Environment(\.dismiss) private var dismiss
    @State private var preview: InviteLinkPreview?
    @State private var error: String?
    @State private var joining = false

    var body: some View {
        NavigationStack {
            List {
                if let preview {
                    Section {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("🏠 \(preview.householdName)").font(.title2.bold())
                            Text(preview.invitedBy.map { "\($0) invited you · \(preview.people) people" } ?? "\(preview.people) people")
                                .foregroundStyle(.secondary)
                        }
                        .padding(.vertical, 4)
                    } footer: {
                        if let mine = session.user?.email, mine.lowercased() != preview.email.lowercased() {
                            Text("This invite is for \(preview.email). Log in with that email to use it.")
                                .foregroundStyle(.orange)
                        }
                    }
                    Section {
                        Button {
                            Task { await join() }
                        } label: {
                            if joining { ProgressView().tint(.white) } else { Text("Join \(preview.householdName)") }
                        }
                        .buttonStyle(.brand)
                        .disabled(joining)
                    }
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets())
                } else if error == nil {
                    ProgressView().frame(maxWidth: .infinity)
                }
                ErrorBanner(message: error)
            }
            .brandBackground()
            .navigationTitle("You're invited")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Not now") { dismiss() } }
            }
            .task {
                do { preview = try await APIClient.shared.inviteLinkPreview(token: token) } catch {
                    self.error = "This invite has expired or was cancelled. Ask for a new one."
                }
            }
        }
    }

    private func join() async {
        joining = true
        defer { joining = false }
        do {
            let house = try await APIClient.shared.acceptInviteLink(token: token)
            session.rememberHousehold(house.id)  // the tabs follow it
            dismiss()
        } catch {
            self.error = error.localizedDescription
        }
    }
}
