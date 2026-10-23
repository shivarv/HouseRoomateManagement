import Foundation
import Observation

/// Whether a row on the Groceries settings tab differs from what's saved.
enum DraftState { case unchanged, new, edited, removed }

/// A category as the admin sees it: saved data with the unsaved draft applied.
struct CategoryDraftRow: Identifiable, Hashable {
    let id: UUID
    let key: String  // "new:<id>" until a new category is saved
    var label: String
    var icon: String
    let canDelete: Bool
    var state: DraftState
}

/// A quick-add item as the admin sees it. `categoryKey` "" = picked from the name on save.
struct PresetDraftRow: Identifiable, Hashable {
    let id: UUID
    var name: String
    var categoryKey: String
    let isNew: Bool
    var state: DraftState
}

/// The admin's Groceries tab. Every change (add, edit, remove, reorder, suggestions) is kept
/// as a draft until `save()`. Mirrors web GrocerySettings.tsx.
@MainActor
@Observable
final class GrocerySettingsModel {
    static let auto = ""

    private struct PresetEdit: Equatable { var name: String?; var categoryKey: String? }
    private struct CategoryEdit: Equatable { var label: String?; var icon: String? }
    private struct NewPreset { let id = UUID(); var name: String; var categoryKey: String }
    private struct NewCategory { let id = UUID(); var label: String; var icon: String }

    let householdId: UUID
    private(set) var saved: GrocerySettings?
    var error: String?
    private(set) var isSaving = false

    private var newPresets: [NewPreset] = []
    private var presetEdits: [UUID: PresetEdit] = [:]
    private var presetRemoved: Set<UUID> = []
    private var newCategories: [NewCategory] = []
    private var categoryEdits: [UUID: CategoryEdit] = [:]
    private var categoryRemoved: Set<UUID> = []
    private var categoryOrder: [UUID]?
    private var dismissed: Set<String> = []  // suggestion names

    private let client = APIClient.shared

    init(householdId: UUID) {
        self.householdId = householdId
    }

    static func tempKey(_ id: UUID) -> String { "new:\(id)" }

    // MARK: Loading

    func load() async {
        do {
            saved = try await client.grocerySettings(householdId: householdId)
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Applies straight away, so it's only offered with nothing unsaved.
    func restoreStandard() async {
        do {
            saved = try await client.restoreStandardGroceries(householdId: householdId)
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    // MARK: What the admin sees

    var categories: [CategoryDraftRow] {
        guard let saved else { return [] }
        let rows = ordered(saved.categories, by: categoryOrder).map { c in
            let edit = categoryEdits[c.id]
            let state: DraftState = categoryRemoved.contains(c.id) ? .removed : edit != nil ? .edited : .unchanged
            return CategoryDraftRow(
                id: c.id, key: c.key, label: edit?.label ?? c.label, icon: edit?.icon ?? c.icon,
                canDelete: c.canDelete, state: state
            )
        }
        return rows + newCategories.map {
            CategoryDraftRow(id: $0.id, key: Self.tempKey($0.id), label: $0.label,
                             icon: $0.icon.isEmpty ? "🛍️" : $0.icon, canDelete: true, state: .new)
        }
    }

    /// Categories items can be filed under: everything not about to be deleted.
    var liveCategories: [CategoryDraftRow] { categories.filter { $0.state != .removed } }

    var presets: [PresetDraftRow] {
        guard let saved else { return [] }
        // Alphabetical from the server; new ones at the end of their type until saved.
        let rows = saved.presets.map { p in
            let edit = presetEdits[p.id]
            let state: DraftState = presetRemoved.contains(p.id) ? .removed : edit != nil ? .edited : .unchanged
            return PresetDraftRow(id: p.id, name: edit?.name ?? p.name, categoryKey: edit?.categoryKey ?? p.categoryKey,
                                  isNew: false, state: state)
        }
        return rows + newPresets.map {
            PresetDraftRow(id: $0.id, name: $0.name, categoryKey: $0.categoryKey, isNew: true, state: .new)
        }
    }

    /// The section a quick-add item shows under: its category, "" for new auto ones, else "other".
    func group(of preset: PresetDraftRow) -> String {
        if preset.isNew && preset.categoryKey == Self.auto { return Self.auto }
        return liveCategories.contains { $0.key == preset.categoryKey } ? preset.categoryKey : "other"
    }

    /// Suggestions not yet accepted into the draft.
    var suggestions: [GrocerySuggestion] {
        let names = Set(presets.filter { $0.state != .removed }.map { $0.name.lowercased() })
        return (saved?.suggestions ?? []).filter { !names.contains($0.name.lowercased()) }
    }

    func isDismissed(_ s: GrocerySuggestion) -> Bool { dismissed.contains(s.name) }

    var changeCount: Int {
        guard let saved else { return 0 }
        return newPresets.count + newCategories.count + dismissed.count
            + presetEdits.keys.filter { !presetRemoved.contains($0) }.count
            + categoryEdits.keys.filter { !categoryRemoved.contains($0) }.count
            + presetRemoved.count + categoryRemoved.count
            + (sameOrder(saved.categories, categoryOrder, categoryRemoved) ? 0 : 1)
    }

    var hasChanges: Bool { changeCount > 0 }

    var hasBlankNames: Bool {
        presets.contains { $0.state != .removed && $0.name.trimmingCharacters(in: .whitespaces).isEmpty }
            || liveCategories.contains {
                $0.label.trimmingCharacters(in: .whitespaces).isEmpty || $0.icon.trimmingCharacters(in: .whitespaces).isEmpty
            }
    }

    // MARK: Quick-add items

    /// Returns an error message instead of adding a duplicate.
    func addPreset(name: String, categoryKey: String) -> String? {
        let name = name.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty else { return nil }
        if presets.contains(where: { $0.state != .removed && $0.name.lowercased() == name.lowercased() }) {
            return "\(name) is already a quick-add item"
        }
        newPresets.append(NewPreset(name: name, categoryKey: categoryKey))
        return nil
    }

    func accept(_ suggestion: GrocerySuggestion, categoryKey: String) {
        newPresets.append(NewPreset(name: suggestion.name, categoryKey: categoryKey))
    }

    func toggleDismiss(_ suggestion: GrocerySuggestion) {
        if dismissed.contains(suggestion.name) { dismissed.remove(suggestion.name) } else { dismissed.insert(suggestion.name) }
    }

    func rename(_ preset: PresetDraftRow, to name: String) { editPreset(preset, name: name) }
    func setCategory(_ preset: PresetDraftRow, to key: String) { editPreset(preset, categoryKey: key) }

    private func editPreset(_ preset: PresetDraftRow, name: String? = nil, categoryKey: String? = nil) {
        if preset.isNew, let i = newPresets.firstIndex(where: { $0.id == preset.id }) {
            if let name { newPresets[i].name = name }
            if let categoryKey { newPresets[i].categoryKey = categoryKey }
            return
        }
        guard let original = saved?.presets.first(where: { $0.id == preset.id }) else { return }
        var edit = presetEdits[preset.id] ?? PresetEdit()
        if let name { edit.name = name == original.name ? nil : name }
        if let categoryKey { edit.categoryKey = categoryKey == original.categoryKey ? nil : categoryKey }
        presetEdits[preset.id] = edit == PresetEdit() ? nil : edit
    }

    func remove(_ preset: PresetDraftRow) {
        if preset.isNew { newPresets.removeAll { $0.id == preset.id } } else { presetRemoved.insert(preset.id) }
    }

    func undo(_ preset: PresetDraftRow) {
        presetEdits[preset.id] = nil
        presetRemoved.remove(preset.id)
        newPresets.removeAll { $0.id == preset.id }
    }

    // MARK: Categories

    func addCategory(label: String, icon: String) -> String? {
        let label = label.trimmingCharacters(in: .whitespaces)
        guard !label.isEmpty else { return nil }
        if liveCategories.contains(where: { $0.label.lowercased() == label.lowercased() }) {
            return "There's already a category called “\(label)”"
        }
        newCategories.append(NewCategory(label: label, icon: icon.trimmingCharacters(in: .whitespaces)))
        return nil
    }

    func edit(_ category: CategoryDraftRow, label: String? = nil, icon: String? = nil) {
        if category.state == .new, let i = newCategories.firstIndex(where: { $0.id == category.id }) {
            if let label { newCategories[i].label = label }
            if let icon { newCategories[i].icon = icon }
            return
        }
        guard let original = saved?.categories.first(where: { $0.id == category.id }) else { return }
        var edit = categoryEdits[category.id] ?? CategoryEdit()
        if let label { edit.label = label == original.label ? nil : label }
        if let icon { edit.icon = icon == original.icon ? nil : icon }
        categoryEdits[category.id] = edit == CategoryEdit() ? nil : edit
    }

    func remove(_ category: CategoryDraftRow) {
        if category.state == .new { dropNew(category) } else { categoryRemoved.insert(category.id) }
    }

    func undo(_ category: CategoryDraftRow) {
        categoryEdits[category.id] = nil
        categoryRemoved.remove(category.id)
        if category.state == .new { dropNew(category) }
    }

    /// Anything already filed under a dropped new category goes back to "auto" / unchanged.
    private func dropNew(_ category: CategoryDraftRow) {
        newCategories.removeAll { $0.id == category.id }
        for i in newPresets.indices where newPresets[i].categoryKey == category.key {
            newPresets[i].categoryKey = Self.auto
        }
        for (id, edit) in presetEdits where edit.categoryKey == category.key {
            var cleared = edit
            cleared.categoryKey = nil
            presetEdits[id] = cleared == PresetEdit() ? nil : cleared
        }
    }

    func move(_ category: CategoryDraftRow, by step: Int) {
        var ids = categories.filter { $0.state != .new }.map(\.id)
        guard let a = ids.firstIndex(of: category.id), ids.indices.contains(a + step) else { return }
        ids.swapAt(a, a + step)
        categoryOrder = ids
    }

    func canMove(_ category: CategoryDraftRow, by step: Int) -> Bool {
        guard category.state != .new, category.state != .removed else { return false }
        let ids = categories.filter { $0.state != .new }.map(\.id)
        guard let a = ids.firstIndex(of: category.id) else { return false }
        return ids.indices.contains(a + step)
    }

    // MARK: Saving

    func discard() {
        newPresets = []
        presetEdits = [:]
        presetRemoved = []
        newCategories = []
        categoryEdits = [:]
        categoryRemoved = []
        categoryOrder = nil
        dismissed = []
        error = nil
    }

    /// Step by step. Each step leaves the draft once it's saved, so a failure keeps only what's left.
    func save() async {
        guard let saved, !isSaving else { return }
        isSaving = true
        defer { isSaving = false }
        var keys: [String: String] = [:]  // temporary category key → real key
        func real(_ key: String) -> String { keys[key] ?? key }
        var createdCategories: [UUID] = []
        do {
            for n in newCategories {
                let icon = n.icon.trimmingCharacters(in: .whitespaces)
                let created = try await client.addGroceryCategory(
                    householdId: householdId, label: n.label.trimmingCharacters(in: .whitespaces),
                    icon: icon.isEmpty ? nil : icon)
                let temp = Self.tempKey(n.id)
                keys[temp] = created.key
                createdCategories.append(created.id)
                newCategories.removeAll { $0.id == n.id }
                // If a later step fails, the draft must already point at the real category.
                for i in newPresets.indices where newPresets[i].categoryKey == temp {
                    newPresets[i].categoryKey = created.key
                }
                for (id, edit) in presetEdits where edit.categoryKey == temp {
                    presetEdits[id]?.categoryKey = created.key
                }
            }
            for (id, edit) in categoryEdits {
                if !categoryRemoved.contains(id) {
                    _ = try await client.updateGroceryCategory(
                        id, label: edit.label?.trimmingCharacters(in: .whitespaces),
                        icon: edit.icon?.trimmingCharacters(in: .whitespaces))
                }
                categoryEdits[id] = nil
            }
            for n in newPresets {
                _ = try await client.addGroceryPreset(
                    householdId: householdId, name: n.name.trimmingCharacters(in: .whitespaces),
                    categoryKey: n.categoryKey == Self.auto ? nil : real(n.categoryKey))
                newPresets.removeAll { $0.id == n.id }
            }
            for (id, edit) in presetEdits {
                if !presetRemoved.contains(id) {
                    _ = try await client.updateGroceryPreset(
                        id, name: edit.name?.trimmingCharacters(in: .whitespaces),
                        categoryKey: edit.categoryKey.map(real))
                }
                presetEdits[id] = nil
            }
            let removedPresets = presetRemoved
            for name in dismissed {
                try await client.dismissGrocerySuggestion(householdId: householdId, name: name)
                dismissed.remove(name)
            }
            for id in removedPresets {
                try await client.removeGroceryPreset(id)
                presetRemoved.remove(id)
            }
            let removedCategories = categoryRemoved
            for id in removedCategories {
                try await client.deleteGroceryCategory(id)
                categoryRemoved.remove(id)
            }
            // New rows were created at the end, which is also where the draft shows them.
            if !sameOrder(saved.categories, categoryOrder, removedCategories) {
                let kept = saved.categories.filter { !removedCategories.contains($0.id) }
                try await client.orderGroceryCategories(
                    householdId: householdId, ids: ordered(kept, by: categoryOrder).map(\.id) + createdCategories)
            }
            categoryOrder = nil
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        await load()
    }

    // MARK: Helpers

    private func ordered<T: Identifiable>(_ rows: [T], by order: [UUID]?) -> [T] where T.ID == UUID {
        guard let order else { return rows }
        let rank = Dictionary(uniqueKeysWithValues: order.enumerated().map { ($1, $0) })
        return rows.enumerated()
            .sorted { (rank[$0.element.id] ?? Int.max, $0.offset) < (rank[$1.element.id] ?? Int.max, $1.offset) }
            .map(\.element)
    }

    private func sameOrder<T: Identifiable>(_ rows: [T], _ order: [UUID]?, _ removed: Set<UUID>) -> Bool where T.ID == UUID {
        guard order != nil else { return true }
        let kept = rows.filter { !removed.contains($0.id) }
        return kept.map(\.id) == ordered(kept, by: order).map(\.id)
    }
}
