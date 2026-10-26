import Foundation
import Observation

/// Who is signed in. Injected into the SwiftUI environment from RoommateApp.
@MainActor
@Observable
final class Session {
    private(set) var user: User?
    private(set) var isRestoring = true
    /// A website link the app was opened with (an invite or the email confirmation), until it's
    /// handled. An invite waits here while signed out, then opens after logging in.
    var pendingLink: AppLink?

    private let client: APIClient

    init(client: APIClient? = nil) {
        let client = client ?? .shared
        self.client = client
        client.onUnauthorized = { [weak self] in self?.signOut() }
    }

    func restore() async {
        defer { isRestoring = false }
        guard client.token != nil else { return }
        user = try? await client.me()
        if user == nil { client.token = nil }
    }

    func signIn(_ response: TokenResponse) {
        client.token = response.accessToken
        user = response.user
    }

    /// Of these houses, the one to open on: the one picked last (on any device), else the first.
    func preferredHousehold(in households: [Household]) -> UUID? {
        households.first { $0.id == user?.lastHouseholdId }?.id ?? households.first?.id
    }

    /// Remember a house picked, created or joined, so every device opens on it next time.
    func rememberHousehold(_ id: UUID) {
        guard user != nil, user?.lastHouseholdId != id else { return }
        user?.lastHouseholdId = id
        Task { _ = try? await client.setLastHousehold(id) }
    }

    /// After editing my profile.
    func updateUser(_ updated: User) {
        user = updated
    }

    func signOut() {
        client.token = nil
        user = nil
    }

    /// A link the app was opened with. Anything that isn't ours opens nothing.
    func open(_ url: URL) {
        if let link = AppLink(url) { pendingLink = link }
    }
}
