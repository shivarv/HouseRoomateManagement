import SwiftUI

/// Signed in but not in any home yet: no tabs, just the two ways in — create a home, or join one
/// with the code or link a roommate sent — plus any invites to my email. Mirrors web WelcomePage.tsx.
struct WelcomeView: View {
    var onJoined: () async -> Void
    @Environment(Session.self) private var session
    @State private var invites: [MyInvite] = []
    @State private var creating = false
    @State private var joining: JoinTarget?
    @State private var joiningInvite: String?  // the token being joined
    @State private var inviteError: String?

    struct JoinTarget: Identifiable {
        let code: String
        var id: String { code }
    }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(alignment: .top, spacing: 14) {
                        AppMark(size: 48)
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Let's get you into a home").font(.title2.bold()).foregroundStyle(Brand.textGradient)
                            Text("Roommates keeps chores, groceries and bills fair and in one place. Start your own home, or join the one your roommates set up.")
                                .font(.subheadline).foregroundStyle(.secondary)
                        }
                    }
                    .padding(.vertical, 4)
                }
                .listRowBackground(Color.clear)

                if !invites.isEmpty {
                    Section("📬 You're invited") {
                        ForEach(invites) { invite in
                            Button {
                                Task { await join(invite) }
                            } label: {
                                HStack {
                                    VStack(alignment: .leading) {
                                        Text("🏠 \(invite.householdName)").font(.headline).foregroundStyle(.primary)
                                        Text(invite.invitedBy.map { "\($0) invited you" } ?? "You were invited")
                                            .font(.caption).foregroundStyle(.secondary)
                                    }
                                    Spacer()
                                    if joiningInvite == invite.token { ProgressView() } else { Text("Join").bold() }
                                }
                            }
                            .disabled(joiningInvite != nil)
                        }
                        ErrorBanner(message: inviteError)
                    }
                }

                Section {
                    Button { creating = true } label: {
                        Label {
                            VStack(alignment: .leading) {
                                Text("Create a new home").font(.headline)
                                Text("A few quick steps: chores, groceries and bills, prefilled. You'll be its admin.")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        } icon: { Text("✨") }
                    }
                    Button { joining = JoinTarget(code: "") } label: {
                        Label {
                            VStack(alignment: .leading) {
                                Text("Join a home").font(.headline)
                                Text("Got an invite on WhatsApp or email? Paste the link or the 8-character code.")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        } icon: { Text("🔑") }
                    }
                }

                Section {
                    Label("Set up your home: pick how many chores and bills. Everything is prefilled.", systemImage: "1.circle.fill")
                    Label("Invite your roommates on WhatsApp or email. They sign up and join.", systemImage: "2.circle.fill")
                    Label("Turns rotate on their own, bills remind you, and the grocery list stays shared.", systemImage: "3.circle.fill")
                } header: {
                    IconHeader(title: "How it works", systemImage: "lightbulb.fill", color: .orange)
                }
                .font(.subheadline)
                .foregroundStyle(.primary, Brand.indigo)
            }
            .brandBackground()
            .navigationTitle("Welcome, \(session.user?.firstName ?? "") 👋")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Sign out") { session.signOut() }
                }
            }
            .refreshable { await load() }
            .task { await load() }
            .sheet(isPresented: $creating) { SetupWizardView { _ in Task { await onJoined() } } }
            .sheet(item: $joining) { target in
                JoinHouseholdSheet(initialCode: target.code) { Task { await onJoined() } }
            }
        }
    }

    private func load() async {
        invites = (try? await APIClient.shared.myInvites()) ?? []
    }

    /// Joins with the invite's private link: refused if it was cancelled or expired meanwhile.
    private func join(_ invite: MyInvite) async {
        joiningInvite = invite.token
        defer { joiningInvite = nil }
        do {
            let house = try await APIClient.shared.acceptInviteLink(token: invite.token)
            session.rememberHousehold(house.id)
            inviteError = nil
            await onJoined()
        } catch {
            inviteError = error.localizedDescription
            await load()  // a cancelled invite drops off the list
        }
    }
}
