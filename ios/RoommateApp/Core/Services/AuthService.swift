import Foundation

extension APIClient {
    private struct LoginBody: Encodable { let email: String; let password: String }
    private struct LastHouseholdBody: Encodable { let householdId: UUID }
    private struct RegisterBody: Encodable { let firstName: String; let lastName: String; let email: String; let password: String }
    private struct ProfileBody: Encodable { let firstName: String; let lastName: String }
    private struct ResendBody: Encodable { let email: String }
    private struct ResendResponse: Decodable { let emailEnabled: Bool }
    private struct VerifyBody: Encodable { let token: String }

    func login(email: String, password: String) async throws -> TokenResponse {
        try await send("POST", "/auth/login", body: LoginBody(email: email, password: password))
    }

    /// Doesn't sign in: we email a link that confirms the address. Then they log in here.
    func register(firstName: String, lastName: String, email: String, password: String) async throws -> RegisterResponse {
        try await send("POST", "/auth/register", body: RegisterBody(firstName: firstName, lastName: lastName, email: email, password: password))
    }

    /// My first and last name (last may be empty).
    func updateProfile(firstName: String, lastName: String) async throws -> User {
        try await send("PATCH", "/auth/me", body: ProfileBody(firstName: firstName, lastName: lastName))
    }

    func me() async throws -> User {
        try await get("/auth/me")
    }

    /// For good: homes nobody else is in go with it; elsewhere a roommate takes over as admin.
    func deleteAccount() async throws {
        try await sendNoContent("DELETE", "/auth/me")
    }

    /// The link from the confirmation email (works signed out). The first open also signs me in.
    func verifyEmail(token: String) async throws -> VerifyEmailResponse {
        try await send("POST", "/auth/verify-email", body: VerifyBody(token: token))
    }

    /// Email the confirmation link again (signed out). The answer is the same whether or not the account exists.
    func resendVerification(email: String) async throws {
        let _: ResendResponse = try await send("POST", "/auth/resend-verification", body: ResendBody(email: email))
    }

    func setLastHousehold(_ householdId: UUID) async throws -> User {
        try await send("PUT", "/auth/me/last-household", body: LastHouseholdBody(householdId: householdId))
    }
}
