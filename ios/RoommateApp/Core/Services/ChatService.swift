import Foundation

extension APIClient {
    private struct BodyText: Encodable { let body: String }

    /// Latest messages; `before` pages back; `after` returns what's new or changed since then.
    func chatPage(householdId: UUID, before: String? = nil, after: String? = nil) async throws -> ChatPage {
        var parts = URLComponents()
        parts.queryItems = [before.map { URLQueryItem(name: "before", value: $0) },
                            after.map { URLQueryItem(name: "after", value: $0) }].compactMap { $0 }
        // Times look like 2026-10-24T10:00:00+00:00: a bare "+" would reach the server as a space.
        let query = parts.percentEncodedQuery.map { "?" + $0.replacingOccurrences(of: "+", with: "%2B") } ?? ""
        return try await get("/households/\(householdId)/chat\(query)")
    }

    func sendChat(householdId: UUID, body: String) async throws -> ChatMessage {
        try await send("POST", "/households/\(householdId)/chat", body: BodyText(body: body))
    }

    func editChat(_ id: UUID, body: String) async throws -> ChatMessage {
        try await send("PATCH", "/chat-messages/\(id)", body: BodyText(body: body))
    }

    /// Whoever wrote it, or an admin. It stays as "Message deleted".
    func deleteChat(_ id: UUID) async throws -> ChatMessage {
        try await send("DELETE", "/chat-messages/\(id)", body: Optional<String>.none)
    }

    func markChatRead(householdId: UUID) async throws {
        try await sendNoContent("POST", "/households/\(householdId)/chat/read")
    }

    func chatUnread(householdId: UUID) async throws -> ChatUnread {
        try await get("/households/\(householdId)/chat/unread")
    }
}
