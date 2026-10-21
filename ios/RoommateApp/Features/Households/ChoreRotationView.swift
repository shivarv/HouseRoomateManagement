import SwiftUI

/// A chore's settings and (for rotation chores) its round-robin order.
/// Admins can change how often it happens, who does it, and drag to reorder.
struct ChoreRotationView: View {
    let model: HouseholdViewModel
    let chore: Chore

    @Environment(\.dismiss) private var dismiss
    @State private var order: [MemberBrief]
    @State private var frequency: Frequency
    @State private var mode: AssignmentMode
    @State private var target: Int
    @State private var confirmDelete = false

    init(model: HouseholdViewModel, chore: Chore) {
        self.model = model
        self.chore = chore
        _order = State(initialValue: chore.rotation)
        _frequency = State(initialValue: chore.frequency)
        _mode = State(initialValue: chore.assignmentMode)
        _target = State(initialValue: chore.targetPerWeek ?? 0)
    }

    private var everyone: [MemberBrief] { model.members }
    private var excluded: [MemberBrief] { everyone.filter { m in !order.contains { $0.id == m.id } } }
    private var orderChanged: Bool { order.map(\.id) != chore.rotation.map(\.id) }
    private var settingsChanged: Bool {
        frequency != chore.frequency || mode != chore.assignmentMode
            || (mode == .open && target != (chore.targetPerWeek ?? 0))
    }

    var body: some View {
        List {
            Section {
                Picker("How often", selection: $frequency) {
                    ForEach(Frequency.allCases) { Text($0.label).tag($0) }
                }
                Picker("Who does it", selection: $mode) {
                    ForEach(AssignmentMode.allCases) { Text($0.label).tag($0) }
                }
                if mode == .open {
                    Stepper(target == 0 ? "No weekly target" : "Target: \(target)× per week", value: $target, in: 0...50)
                }
            } header: {
                Text("Settings")
            } footer: {
                if settingsChanged { Text("The change applies from today. History is kept.") }
            }
            .disabled(!model.isAdmin)

            if mode == .rotation {
                Section {
                    ForEach(Array(order.enumerated()), id: \.element.id) { index, member in
                        HStack {
                            Text("\(index + 1).").foregroundStyle(.secondary).frame(width: 28, alignment: .leading)
                            Text(member.displayName)
                            Spacer()
                            if member.id == chore.todayAssignee?.id && !orderChanged {
                                Badge(text: chore.frequency == .weekly ? "This week" : "Today", color: .accentColor)
                            }
                        }
                    }
                    .onMove { order.move(fromOffsets: $0, toOffset: $1) }
                    .onDelete { order.remove(atOffsets: $0) }
                    .moveDisabled(!model.isAdmin)
                    .deleteDisabled(!model.isAdmin)
                } header: {
                    Text("Rotation · \(frequency == .weekly ? "one person per week" : "one person per day") · repeats")
                } footer: {
                    if model.isAdmin {
                        Text("Drag to reorder, swipe to skip someone. The current person keeps their turn; the new order applies after that.")
                    }
                }

                if model.isAdmin && !excluded.isEmpty {
                    Section("Not in this rotation") {
                        ForEach(excluded) { member in
                            Button {
                                order.append(member)
                            } label: {
                                Label(member.displayName, systemImage: "plus.circle")
                            }
                        }
                    }
                }
            } else {
                Section {
                    Text("Nobody is assigned. Whoever does it taps \"I did it\"; the Report tab shows who did it how often.")
                        .foregroundStyle(.secondary)
                }
            }

            if model.isAdmin {
                Section {
                    Button(chore.isActive ? "Pause chore" : "Resume chore") {
                        Task {
                            await model.update(chore, ChoreChanges(isActive: !chore.isActive))
                            dismiss()
                        }
                    }
                    Button("Delete chore", role: .destructive) { confirmDelete = true }
                }
            }
        }
        .environment(\.editMode, .constant(model.isAdmin && mode == .rotation ? .active : .inactive))
        .navigationTitle(chore.name)
        .toolbar {
            if model.isAdmin {
                Button("Save") {
                    Task {
                        if settingsChanged {
                            await model.update(chore, ChoreChanges(
                                frequency: frequency == chore.frequency ? nil : frequency,
                                assignmentMode: mode == chore.assignmentMode ? nil : mode,
                                targetPerWeek: mode == .open ? target : nil
                            ))
                        }
                        if orderChanged && mode == .rotation {
                            await model.setRotation(chore, order)
                        }
                        dismiss()
                    }
                }
                .disabled(!orderChanged && !settingsChanged)
            }
        }
        .confirmationDialog("Delete \"\(chore.name)\" and its history?", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                Task {
                    await model.deleteChore(chore)
                    dismiss()
                }
            }
        }
    }
}
