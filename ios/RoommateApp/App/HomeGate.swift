import SwiftUI

/// Signed in: the tabs once I'm in a home; until then, the welcome screen (no tabs).
struct HomeGate: View {
    @State private var hasHome: Bool?

    var body: some View {
        Group {
            switch hasHome {
            case .some(true): MainTabView()
            case .some(false): WelcomeView { await check() }
            case .none: ProgressView()
            }
        }
        .task { await check() }
    }

    private func check() async {
        hasHome = !((try? await APIClient.shared.households()) ?? []).isEmpty
    }
}
