import SwiftUI

/// Shows a chore's round-robin order; admins can drag to reorder, skip or add people.
struct ChoreRotationView: View {
    let model: HouseholdViewModel
    let chore: Chore

    @Environment(\.dismiss) private var dismiss
    @State private var order: [MemberBrief]
    @State private var confirmDelete = false

    init(model: HouseholdViewModel, chore: Chore) {
        self.model = model
        self.chore = chore
        _order = State(initialValue: chore.rotation)
    }

    private var everyone: [MemberBrief] { model.detail?.members.map(\.brief) ?? [] }
    private var excluded: [MemberBrief] { everyone.filter { m in !order.contains { $0.id == m.id } } }
    private var hasChanges: Bool { order.map(\.id) != chore.rotation.map(\.id) }

    var body: some View {
        List {
            Section {
                ForEach(Array(order.enumerated()), id: \.element.id) { index, member in
                    HStack {
                        Text("\(index + 1).").foregroundStyle(.secondary).frame(width: 28, alignment: .leading)
                        Text(member.displayName)
                        Spacer()
                        if member.id == chore.todayAssignee?.id && !hasChanges {
                            Badge(text: "Today", color: .accentColor)
                        }
                    }
                }
                .onMove { order.move(fromOffsets: $0, toOffset: $1) }
                .onDelete { order.remove(atOffsets: $0) }
                .moveDisabled(!model.isAdmin)
                .deleteDisabled(!model.isAdmin)
            } header: {
                Text("Rotation · daily · repeats")
            } footer: {
                if model.isAdmin {
                    Text("Drag to reorder, swipe to skip someone. Today's person stays the same; the new order applies from tomorrow.")
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

            if model.isAdmin {
                Section {
                    Button(chore.isActive ? "Pause chore" : "Resume chore") {
                        Task {
                            await model.setActive(chore, !chore.isActive)
                            dismiss()
                        }
                    }
                    Button("Delete chore", role: .destructive) { confirmDelete = true }
                }
            }
        }
        .environment(\.editMode, .constant(model.isAdmin ? .active : .inactive))
        .navigationTitle(chore.name)
        .toolbar {
            if model.isAdmin {
                Button("Save") {
                    Task {
                        await model.setRotation(chore, order)
                        dismiss()
                    }
                }
                .disabled(!hasChanges)
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
