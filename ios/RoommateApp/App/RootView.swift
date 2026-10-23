import SwiftUI

struct RootView: View {
    @Environment(Session.self) private var session

    var body: some View {
        if session.isRestoring {
            ProgressView()
        } else if session.user == nil {
            AuthView()
        } else {
            HomeGate()
        }
    }
}

struct MainTabView: View {
    // Owned here so the tab badge stays current even when another tab is showing.
    @State private var notifications = NotificationsViewModel()

    var body: some View {
        TabView {
            MyDayView()
                .tabItem { Label("Today", systemImage: "checklist") }
            RemindersView()
                .tabItem { Label("Reminders", systemImage: "calendar.badge.clock") }
            HouseholdsView()
                .tabItem { Label("Households", systemImage: "house") }
            ShoppingView()
                .tabItem { Label("Groceries", systemImage: "cart") }
            NotificationsView(model: notifications, scope: .everyone)
                .tabItem { Label("Notifications", systemImage: "bell") }
                .badge(notifications.waitingCount)
            NotificationsView(model: notifications, scope: .mine)
                .tabItem { Label("Help", systemImage: "hand.raised") }
            ProfileView()
                .tabItem { Label("Profile", systemImage: "person.crop.circle") }
        }
        // New requests show up in the badge without visiting the tab.
        .task {
            while !Task.isCancelled {
                await notifications.load()
                try? await Task.sleep(for: .seconds(60))
            }
        }
    }
}
