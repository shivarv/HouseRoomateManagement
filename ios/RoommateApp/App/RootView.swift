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

/// A tab with its own colour. The tab bar tints every icon alike unless the image keeps its
/// original colours, so the symbol is coloured here as a UIImage.
private struct TabIcon: View {
    let title: String
    let systemImage: String
    let color: UIColor

    var body: some View {
        Label {
            Text(title)
        } icon: {
            if let image = UIImage(systemName: systemImage)?.withTintColor(color, renderingMode: .alwaysOriginal) {
                Image(uiImage: image)
            } else {
                Image(systemName: systemImage)
            }
        }
    }
}

struct MainTabView: View {
    // Owned here so the tab badge stays current even when another tab is showing.
    @State private var notifications = NotificationsViewModel()
    @State private var chat = ChatModel()
    /// Bills of the current house that are overdue or due soon, on the House tab.
    @State private var billsDue = 0
    @Environment(Session.self) private var session

    var body: some View {
        // Five tabs, so iOS never folds one into "More". Profile is the avatar at the top right.
        TabView {
            MyDayView()
                .tabItem { TabIcon(title: "Today", systemImage: "sun.max.fill", color: .systemOrange) }
            HouseTabView()
                .tabItem { TabIcon(title: "House", systemImage: "house.fill", color: UIColor(Brand.indigo)) }
                .badge(billsDue)
            ChatView(model: chat)
                .tabItem { TabIcon(title: "Chat", systemImage: "bubble.left.and.bubble.right.fill", color: .systemTeal) }
                .badge(chat.unread)
            ShoppingView()
                .tabItem { TabIcon(title: "Groceries", systemImage: "cart.fill", color: .systemGreen) }
            NotificationsView(model: notifications)
                .tabItem { TabIcon(title: "Favours", systemImage: "hand.wave.fill", color: UIColor(Brand.fuchsia)) }
                .badge(notifications.waitingCount)
        }
        .tint(Brand.indigo)
        // New requests show up in the badge without visiting the tab.
        .task {
            while !Task.isCancelled {
                await notifications.load()
                if chat.households.isEmpty { chat.households = (try? await APIClient.shared.households()) ?? [] }
                if chat.householdId == nil { chat.householdId = session.preferredHousehold(in: chat.households) }
                await chat.refreshUnread()
                if let house = chat.householdId, let list = try? await APIClient.shared.bills(householdId: house) {
                    billsDue = BillsBadge.needingPayment(list.bills)
                }
                try? await Task.sleep(for: .seconds(60))
            }
        }
    }
}
