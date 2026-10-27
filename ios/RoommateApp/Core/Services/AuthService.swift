import Foundation

extension APIClient {
    private struct LoginBody: Encodable { let email: String; let password: String }
    private struct LastHouseholdBody: Encodable { let householdId: UUID }
    private struct RegisterBody: Encodable { let firstName: String; let lastName: String; let email: String; let password: String }
    private struct ProfileBody: Encodable { let firstName: String; let lastName: String; let phone: String?; let email: String? }
    private struct ResendBody: Encodable { let email: String }
    private struct ResendResponse: Decodable { let emailEnabled: Bool }
    private struct VerifyBody: Encodable { let token: String }
    private struct OAuthBody: Encodable {
        let token: String
        let nonce: String?
        let firstName: String
        let lastName: String
        let email: String?
        let phone: String?
    }

    func login(email: String, password: String) async throws -> TokenResponse {
        try await send("POST", "/auth/login", body: LoginBody(email: email, password: password))
    }

    /// Doesn't sign in: we email a link that confirms the address. Then they log in here.
    func register(firstName: String, lastName: String, email: String, password: String) async throws -> RegisterResponse {
        try await send("POST", "/auth/register", body: RegisterBody(firstName: firstName, lastName: lastName, email: email, password: password))
    }

    /// My first and last name (last may be empty).
    /// My name (one part may be empty), and optionally my phone (`""` clears it) or an email (only
    /// when I don't have one yet). nil leaves them as they are.
    func updateProfile(firstName: String, lastName: String, phone: String? = nil, email: String? = nil) async throws -> User {
        try await send("PATCH", "/auth/me", body: ProfileBody(firstName: firstName, lastName: lastName, phone: phone, email: email))
    }

    func me() async throws -> User {
        try await get("/auth/me")
    }

    func authProviders() async throws -> AuthProviders {
        try await get("/auth/providers")
    }

    /// Sign in or up with what the provider's sign-in returned, plus what I typed for anything it
    /// didn't share. `nonce`: the one given to Apple / Facebook, checked against the token.
    func oauth(_ provider: SocialProvider, token: String, nonce: String? = nil, firstName: String = "",
               lastName: String = "", email: String? = nil, phone: String? = nil) async throws -> OAuthResult {
        try await send("POST", "/auth/oauth/\(provider.rawValue)",
                       body: OAuthBody(token: token, nonce: nonce, firstName: firstName, lastName: lastName, email: email, phone: phone))
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
