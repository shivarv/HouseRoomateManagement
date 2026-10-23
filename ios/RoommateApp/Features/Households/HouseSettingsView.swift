import SwiftUI

/// ⚙ Settings: a house's admin pages, kept apart from the everyday tabs. Opened from the house
/// screen's gear, or from Profile below Sign out. Mirrors web Settings.
struct HouseSettingsView: View {
    enum Section: String, CaseIterable, Identifiable {
        case groceries = "Groceries", bills = "Bills", history = "Past months", homes = "Homes"
        var id: Self { self }
    }

    let model: HouseholdViewModel
    /// Called after this very house is deleted, so the screens about it can close.
    var onDeletedThisHouse: () -> Void = {}
    @State private var groceries: GrocerySettingsModel
    @State private var billSettings: BillSettingsModel
    @State private var section: Section = .groceries
    /// Where the admin tried to go with unsaved grocery changes; asks before discarding them.
    @State private var pendingSection: Section?
    @State private var confirmBack = false
    @Environment(\.dismiss) private var dismiss

    init(model: HouseholdViewModel, onDeletedThisHouse: @escaping () -> Void = {}) {
        self.model = model
        self.onDeletedThisHouse = onDeletedThisHouse
        _groceries = State(initialValue: GrocerySettingsModel(householdId: model.householdId))
        _billSettings = State(initialValue: BillSettingsModel(householdId: model.householdId))
    }

    private var unsavedGroceries: Bool { section == .groceries && groceries.hasChanges }

    var body: some View {
        List {
            ChipTabs(items: Section.allCases, selection: Binding(get: { section }, set: { next in
                if unsavedGroceries && next != .groceries { pendingSection = next } else { section = next }
            }))
            .listRowBackground(Color.clear)
            .listRowInsets(EdgeInsets())

            switch section {
            case .groceries: GrocerySettingsSection(model: groceries)
            case .bills: BillSettingsSection(model: billSettings, members: model.detail?.members ?? [])
            case .history: HistorySection(model: model)
            case .homes: YourHomesSection(currentId: model.householdId) { deleted in
                if deleted == model.householdId { dismiss(); onDeletedThisHouse() }
            }
            }
        }
        .safeAreaInset(edge: .bottom) {
            if section == .groceries && (groceries.hasChanges || groceries.error != nil) && groceries.saved != nil {
                GrocerySaveBar(model: groceries)
            }
        }
        .navigationTitle("Settings")
        .navigationBarTitleDisplayMode(.inline)
        // With unsaved grocery changes, going back asks first (the system back button can't).
        .navigationBarBackButtonHidden(unsavedGroceries)
        .toolbar {
            if unsavedGroceries {
                ToolbarItem(placement: .topBarLeading) {
                    Button { confirmBack = true } label: { Label("Back", systemImage: "chevron.left") }
                }
            }
        }
        .confirmationDialog("Discard unsaved grocery changes?",
                            isPresented: Binding(get: { pendingSection != nil || confirmBack },
                                                 set: { if !$0 { pendingSection = nil; confirmBack = false } }),
                            titleVisibility: .visible) {
            Button("Discard changes", role: .destructive) {
                groceries.discard()
                if let next = pendingSection { section = next } else { dismiss() }
                pendingSection = nil
                confirmBack = false
            }
        } message: {
            Text("Your edits on Groceries haven't been saved.")
        }
        .refreshable {
            await model.load()
            if section == .groceries { await groceries.load() }  // keeps the draft
            if section == .bills { await billSettings.load() }
        }
        .task { if model.detail == nil { await model.load() } }
    }
}

/// Profile → below Sign out: Settings for each house I'm an admin of.
struct AdminSettingsLinks: View {
    @State private var households: [Household] = []

    var body: some View {
        let admin = households.filter { $0.myRole == .admin }
        Group {
            if !admin.isEmpty {
                Section {
                    ForEach(admin) { house in
                        NavigationLink {
                            HouseSettingsLoader(householdId: house.id)
                        } label: {
                            Label(admin.count > 1 ? "Settings · \(house.name)" : "Settings", systemImage: "gearshape")
                        }
                    }
                } footer: {
                    Text("Groceries, bills and past months for houses you're an admin of.")
                }
            }
        }
        .task { households = (try? await APIClient.shared.households()) ?? [] }
    }
}

/// Settings needs the house's own model (people, history); this owns one for the Profile route.
private struct HouseSettingsLoader: View {
    @State private var model: HouseholdViewModel

    init(householdId: UUID) {
        _model = State(initialValue: HouseholdViewModel(householdId: householdId))
    }

    var body: some View {
        HouseSettingsView(model: model)
    }
}

/// Homes I'm an admin of, to delete. The last one stays: everyone keeps a home they run.
private struct YourHomesSection: View {
    let currentId: UUID
    let onDeleted: (UUID) -> Void
    @State private var households: [Household] = []
    @State private var pending: Household?
    @State private var typed = ""
    @State private var error: String?
    @State private var deleting = false

    private var mine: [Household] { households.filter { $0.myRole == .admin } }
    private var last: Bool { mine.count <= 1 }

    var body: some View {
        Section {
            ForEach(mine) { house in
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 6) {
                            Text(house.name).font(.headline)
                            if house.id == currentId { Badge(text: "Open now", color: .accentColor) }
                        }
                        if let address = house.address { Text(address).font(.caption).foregroundStyle(.secondary) }
                    }
                    Spacer()
                    Button("Delete", role: .destructive) { typed = ""; pending = house }
                        .buttonStyle(.bordered)
                        .disabled(last || deleting)
                }
            }
            ErrorBanner(message: error)
        } header: {
            Text("Your homes")
        } footer: {
            Text(last
                 ? "This is your last home as admin, so it can't be deleted. Set up another home you run first."
                 : "Deleting a home removes it for everyone in it, with its chores, groceries, bills and history.")
        }
        .task { await load() }
        .alert("Delete \(pending?.name ?? "")?", isPresented: Binding(get: { pending != nil }, set: { if !$0 { pending = nil } })) {
            TextField("Type the home's name", text: $typed)
            Button("Delete for everyone", role: .destructive) {
                if let house = pending { Task { await delete(house) } }
            }
            .disabled(typed.trimmingCharacters(in: .whitespaces).lowercased() != pending?.name.lowercased())
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Type “\(pending?.name ?? "")” to delete it for everyone, with all its chores, groceries, bills and history.")
        }
    }

    private func load() async {
        do {
            households = try await APIClient.shared.households()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func delete(_ house: Household) async {
        deleting = true
        defer { deleting = false }
        do {
            try await APIClient.shared.deleteHousehold(house.id)
            error = nil
            await load()
            onDeleted(house.id)
        } catch {
            self.error = error.localizedDescription
        }
    }
}
