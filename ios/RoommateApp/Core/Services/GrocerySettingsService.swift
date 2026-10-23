import Foundation

/// Admin only: the house's grocery categories and quick-add items.
extension APIClient {
    private struct CategoryBody: Encodable { let label: String?; let icon: String? }
    private struct PresetBody: Encodable { let name: String?; let categoryKey: String? }
    private struct OrderBody: Encodable { let ids: [UUID] }
    private struct NameBody: Encodable { let name: String }

    func grocerySettings(householdId: UUID) async throws -> GrocerySettings {
        try await get("/households/\(householdId)/grocery-settings")
    }

    /// Brings back removed standard categories and quick-add items; custom ones stay.
    func restoreStandardGroceries(householdId: UUID) async throws -> GrocerySettings {
        try await send("POST", "/households/\(householdId)/grocery-settings/restore", body: Optional<String>.none)
    }

    func addGroceryCategory(householdId: UUID, label: String, icon: String?) async throws -> GroceryCategory {
        try await send("POST", "/households/\(householdId)/grocery-categories", body: CategoryBody(label: label, icon: icon))
    }

    func updateGroceryCategory(_ id: UUID, label: String?, icon: String?) async throws -> GroceryCategory {
        try await send("PATCH", "/grocery-categories/\(id)", body: CategoryBody(label: label, icon: icon))
    }

    /// Its items and quick-add items move to "Other".
    func deleteGroceryCategory(_ id: UUID) async throws {
        try await sendNoContent("DELETE", "/grocery-categories/\(id)")
    }

    func orderGroceryCategories(householdId: UUID, ids: [UUID]) async throws {
        try await sendNoContent("PUT", "/households/\(householdId)/grocery-categories/order", body: OrderBody(ids: ids))
    }

    /// Without a category, the backend picks one from the name.
    func addGroceryPreset(householdId: UUID, name: String, categoryKey: String?) async throws -> GroceryPreset {
        try await send("POST", "/households/\(householdId)/grocery-presets", body: PresetBody(name: name, categoryKey: categoryKey))
    }

    func updateGroceryPreset(_ id: UUID, name: String?, categoryKey: String?) async throws -> GroceryPreset {
        try await send("PATCH", "/grocery-presets/\(id)", body: PresetBody(name: name, categoryKey: categoryKey))
    }

    func removeGroceryPreset(_ id: UUID) async throws {
        try await sendNoContent("DELETE", "/grocery-presets/\(id)")
    }

    func dismissGrocerySuggestion(householdId: UUID, name: String) async throws {
        try await sendNoContent("POST", "/households/\(householdId)/grocery-suggestions/dismiss", body: NameBody(name: name))
    }
}
