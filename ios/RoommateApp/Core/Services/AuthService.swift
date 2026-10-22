import Foundation

extension APIClient {
    private struct LoginBody: Encodable { let email: String; let password: String }
    private struct LastHouseholdBody: Encodable { let householdId: UUID }
    private struct RegisterBody: Encodable { let name: String; let email: String; let password: String }

    func login(email: String, password: String) async throws -> TokenResponse {
        try await send("POST", "/auth/login", body: LoginBody(email: email, password: password))
    }

    func register(name: String, email: String, password: String) async throws -> TokenResponse {
        try await send("POST", "/auth/register", body: RegisterBody(name: name, email: email, password: password))
    }

    func me() async throws -> User {
        try await get("/auth/me")
    }

    func setLastHousehold(_ householdId: UUID) async throws -> User {
        try await send("PUT", "/auth/me/last-household", body: LastHouseholdBody(householdId: householdId))
    }
}
