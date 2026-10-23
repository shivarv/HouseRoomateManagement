import Foundation

extension APIClient {
    private struct LoginBody: Encodable { let email: String; let password: String }
    private struct LastHouseholdBody: Encodable { let householdId: UUID }
    private struct RegisterBody: Encodable { let firstName: String; let lastName: String; let email: String; let password: String }
    private struct ProfileBody: Encodable { let firstName: String; let lastName: String }

    func login(email: String, password: String) async throws -> TokenResponse {
        try await send("POST", "/auth/login", body: LoginBody(email: email, password: password))
    }

    func register(firstName: String, lastName: String, email: String, password: String) async throws -> TokenResponse {
        try await send("POST", "/auth/register", body: RegisterBody(firstName: firstName, lastName: lastName, email: email, password: password))
    }

    /// My first and last name (last may be empty).
    func updateProfile(firstName: String, lastName: String) async throws -> User {
        try await send("PATCH", "/auth/me", body: ProfileBody(firstName: firstName, lastName: lastName))
    }

    func me() async throws -> User {
        try await get("/auth/me")
    }

    func setLastHousehold(_ householdId: UUID) async throws -> User {
        try await send("PUT", "/auth/me/last-household", body: LastHouseholdBody(householdId: householdId))
    }
}
