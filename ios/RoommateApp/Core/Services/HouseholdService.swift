import Foundation

extension APIClient {
    private struct CreateHouseholdBody: Encodable { let name: String; let timezone: String }
    private struct MemberBody: Encodable { let displayName: String }
    private struct RoleBody: Encodable { let role: Role }
    private struct AcceptBody: Encodable { let memberId: UUID? }

    func households() async throws -> [Household] {
        try await get("/households")
    }

    func household(_ id: UUID) async throws -> HouseholdDetail {
        try await get("/households/\(id)")
    }

    func createHousehold(name: String, timezone: String) async throws -> Household {
        try await send("POST", "/households", body: CreateHouseholdBody(name: name, timezone: timezone))
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
