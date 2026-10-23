import Foundation

extension APIClient {
    private struct MemberBody: Encodable { let displayName: String }
    private struct RoleBody: Encodable { let role: Role }
    private struct AcceptBody: Encodable { let memberId: UUID? }

    func households() async throws -> [Household] {
        try await get("/households")
    }

    func household(_ id: UUID) async throws -> HouseholdDetail {
        try await get("/households/\(id)")
    }

    /// Guided set-up: defaults to prefill, then the whole house created in one go.
    func setupTemplate() async throws -> SetupTemplate {
        try await get("/households/setup/template")
    }

    func setupHousehold(_ setup: HouseholdSetup) async throws -> Household {
        try await send("POST", "/households/setup", body: setup)
    }

    /// Admins, for everyone in it. The last home you're an admin of can't be deleted (409).
    func deleteHousehold(_ id: UUID) async throws {
        try await sendNoContent("DELETE", "/households/\(id)")
    }


    func addMember(householdId: UUID, displayName: String) async throws -> Member {
        try await send("POST", "/households/\(householdId)/members", body: MemberBody(displayName: displayName))
    }

    func setRole(memberId: UUID, role: Role) async throws -> Member {
        try await send("PATCH", "/members/\(memberId)", body: RoleBody(role: role))
    }

    func removeMember(_ memberId: UUID) async throws {
        try await sendNoContent("DELETE", "/members/\(memberId)")
    }

    func previewInvite(code: String) async throws -> InvitePreview {
        try await get("/invites/\(code.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? code)")
    }

    func acceptInvite(code: String, memberId: UUID?) async throws -> Household {
        let path = "/invites/\(code.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? code)/accept"
        return try await send("POST", path, body: AcceptBody(memberId: memberId))
    }
}
