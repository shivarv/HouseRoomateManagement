import SwiftUI

/// ⚙ Settings: a house's admin pages, kept apart from the everyday tabs. Opened from the house
/// screen's gear, or from Profile below Sign out. Mirrors web Settings.
struct HouseSettingsView: View {
    enum Section: String, CaseIterable, Identifiable {
        case groceries = "Groceries", bills = "Bills", history = "Past months"
        var id: Self { self }
    }

    let model: HouseholdViewModel
    @State private var groceries: GrocerySettingsModel
    @State private var billSettings: BillSettingsModel
    @State private var section: Section = .groceries
    /// Where the admin tried to go with unsaved grocery changes; asks before discarding them.
    @State private var pendingSection: Section?
    @State private var confirmBack = false
    @Environment(\.dismiss) private var dismiss

    init(model: HouseholdViewModel) {
        self.model = model
        _groceries = State(initialValue: GrocerySettingsModel(householdId: model.householdId))
        _billSettings = State(initialValue: BillSettingsModel(householdId: model.householdId))
    }

    private var unsavedGroceries: Bool { section == .groceries && groceries.hasChanges }

    var body: some View {
        List {
            Picker("Settings", selection: Binding(get: { section }, set: { next in
                if unsavedGroceries && next != .groceries { pendingSection = next } else { section = next }
            })) {
                ForEach(Section.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .listRowBackground(Color.clear)
            .listRowInsets(EdgeInsets())

            switch section {
            case .groceries: GrocerySettingsSection(model: groceries)
            case .bills: BillSettingsSection(model: billSettings, members: model.detail?.members ?? [])
            case .history: HistorySection(model: model)
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
