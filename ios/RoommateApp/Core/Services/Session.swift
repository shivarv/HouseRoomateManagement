import Foundation
import Observation

/// Who is signed in. Injected into the SwiftUI environment from RoommateApp.
@MainActor
@Observable
final class Session {
    private(set) var user: User?
    private(set) var isRestoring = true

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

    func signOut() {
        client.token = nil
        user = nil
    }
}
