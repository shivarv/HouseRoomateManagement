import Foundation

extension APIClient {
    private struct CreateHelpBody: Encodable {
        let title: String
        let details: String?
    }
    private struct UpdateHelpBody: Encodable {
        let title: String?
        let details: String?  // "" clears it
    }

    /// Open requests in every house I'm in, ones done in the last two weeks, and all of mine.
    func helpRequests() async throws -> [HelpRequest] {
        try await get("/me/help-requests")
    }

    func askForHelp(householdId: UUID, title: String, details: String?) async throws -> HelpRequest {
        try await send("POST", "/households/\(householdId)/help-requests",
                       body: CreateHelpBody(title: title, details: details))
    }

    /// Only the person who asked, and only while it's open (409 once someone did it).
    func updateHelpRequest(_ id: UUID, title: String?, details: String?) async throws -> HelpRequest {
        try await send("PATCH", "/help-requests/\(id)", body: UpdateHelpBody(title: title, details: details))
    }

    /// Anyone in the house. The first person wins; everyone after gets a 409 saying who did it.
    func markHelpDone(_ id: UUID) async throws -> HelpRequest {
        try await send("POST", "/help-requests/\(id)/done", body: Optional<String>.none)
    }

    func reopenHelpRequest(_ id: UUID) async throws -> HelpRequest {
        try await send("POST", "/help-requests/\(id)/reopen", body: Optional<String>.none)
    }

    func withdrawHelpRequest(_ id: UUID) async throws {
        try await sendNoContent("DELETE", "/help-requests/\(id)")
    }
}
