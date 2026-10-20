import SwiftUI

struct RootView: View {
    @Environment(Session.self) private var session

    var body: some View {
        if session.isRestoring {
            ProgressView()
        } else if session.user == nil {
            AuthView()
        } else {
            MainTabView()
        }
    }
}

struct MainTabView: View {
    var body: some View {
        TabView {
            MyDayView()
                .tabItem { Label("Today", systemImage: "checklist") }
            HouseholdsView()
                .tabItem { Label("Households", systemImage: "house") }
            ProfileView()
                .tabItem { Label("Profile", systemImage: "person.crop.circle") }
        }
    }
}
