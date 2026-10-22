import Foundation

extension APIClient {
    private struct AskBody: Encodable {
        let dueDate: String
        let note: String?
    }

    /// Ask the house to take one of my turns. Asking again returns the same request.
    func askForSwap(choreId: UUID, dueDate: String, note: String?) async throws -> Swap {
        try await send("POST", "/chores/\(choreId)/swaps", body: AskBody(dueDate: dueDate, note: note))
    }

    func householdSwaps(householdId: UUID) async throws -> [Swap] {
        try await get("/households/\(householdId)/swaps")
    }

    func mySwaps() async throws -> [Swap] {
        try await get("/me/swaps")
    }

    /// The first person to accept wins; everyone after gets a 409 saying who already took it.
    func acceptSwap(_ swapId: UUID) async throws -> Swap {
        try await send("POST", "/swaps/\(swapId)/accept", body: Optional<String>.none)
    }

    func cancelSwap(_ swapId: UUID) async throws -> Swap {
        try await send("POST", "/swaps/\(swapId)/cancel", body: Optional<String>.none)
    }
}
