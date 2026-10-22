import SwiftUI

struct HouseholdDetailView: View {
    enum Tab: String, CaseIterable, Identifiable {
        case today = "Today", activity = "Activity", report = "Report", schedule = "Schedule"
        case people = "People", chores = "Chores", history = "History"
        var id: Self { self }
    }

    @State private var model: HouseholdViewModel
    @State private var tab: Tab = .today

    init(householdId: UUID) {
        _model = State(initialValue: HouseholdViewModel(householdId: householdId))
    }

    private var tabs: [Tab] { Tab.allCases.filter { $0 != .history || model.isAdmin } }

    var body: some View {
        List {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(tabs) { t in
                        Button(t.rawValue) { tab = t }
                            .font(.subheadline.weight(.medium))
                            .padding(.horizontal, 12).padding(.vertical, 6)
                            .background(tab == t ? Color.accentColor : Color.secondary.opacity(0.12), in: Capsule())
                            .foregroundStyle(tab == t ? Color.white : Color.primary)
                            .buttonStyle(.plain)
                    }
                }
                .padding(.vertical, 4)
            }
            .listRowBackground(Color.clear)
            .listRowInsets(EdgeInsets())

            if let error = model.error {
                ErrorBanner(message: error)
            }

            switch tab {
            case .today: TodaySection(model: model)
            case .activity: ActivitySection(model: model)
            case .report: ReportTabSection(model: model)
            case .schedule: ScheduleSection(model: model)
            case .people: PeopleSection(model: model)
            case .chores: ChoresSection(model: model)
            case .history: HistorySection(model: model)
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

    private var daily: [ChoreTask] { model.today.filter { !$0.isWeekly } }
    private var weekly: [ChoreTask] { model.today.filter(\.isWeekly) }

    var body: some View {
        if model.today.isEmpty && model.open.isEmpty {
            Text("No chores yet. Add people and chores first.").foregroundStyle(.secondary)
        }
        SwapRequestsSection(swaps: model.swaps) { swap in await model.acceptSwap(swap) }
        if !daily.isEmpty {
            Section(model.todayDate.map(DayFormat.long) ?? "Today") {
                ForEach(daily) { row($0) }
            }
        }
        if !weekly.isEmpty {
            Section("This week") {
                ForEach(weekly) { row($0) }
            }
        }
        if !model.open.isEmpty {
            Section("Anyone can do") {
                ForEach(model.open) { item in
                    OpenChoreRow(
                        item: item, myMemberId: model.detail?.myMemberId,
                        today: model.todayDate,
                        onLog: { who in Task { await model.log(item, by: who) } },
                        onRemove: { log in Task { await model.removeLog(log) } }
                    )
                }
            }
        }
    }

    private func row(_ task: ChoreTask) -> some View {
        TaskRow(
            task: task, members: model.members, myMemberId: model.detail?.myMemberId,
            onDone: { who in Task { await model.complete(task, by: who) } },
            onUndo: { Task { await model.reopen(task) } },
            onAskSwap: { note in Task { await model.askForSwap(task, note: note) } },
            onCancelSwap: { id in Task { await model.cancelSwap(id) } }
        )
    }
}

// MARK: - Activity

private struct ActivitySection: View {
    let model: HouseholdViewModel

    private var groups: [(day: String, events: [ActivityEvent])] {
        var result: [(String, [ActivityEvent])] = []
        for event in model.activity {
            let day = DayFormat.timestamp(event.createdAt)?
                .formatted(.dateTime.weekday(.wide).month(.wide).day()) ?? ""
            if result.last?.0 == day {
                result[result.count - 1].1.append(event)
            } else {
                result.append((day, [event]))
            }
        }
        return result
    }

    var body: some View {
        if model.activity.isEmpty {
            Text("No activity yet.").foregroundStyle(.secondary)
        }
        ForEach(groups, id: \.day) { group in
            Section(group.day) {
                ForEach(group.events) { event in
                    let line = ActivityText.describe(event)
                    HStack(alignment: .firstTextBaseline, spacing: 10) {
                        Text(line.icon)
                        Text(line.text).font(.subheadline)
                        Spacer(minLength: 0)
                        Text(DayFormat.time(event.createdAt)).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }
    }
}

// MARK: - Report & History

private struct ReportTabSection: View {
    let model: HouseholdViewModel

    var body: some View {
        if let report = model.report {
            ReportSections(report: report, myMemberId: model.detail?.myMemberId)
        }
    }
}

private struct HistorySection: View {
    @Bindable var model: HouseholdViewModel

    var body: some View {
        Group {
            if model.pastMonths.isEmpty {
                Text("No past months yet. This month's numbers are in the Report tab.")
                    .foregroundStyle(.secondary)
            } else {
                Picker("Month", selection: $model.selectedMonth) {
                    ForEach(model.pastMonths, id: \.self) { Text(DayFormat.month($0)).tag(Optional($0)) }
                }
                .onChange(of: model.selectedMonth) { _, _ in Task { await model.loadHistory() } }
                if let report = model.pastReport {
                    ReportSections(report: report, myMemberId: model.detail?.myMemberId)
                }
            }
        }
        .task { await model.loadHistory() }
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
                        if slot.chore.frequency == .weekly { Badge(text: "Week") }
                        Spacer()
                        Text(slot.member.displayName)
                            .fontWeight(slot.member.id == model.detail?.myMemberId ? .bold : .regular)
                            .foregroundStyle(slot.member.id == model.detail?.myMemberId ? Color.accentColor : .secondary)
                        if slot.status == .done { Image(systemName: "checkmark").foregroundStyle(.green) }
                        if let other = slot.swappedWith {
                            Image(systemName: "arrow.left.arrow.right")
                                .font(.caption)
                                .foregroundStyle(.pink)
                                .accessibilityLabel("Swapped with \(other.displayName)")
                        }
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
    @State private var frequency: Frequency = .daily
    @State private var mode: AssignmentMode = .rotation
    @State private var target = 0

    var body: some View {
        Section("Chores") {
            ForEach(model.chores) { chore in
                NavigationLink {
                    ChoreRotationView(model: model, chore: chore)
                } label: {
                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 6) {
                            Text("\(ChoreIcon.emoji(for: chore.name)) \(chore.name)").font(.headline)
                            Badge(text: chore.frequency == .weekly ? "Weekly" : "Daily")
                            if chore.isOpen { Badge(text: "Anyone", color: .green) }
                            if !chore.isActive { Badge(text: "Paused", color: .orange) }
                        }
                        Text(summary(chore))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                    }
                }
            }
        }
        if model.isAdmin {
            Section {
                TextField("e.g. Clean bathroom", text: $newChore)
                Picker("How often", selection: $frequency) {
                    ForEach(Frequency.allCases) { Text($0.label).tag($0) }
                }
                Picker("Who does it", selection: $mode) {
                    ForEach(AssignmentMode.allCases) { Text($0.label).tag($0) }
                }
                if mode == .open {
                    Stepper(target == 0 ? "No weekly target" : "Target: \(target)× per week", value: $target, in: 0...50)
                }
                Button("Add chore") {
                    let name = newChore.trimmingCharacters(in: .whitespaces)
                    newChore = ""
                    Task { await model.addChore(name, frequency: frequency, mode: mode, target: target == 0 ? nil : target) }
                }
                .disabled(newChore.trimmingCharacters(in: .whitespaces).isEmpty)
            } header: {
                Text("Add a chore")
            } footer: {
                Text("Need it twice a day? Add two chores, e.g. \"Cooking – Lunch\" and \"Cooking – Dinner\".")
            }
        }
    }

    private func summary(_ chore: Chore) -> String {
        if chore.isOpen {
            return "Nobody assigned · whoever does it logs it" + (chore.targetPerWeek.map { " · \($0)× per week" } ?? "")
        }
        guard !chore.rotation.isEmpty else { return "Nobody in the rotation yet" }
        let label = chore.frequency == .weekly ? "This week" : "Today"
        let current = chore.todayAssignee.map { "\(label): \($0.displayName) · " } ?? ""
        return current + chore.rotation.map(\.displayName).joined(separator: " → ") + " ↺"
    }
}
