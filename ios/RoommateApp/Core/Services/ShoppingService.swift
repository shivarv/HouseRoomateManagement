import Foundation

extension APIClient {
    private struct AddBody: Encodable {
        let name: String
        let quantity: String?
    }
    private struct EditBody: Encodable {
        let name: String?
        let quantity: String?  // "" clears it
        let note: String?  // "" clears it
    }
    private struct BoughtManyBody: Encodable { let itemIds: [UUID] }

    func shoppingList(householdId: UUID) async throws -> ShoppingList {
        try await get("/households/\(householdId)/shopping")
    }

    /// Already on the list (any capitalisation)? The existing item comes back instead of a copy.
    func addShoppingItem(householdId: UUID, name: String, quantity: String?) async throws -> ShoppingItem {
        try await send("POST", "/households/\(householdId)/shopping", body: AddBody(name: name, quantity: quantity))
    }

    func editShoppingItem(_ id: UUID, name: String?, quantity: String?, note: String?) async throws -> ShoppingItem {
        try await send("PATCH", "/shopping/\(id)", body: EditBody(name: name, quantity: quantity, note: note))
    }

    /// The first person wins; anyone after gets a 409 saying who already bought it.
    func markBought(_ id: UUID) async throws -> ShoppingItem {
        try await send("POST", "/shopping/\(id)/bought", body: Optional<String>.none)
    }

    /// One shopping trip. Items someone else already bought keep their buyer.
    func markBought(householdId: UUID, itemIds: [UUID]) async throws -> [ShoppingItem] {
        try await send("POST", "/households/\(householdId)/shopping/bought", body: BoughtManyBody(itemIds: itemIds))
    }

    func undoBought(_ id: UUID) async throws -> ShoppingItem {
        try await send("POST", "/shopping/\(id)/undo", body: Optional<String>.none)
    }

    func removeShoppingItem(_ id: UUID) async throws {
        try await sendNoContent("DELETE", "/shopping/\(id)")
    }
}
