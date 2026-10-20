import SwiftUI

struct HouseholdDetailView: View {
    enum Tab: String, CaseIterable, Identifiable {
        case today = "Today", schedule = "Schedule", people = "People", chores = "Chores"
        var id: Self { self }
    }

    @State private var model: HouseholdViewModel
    @State private var tab: Tab = .today

    init(householdId: UUID) {
        _model = State(initialValue: HouseholdViewModel(householdId: householdId))
    }

    var body: some View {
        List {
            Picker("Section", selection: $tab) {
                ForEach(Tab.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .listRowBackground(Color.clear)
            .listRowInsets(EdgeInsets())

            if let error = model.error {
                ErrorBanner(message: error)
            }

            switch tab {
            case .today: TodaySection(model: model)
            case .schedule: ScheduleSection(model: model)
            case .people: PeopleSection(model: model)
            case .chores: ChoresSection(model: model)
            }
        }
        .navigationTitle(model.detail?.name ?? "Household")
        .toolbar {
            if let code = model.detail?.inviteCode {
                ShareLink(item: "Join our house on Roommates with invite code \(code)") {
                    Label(code, systemImage: "person.badge.plus")
                }
            }
        }
        .overlay { if model.detail == nil && model.isLoading { ProgressView() } }
        .refreshable { await model.load() }
        .task { await model.load() }
    }
}

// MARK: - Today

private struct TodaySection: View {
    let model: HouseholdViewModel

    var body: some View {
        Section(model.todayDate.map(DayFormat.long) ?? "Today") {
            if model.today.isEmpty {
                Text("No chores today. Add people and chores first.").foregroundStyle(.secondary)
            }
            ForEach(model.today) { task in
                TaskRow(task: task, canToggle: task.isMine || model.isAdmin) {
                    Task { await model.toggle(task) }
                }
            }
        }
    }
}

// MARK: - Schedule

private struct ScheduleSection: View {
    let model: HouseholdViewModel

    var body: some View {
        ForEach(Array(model.schedule.enumerated()), id: \.element.id) { index, day in
            Section(index == 0 ? "Today · \(DayFormat.short(day.date))" : DayFormat.short(day.date)) {
                ForEach(day.slots, id: \.chore.id) { slot in
                    HStack {
                        Text("\(ChoreIcon.emoji(for: slot.chore.name)) \(slot.chore.name)")
                        Spacer()
                        Text(slot.member.displayName)
                            .fontWeight(slot.member.id == model.detail?.myMemberId ? .bold : .regular)
                            .foregroundStyle(slot.member.id == model.detail?.myMemberId ? Color.accentColor : .secondary)
                        if slot.status == .done { Image(systemName: "checkmark").foregroundStyle(.green) }
                    }
                }
            }
        }
    }
}

// MARK: - People

private struct PeopleSection: View {
    let model: HouseholdViewModel
    @State private var newName = ""
    @State private var pendingRemoval: Member?

    var body: some View {
        if model.isAdmin {
            Section {
                HStack {
                    TextField("Roommate's name", text: $newName)
                    Button("Add") {
                        let name = newName.trimmingCharacters(in: .whitespaces)
                        newName = ""
                        Task { await model.addMember(name) }
                    }
                    .disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            } header: {
                Text("Add a roommate")
            } footer: {
                Text("New people join the end of every chore rotation. They can claim their name later with invite code \(model.detail?.inviteCode ?? "").")
            }
        }

        Section("\(model.detail?.members.count ?? 0) people") {
            ForEach(model.detail?.members ?? []) { member in
                HStack {
                    Text(String(member.displayName.prefix(1)).uppercased())
                        .font(.subheadline.bold())
                        .frame(width: 32, height: 32)
                        .background(Color.accentColor.opacity(0.15), in: Circle())
                    VStack(alignment: .leading) {
                        HStack(spacing: 6) {
                            Text(member.displayName)
                            if member.id == model.detail?.myMemberId { Badge(text: "You") }
                            if member.role == .admin { Badge(text: "Admin", color: .accentColor) }
                        }
                        Text(member.hasAccount ? "Has an account" : "No account yet")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
                .swipeActions {
                    if model.isAdmin && member.id != model.detail?.myMemberId {
                        Button("Remove", role: .destructive) { pendingRemoval = member }
                        Button(member.role == .admin ? "Make member" : "Make admin") {
                            Task { await model.toggleAdmin(member) }
                        }
                        .tint(.indigo)
                    }
                }
            }
        }
        .confirmationDialog(
            "Remove \(pendingRemoval?.displayName ?? "")?",
            isPresented: Binding(get: { pendingRemoval != nil }, set: { if !$0 { pendingRemoval = nil } }),
            titleVisibility: .visible
        ) {
            Button("Remove from house and rotations", role: .destructive) {
                if let member = pendingRemoval { Task { await model.removeMember(member) } }
            }
        }
    }
}

// MARK: - Chores

private struct ChoresSection: View {
    let model: HouseholdViewModel
    @State private var newChore = ""

    var body: some View {
        Section("Chores") {
            ForEach(model.chores) { chore in
                NavigationLink {
                    ChoreRotationView(model: model, chore: chore)
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text("\(ChoreIcon.emoji(for: chore.name)) \(chore.name)").font(.headline)
                            if !chore.isActive { Badge(text: "Paused", color: .orange) }
                        }
                        Text(rotationSummary(chore))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                    }
                }
            }
        }
        if model.isAdmin {
            Section("Add a chore") {
                HStack {
                    TextField("e.g. Clean bathroom", text: $newChore)
                    Button("Add") {
                        let name = newChore.trimmingCharacters(in: .whitespaces)
                        newChore = ""
                        Task { await model.addChore(name) }
                    }
                    .disabled(newChore.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            }
        }
    }

    private func rotationSummary(_ chore: Chore) -> String {
        guard !chore.rotation.isEmpty else { return "Nobody in the rotation yet" }
        let today = chore.todayAssignee.map { "Today: \($0.displayName) · " } ?? ""
        return today + chore.rotation.map(\.displayName).joined(separator: " → ") + " ↺"
    }
}
