import Foundation

extension APIClient {
    private struct MemberBody: Encodable { let displayName: String; let email: String?; let phone: String? }
    private struct RoleBody: Encodable { let role: Role }
    private struct ContactBody: Encodable { let email: String; let phone: String }  // "" clears
    private struct EmailsBody: Encodable { let emails: [String] }
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


    /// A name plus an email or phone (at least one). An email gets the invite right away.
    func addMember(householdId: UUID, displayName: String, email: String?, phone: String?) async throws -> MemberAdded {
        try await send("POST", "/households/\(householdId)/members", body: MemberBody(displayName: displayName, email: email, phone: phone))
    }

    /// An email and phone for someone who hasn't joined yet ("" clears them).
    func setContact(memberId: UUID, email: String, phone: String) async throws -> Member {
        try await send("PATCH", "/members/\(memberId)", body: ContactBody(email: email, phone: phone))
    }

    /// Invite by email: saved as pending, and emailed when email is set up on the server.
    func emailInvites(householdId: UUID, emails: [String]) async throws -> EmailInviteResults {
        try await send("POST", "/households/\(householdId)/email-invites", body: EmailsBody(emails: emails))
    }

    func pendingInvites(householdId: UUID) async throws -> [EmailInvite] {
        try await get("/households/\(householdId)/email-invites")
    }

    func cancelInvite(_ id: UUID) async throws {
        try await sendNoContent("DELETE", "/email-invites/\(id)")
    }

    /// Houses that invited my email and I haven't joined yet.
    func myInvites() async throws -> [MyInvite] {
        try await get("/me/invites")
    }

    /// Join with a private (emailed) invite. 404 "expired or was cancelled" once it's cancelled, used or expired.
    func acceptInviteLink(token: String) async throws -> Household {
        try await send("POST", "/invite-links/\(token)/accept", body: Optional<String>.none)
    }

    /// Admins: a new shared code; every old shared link and code stops working.
    func resetInviteCode(householdId: UUID) async throws -> Household {
        try await send("POST", "/households/\(householdId)/invite-code", body: Optional<String>.none)
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
