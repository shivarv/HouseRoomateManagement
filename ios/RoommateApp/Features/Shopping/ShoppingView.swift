import SwiftUI

@MainActor
@Observable
final class ShoppingViewModel {
    var households: [Household] = []
    var householdId: UUID?
    var list: ShoppingList?
    var error: String?
    var hasLoaded = false
    /// Per-item messages, e.g. "Bea already bought it" after losing a race.
    var notices: [UUID: String] = [:]
    var selected: Set<UUID> = []

    private let client = APIClient.shared

    var needed: [ShoppingItem] { list?.needed ?? [] }
    var bought: [ShoppingItem] { list?.recentlyBought ?? [] }
    var myMemberId: UUID? { households.first { $0.id == householdId }?.myMemberId }

    var categories: [GroceryCategory] { list?.categories ?? [] }

    /// The admin's quick-add items, minus anything already on the list.
    var quickAdd: [GroceryPreset] {
        let onList = Set(needed.map { $0.name.lowercased() })
        return (list?.quickAdd ?? []).filter { !onList.contains($0.name.lowercased()) }
    }

    /// The icon of an item's type; unknown types use "Other"'s.
    func icon(for key: String) -> String {
        (categories.first { $0.key == key } ?? categories.first { $0.key == "other" })?.icon ?? "🛍️"
    }

    /// Items whose category no longer exists are shown under "Other".
    func items(in category: GroceryCategory) -> [ShoppingItem] {
        let known = Set(categories.map(\.key))
        return needed.filter { (known.contains($0.category) ? $0.category : "other") == category.key }
    }

    /// `preferred` is the house to show when none is picked yet (or the picked one is gone).
    func load(preferred: ([Household]) -> UUID? = { $0.first?.id }) async {
        defer { hasLoaded = true }
        do {
            households = try await client.households()
            if householdId == nil || !households.contains(where: { $0.id == householdId }) {
                householdId = preferred(households)
            }
            if let householdId {
                list = try await client.shoppingList(householdId: householdId)
                selected.formIntersection(needed.map(\.id))
            }
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func add(_ name: String, quantity: String? = nil, category: String? = nil) async {
        guard let householdId else { return }
        do {
            _ = try await client.addShoppingItem(householdId: householdId, name: name, quantity: quantity, category: category)
        } catch {
            self.error = error.localizedDescription
        }
        await load()
    }

    /// Runs an action on one item, then reloads. A 409 is shown on that item, not as an error.
    func act(on id: UUID, _ action: @escaping () async throws -> Void) async {
        do {
            try await action()
            notices[id] = nil
        } catch {
            notices[id] = error.localizedDescription
        }
        await load()
    }

    func markBought(_ item: ShoppingItem) async { await act(on: item.id) { _ = try await self.client.markBought(item.id) } }
    func undo(_ item: ShoppingItem) async { await act(on: item.id) { _ = try await self.client.undoBought(item.id) } }
    func remove(_ item: ShoppingItem) async { await act(on: item.id) { try await self.client.removeShoppingItem(item.id) } }
    func edit(_ item: ShoppingItem, name: String, quantity: String, note: String) async {
        await act(on: item.id) {
            _ = try await self.client.editShoppingItem(item.id, name: name, quantity: quantity, note: note)
        }
    }

    /// One trip: everything ticked. Anything someone else got to first keeps their name.
    func markSelectedBought() async {
        guard let householdId, !selected.isEmpty else { return }
        do {
            let items = try await client.markBought(householdId: householdId, itemIds: Array(selected))
            for item in items where item.boughtBy != nil && item.boughtBy?.id != myMemberId {
                notices[item.id] = "\(item.boughtBy!.displayName) already bought it"
            }
            selected = []
        } catch {
            self.error = error.localizedDescription
        }
        await load()
    }
}

/// The house's shared shopping list: what's running out, and what was bought recently.
struct ShoppingView: View {
    @State private var model = ShoppingViewModel()
    @State private var name = ""
    @State private var quantity = ""
    @State private var editing: ShoppingItem?
    /// The quick-add item tapped: asks how much before it goes on the list.
    @State private var picking: GroceryPreset?
    @State private var pickQuantity = ""
    @Environment(\.scenePhase) private var scenePhase
    @Environment(Session.self) private var session

    var body: some View {
        NavigationStack {
            List {
                if !model.households.isEmpty {
                    HousePicker(households: model.households, selection: $model.householdId) { await model.load() }
                }
                addSection
                ErrorBanner(message: model.error)

                if model.needed.isEmpty && model.hasLoaded {
                    Section("Needed") {
                        Text("Nothing on the list. Add what's running out above.").foregroundStyle(.secondary)
                    }
                }
                ForEach(model.categories) { category in
                    let items = model.items(in: category)
                    if !items.isEmpty {
                        Section("\(category.icon) \(category.label)") {
                            ForEach(items) { neededRow($0) }
                        }
                    }
                }
                if !model.bought.isEmpty {
                    Section {
                        ForEach(model.bought) { boughtRow($0) }
                    } header: {
                        IconHeader(title: "Recently bought", systemImage: "bag.fill", color: Brand.teal)
                    }
                }
            }
            .brandBackground()
            .navigationTitle("Groceries")
            .profileToolbar()
            .toolbar {
                if !model.selected.isEmpty {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Mark \(model.selected.count) bought") { Task { await model.markSelectedBought() } }
                    }
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Clear") { model.selected = [] }
                    }
                }
            }
            .alert(picking.map { "How much \($0.name)?" } ?? "",
                   isPresented: Binding(get: { picking != nil }, set: { if !$0 { picking = nil } })) {
                TextField("e.g. 2 dozen", text: $pickQuantity)
                Button("Add to list") {
                    if let chip = picking {
                        let qty = pickQuantity.trimmingCharacters(in: .whitespaces)
                        Task { await model.add(chip.name, quantity: qty.isEmpty ? nil : qty, category: chip.categoryKey) }
                    }
                    picking = nil
                }
                Button("Cancel", role: .cancel) { picking = nil }
            } message: {
                Text("Optional: leave it empty if it doesn't matter.")
            }
            .sheet(item: $editing) { item in
                EditShoppingItemView(item: item) { name, quantity, note in
                    Task { await model.edit(item, name: name, quantity: quantity, note: note) }
                }
            }
            .refreshable { await model.load() }
            .task { await model.load(preferred: session.preferredHousehold) }
            .followsCurrentHouse($model.householdId)
            .onChange(of: model.householdId) { _, _ in Task { await model.load(preferred: session.preferredHousehold) } }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { Task { await model.load() } }
            }
        }
    }

    private var addSection: some View {
        Section {
            HStack {
                TextField("What's running out?", text: $name)
                    .submitLabel(.done)
                    .onSubmit(add)
                TextField("How much?", text: $quantity)
                    .frame(width: 100)
                    .foregroundStyle(.secondary)
                Button("Add", action: add)
                    .buttonStyle(.borderedProminent)
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(model.quickAdd) { chip in
                        Button("+ \(model.icon(for: chip.categoryKey)) \(chip.name)") {
                            pickQuantity = ""
                            picking = chip
                        }
                            .font(.caption)
                            .padding(.horizontal, 10).padding(.vertical, 5)
                            .background(Color.secondary.opacity(0.12), in: Capsule())
                            .buttonStyle(.plain)
                    }
                }
            }
        } footer: {
            Text("Tap an item to tick it for one trip, or swipe it: right for bought, left to remove.")
        }
    }

    private func add() {
        let trimmed = name.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        let qty = quantity.trimmingCharacters(in: .whitespaces)
        name = ""
        quantity = ""
        Task { await model.add(trimmed, quantity: qty.isEmpty ? nil : qty) }
    }

    private func neededRow(_ item: ShoppingItem) -> some View {
        let ticked = model.selected.contains(item.id)
        return VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 10) {
                Image(systemName: ticked ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(ticked ? Color.accentColor : .secondary)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text("\(model.icon(for: item.category)) \(item.name)").font(.body.weight(.medium))
                        if let q = item.quantity { Badge(text: q) }
                    }
                    if let note = item.note { Text(note).font(.subheadline) }
                    Text("Added by \(item.addedBy?.displayName ?? "someone")")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
                Button("Bought") { Task { await model.markBought(item) } }
                    .buttonStyle(.bordered)
            }
            .contentShape(Rectangle())
            .onTapGesture {
                if ticked { model.selected.remove(item.id) } else { model.selected.insert(item.id) }
            }
            noticeLine(item.id)
        }
        .swipeActions(edge: .leading) {
            Button("Bought", systemImage: "checkmark") { Task { await model.markBought(item) } }.tint(.green)
        }
        .swipeActions(edge: .trailing) {
            Button("Remove", systemImage: "trash", role: .destructive) { Task { await model.remove(item) } }
            Button("Edit", systemImage: "pencil") { editing = item }.tint(.indigo)
        }
    }

    private func boughtRow(_ item: ShoppingItem) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(model.icon(for: item.category)) " + item.name + (item.quantity.map { " · \($0)" } ?? ""))
                        .strikethrough()
                        .foregroundStyle(.secondary)
                    Text("\(item.boughtBy?.displayName ?? "Someone") bought it" + (item.boughtAt.map { " · \(Self.when($0))" } ?? ""))
                        .font(.caption.weight(.medium))
                        .foregroundStyle(.green)
                }
                Spacer(minLength: 0)
                if item.canUndo {
                    Button("Undo") { Task { await model.undo(item) } }.buttonStyle(.bordered).tint(.gray)
                }
            }
            noticeLine(item.id)
        }
    }

    @ViewBuilder
    private func noticeLine(_ id: UUID) -> some View {
        if let notice = model.notices[id] {
            HStack {
                Text(notice).font(.footnote).foregroundStyle(.secondary)
                Spacer()
                Button { model.notices[id] = nil } label: { Image(systemName: "xmark") }
                    .buttonStyle(.borderless)
                    .accessibilityLabel("Dismiss")
            }
            .padding(8)
            .background(Color.secondary.opacity(0.08), in: RoundedRectangle(cornerRadius: 8))
        }
    }

    static func when(_ timestamp: String) -> String {
        DayFormat.timestamp(timestamp)?.formatted(.relative(presentation: .named)) ?? ""
    }
}

private struct EditShoppingItemView: View {
    let item: ShoppingItem
    let onSave: (String, String, String) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var quantity = ""
    @State private var note = ""

    var body: some View {
        NavigationStack {
            Form {
                TextField("Name", text: $name)
                TextField("How much?", text: $quantity)
                TextField("Note, e.g. the brown one", text: $note, axis: .vertical)
            }
            .navigationTitle("Edit item")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave(name.trimmingCharacters(in: .whitespaces),
                               quantity.trimmingCharacters(in: .whitespaces),
                               note.trimmingCharacters(in: .whitespaces))
                        dismiss()
                    }
                    .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
            .onAppear {
                name = item.name
                quantity = item.quantity ?? ""
                note = item.note ?? ""
            }
        }
    }
}
