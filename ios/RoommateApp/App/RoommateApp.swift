import SwiftUI

@main
struct RoommateApp: App {
    @State private var session = Session()

    var body: some Scene {
        WindowGroup {
            RootView()
                .handlesAppLinks()
                .environment(session)
                .task { await session.restore() }
        }
    }
}
