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
    @State private var chat = ChatModel()
    @Environment(Session.self) private var session

    var body: some View {
        TabView {
            MyDayView()
                .tabItem { Label("Today", systemImage: "checklist") }
            ChatView(model: chat)
                .tabItem { Label("Chat", systemImage: "bubble.left.and.bubble.right") }
                .badge(chat.unread)
            HouseholdsView()
                .tabItem { Label("Households", systemImage: "house") }
            ShoppingView()
                .tabItem { Label("Groceries", systemImage: "cart") }
            NotificationsView(model: notifications)
                .tabItem { Label("Favours", systemImage: "hand.raised") }
                .badge(notifications.waitingCount)
            ProfileView()
                .tabItem { Label("Profile", systemImage: "person.crop.circle") }
        }
        // New requests show up in the badge without visiting the tab.
        .task {
            while !Task.isCancelled {
                await notifications.load()
                if chat.households.isEmpty { chat.households = (try? await APIClient.shared.households()) ?? [] }
                if chat.householdId == nil { chat.householdId = session.preferredHousehold(in: chat.households) }
                await chat.refreshUnread()
                try? await Task.sleep(for: .seconds(60))
            }
        }
    }
}
