import SwiftUI

/// Admin Groceries tab: new things people added, quick-add items and categories.
/// Changes are drafts until "Save" in `GrocerySaveBar`. Mirrors web GrocerySettings.tsx.
struct GrocerySettingsSection: View {
    let model: GrocerySettingsModel
    @State private var newName = ""
    @State private var newCategory = GrocerySettingsModel.auto
    @State private var newLabel = ""
    @State private var newIcon = ""
    @State private var presetError: String?
    @State private var categoryError: String?
    @State private var confirmRestore = false

    var body: some View {
        Group {
            if model.saved == nil {
                if let error = model.error { ErrorBanner(message: error) } else { ProgressView() }
            } else {
                suggestionsSection
                addPresetSection
                presetSections
                addCategorySection
                categoriesSection
            }
        }
        .task { if model.saved == nil { await model.load() } }
    }

    // MARK: New things people added

    @ViewBuilder private var suggestionsSection: some View {
        if !model.suggestions.isEmpty {
            Section {
                ForEach(model.suggestions) { SuggestionRow(model: model, suggestion: $0) }
            } header: {
                Text("✨ New items your house added")
            } footer: {
                Text("Not quick-add items yet. Add the ones you buy often so everyone gets a one-tap button.")
            }
        }
    }

    // MARK: Quick-add items

    private var addPresetSection: some View {
        Section {
            HStack {
                TextField("e.g. Paneer", text: $newName)
                    .onSubmit(addPreset)
                    .onChange(of: newName) { _, _ in presetError = nil }
                CategoryPicker(model: model, selection: $newCategory, allowsAuto: true)
                Button("Add", action: addPreset)
                    .buttonStyle(.borderless)
                    .disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            if let presetError { ErrorBanner(message: presetError) }
            Button("Restore standard items") { confirmRestore = true }
                .disabled(model.hasChanges)
        } header: {
            Text("Add a quick-add item")
        } footer: {
            Text(model.hasChanges
                 ? "Save or discard your changes before restoring the standard items."
                 : "Quick-add items are the one-tap buttons on Groceries: just a name and a type (the type sets the icon). Nothing changes for the house until you tap Save.")
        }
        .confirmationDialog("Bring back any standard items or categories you removed?",
                            isPresented: $confirmRestore, titleVisibility: .visible) {
            Button("Restore standard items") { Task { await model.restoreStandard() } }
        } message: {
            Text("Your own items and categories stay.")
        }
    }

    private func addPreset() {
        presetError = model.addPreset(name: newName, categoryKey: newCategory)
        if presetError == nil {
            newName = ""
            newCategory = GrocerySettingsModel.auto
        }
    }

    @ViewBuilder private var presetSections: some View {
        let presets = model.presets
        if presets.isEmpty {
            Section("Quick-add items") {
                Text("No quick-add items. Add some above, or restore the standard ones.").foregroundStyle(.secondary)
            }
        }
        let auto = presets.filter { model.group(of: $0) == GrocerySettingsModel.auto }
        if !auto.isEmpty {
            Section("✨ New · category picked from the name on save") {
                ForEach(auto) { PresetRow(model: model, preset: $0) }
            }
        }
        ForEach(model.liveCategories) { category in
            let group = presets.filter { model.group(of: $0) == category.key }
            if !group.isEmpty {
                Section("\(category.icon) \(category.label)") {
                    ForEach(group) { PresetRow(model: model, preset: $0) }
                }
            }
        }
    }

    // MARK: Categories

    private var addCategorySection: some View {
        Section {
            HStack {
                TextField("🍿", text: $newIcon)
                    .frame(width: 44)
                    .multilineTextAlignment(.center)
                TextField("e.g. Snacks", text: $newLabel)
                    .onSubmit(addCategory)
                    .onChange(of: newLabel) { _, _ in categoryError = nil }
                Button("Add", action: addCategory)
                    .buttonStyle(.borderless)
                    .disabled(newLabel.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            if let categoryError { ErrorBanner(message: categoryError) }
        } header: {
            Text("Add a category")
        }
    }

    private func addCategory() {
        categoryError = model.addCategory(label: newLabel, icon: newIcon)
        if categoryError == nil {
            newLabel = ""
            newIcon = ""
        }
    }

    private var categoriesSection: some View {
        Section {
            ForEach(model.categories) { CategoryRow(model: model, category: $0) }
        } header: {
            Text("Categories")
        } footer: {
            Text("The sections of the shopping list, in this order. Deleting one moves its items to “Other”. Swipe left to delete.")
        }
    }
}

/// "Unsaved changes · Discard · Save", pinned to the bottom while there's a draft.
struct GrocerySaveBar: View {
    let model: GrocerySettingsModel

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            if model.hasBlankNames {
                ErrorBanner(message: "Names can't be empty.")
            } else if let error = model.error {
                ErrorBanner(message: error)
            }
            HStack {
                Text(model.hasChanges
                     ? "\(model.changeCount) unsaved change\(model.changeCount == 1 ? "" : "s")"
                     : "Some changes couldn't be saved")
                    .font(.subheadline.weight(.medium))
                Spacer()
                Button("Discard", role: .destructive) { model.discard() }
                    .disabled(model.isSaving)
                Button(model.isSaving ? "Saving…" : "Save") { Task { await model.save() } }
                    .buttonStyle(.borderedProminent)
                    .disabled(model.isSaving || !model.hasChanges || model.hasBlankNames)
            }
        }
        .padding()
        .background(.regularMaterial)
    }
}

// MARK: - Rows

private struct CategoryPicker: View {
    let model: GrocerySettingsModel
    @Binding var selection: String
    var allowsAuto = false

    var body: some View {
        Picker("Category", selection: $selection) {
            if allowsAuto { Text("Auto").tag(GrocerySettingsModel.auto) }
            ForEach(model.liveCategories) { c in
                Text("\(c.icon) \(c.label)\(c.state == .new ? " · new" : "")").tag(c.key)
            }
        }
        .pickerStyle(.menu)
        .labelsHidden()
        .fixedSize()
    }
}

private struct StateBadge: View {
    let state: DraftState
    let onUndo: () -> Void

    var body: some View {
        if state != .unchanged {
            Badge(text: state == .new ? "New" : state == .edited ? "Edited" : "Will be removed",
                  color: state == .new ? .green : state == .edited ? .orange : .red)
            Button("Undo", action: onUndo).font(.caption).buttonStyle(.borderless)
        }
    }
}

private struct SuggestionRow: View {
    let model: GrocerySettingsModel
    let suggestion: GrocerySuggestion
    @State private var category = "other"

    var body: some View {
        let dismissed = model.isDismissed(suggestion)
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(suggestion.name).strikethrough(dismissed).foregroundStyle(dismissed ? .secondary : .primary)
                Badge(text: "added \(suggestion.timesAdded)×", color: .indigo)
                Spacer()
                if dismissed {
                    StateBadge(state: .removed) { model.toggleDismiss(suggestion) }
                }
            }
            if !dismissed {
                HStack {
                    CategoryPicker(model: model, selection: $category)
                    Spacer()
                    Button("Dismiss") { model.toggleDismiss(suggestion) }
                        .buttonStyle(.borderless)
                        .foregroundStyle(.secondary)
                    Button("Add") { model.accept(suggestion, categoryKey: category) }
                        .buttonStyle(.borderedProminent)
                }
            }
        }
        .onAppear {
            let known = model.liveCategories.contains { $0.key == suggestion.categoryKey }
            category = known ? suggestion.categoryKey : "other"
        }
    }
}

private struct PresetRow: View {
    let model: GrocerySettingsModel
    let preset: PresetDraftRow

    var body: some View {
        let removed = preset.state == .removed
        VStack(alignment: .leading, spacing: 6) {
            TextField("Name", text: Binding(get: { preset.name }, set: { model.rename(preset, to: $0) }))
                .strikethrough(removed)
                .foregroundStyle(removed ? .secondary : .primary)
                .disabled(removed)
            HStack(spacing: 10) {
                CategoryPicker(
                    model: model,
                    selection: Binding(get: { pickerValue }, set: { model.setCategory(preset, to: $0) }),
                    allowsAuto: preset.isNew
                )
                .disabled(removed)
                StateBadge(state: preset.state) { model.undo(preset) }
                Spacer()
            }
        }
        .swipeActions {
            if preset.state == .unchanged || preset.state == .edited {
                Button("Remove", role: .destructive) { model.remove(preset) }
            }
        }
    }

    private var pickerValue: String {
        if preset.isNew && preset.categoryKey == GrocerySettingsModel.auto { return GrocerySettingsModel.auto }
        return model.liveCategories.contains { $0.key == preset.categoryKey } ? preset.categoryKey : "other"
    }
}

private struct CategoryRow: View {
    let model: GrocerySettingsModel
    let category: CategoryDraftRow

    var body: some View {
        let removed = category.state == .removed
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                TextField("🛍️", text: Binding(get: { category.icon }, set: { model.edit(category, icon: $0) }))
                    .frame(width: 44)
                    .multilineTextAlignment(.center)
                    .disabled(removed)
                TextField("Name", text: Binding(get: { category.label }, set: { model.edit(category, label: $0) }))
                    .strikethrough(removed)
                    .foregroundStyle(removed ? .secondary : .primary)
                    .disabled(removed)
            }
            HStack(spacing: 10) {
                if !category.canDelete { Badge(text: "Fallback") }
                StateBadge(state: category.state) { model.undo(category) }
                Spacer()
                MoveButtons(
                    canUp: model.canMove(category, by: -1), canDown: model.canMove(category, by: 1),
                    onMove: { model.move(category, by: $0) }
                )
            }
        }
        .swipeActions {
            if category.canDelete && (category.state == .unchanged || category.state == .edited) {
                Button("Delete", role: .destructive) { model.remove(category) }
            }
        }
    }
}

private struct MoveButtons: View {
    let canUp: Bool
    let canDown: Bool
    let onMove: (Int) -> Void

    var body: some View {
        HStack(spacing: 14) {
            Button { onMove(-1) } label: { Image(systemName: "arrow.up") }
                .disabled(!canUp)
                .accessibilityLabel("Move up")
            Button { onMove(1) } label: { Image(systemName: "arrow.down") }
                .disabled(!canDown)
                .accessibilityLabel("Move down")
        }
        .buttonStyle(.borderless)
        .font(.subheadline)
    }
}
