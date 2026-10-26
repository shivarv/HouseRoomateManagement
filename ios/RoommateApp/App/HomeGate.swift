import SwiftUI

/// Signed in: the tabs once I'm in a home; until then, the welcome screen (no tabs).
struct HomeGate: View {
    @Environment(Session.self) private var session
    @State private var hasHome: Bool?

    var body: some View {
        Group {
            switch hasHome {
            case .some(true): MainTabView()
            case .some(false): WelcomeView { await check() }
            case .none: ProgressView()
            }
        }
        // Joining from an invite link (outside the welcome screen) changes my current house.
        .task(id: session.user?.lastHouseholdId) { await check() }
    }

    private func check() async {
        hasHome = !((try? await APIClient.shared.households()) ?? []).isEmpty
    }
}
