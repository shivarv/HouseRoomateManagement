import SwiftUI

struct HouseholdDetailView: View {
    enum Tab: String, CaseIterable, Identifiable {
        case today = "Today", activity = "Activity", house = "House"  // chores live in My day
        var id: Self { self }
    }

    /// 🏡 House: who's in the house, whose turn is when, and how everyone's doing. Mirrors web.
    enum HousePart: String, CaseIterable, Identifiable {
        case schedule = "Schedule", report = "Report", people = "People"
        var id: Self { self }
    }

    @State private var model: HouseholdViewModel
    @State private var tab: Tab = .today
    @Environment(\.dismiss) private var dismiss
    @State private var housePart: HousePart = .schedule
    @State private var inviting = false

    init(householdId: UUID) {
        _model = State(initialValue: HouseholdViewModel(householdId: householdId))
    }

    var body: some View {
        List {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(Tab.allCases) { t in
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
            case .house:
                Picker("House", selection: $housePart) {
                    ForEach(HousePart.allCases) { Text($0.rawValue).tag($0) }
                }
                .pickerStyle(.segmented)
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets())
                switch housePart {
                case .schedule: ScheduleSection(model: model)
                case .report: ReportTabSection(model: model)
                case .people: PeopleSection(model: model)
                }
            }
        }
        .navigationTitle(model.detail?.name ?? "Household")
        .toolbar {
            if model.detail != nil {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { inviting = true } label: { Label("Invite people", systemImage: "person.badge.plus") }
                }
            }
            // Admin pages live in Settings, apart from the everyday tabs (also under Profile → Sign out).
            if model.isAdmin {
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink {
                        HouseSettingsView(model: model) { dismiss() }
                    } label: {
                        Label("Settings", systemImage: "gearshape")
                    }
                }
            }
        }
        .overlay { if model.detail == nil && model.isLoading { ProgressView() } }
        .sheet(isPresented: $inviting, onDismiss: { Task { await model.load() } }) {
            if let detail = model.detail { InviteSheet(house: detail) }
        }
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

/// Past months (admins). Shown in Settings.
struct HistorySection: View {
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
                Group {
                    // Admins tap someone who hasn't joined to add their email / phone and invite them.
                    if model.isAdmin && !member.hasAccount {
                        NavigationLink { MemberContactView(model: model, member: member) } label: { memberRow(member) }
                    } else {
                        memberRow(member)
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

private extension PeopleSection {
    func memberRow(_ member: Member) -> some View {
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
                    Badge(text: member.status.label,
                          color: member.status == .verified ? .green : member.status == .joined ? .accentColor : member.status == .invited ? .orange : .gray)
                }
                Text(contactLine(member))
                    .font(.caption).foregroundStyle(.secondary)
            }
        }
    }
}

/// "Beatrice Smith · bea@example.com · +1 617…", or what their status means.
private func contactLine(_ m: Member) -> String {
    let parts = [m.fullName != m.displayName ? m.fullName : "", m.email ?? "", m.phone ?? ""].filter { !$0.isEmpty }
    if !parts.isEmpty { return parts.joined(separator: " · ") }
    switch m.status {
    case .added: return "Added by name — invite them to join"
    case .invited: return "Invite sent — waiting for them to join"
    case .joined: return "Has an account — email not confirmed yet"
    case .verified: return "Has an account with a confirmed email"
    }
}

/// Admins: an email and phone for someone who hasn't joined, and an email invite to them.
private struct MemberContactView: View {
    let model: HouseholdViewModel
    let member: Member
    @State private var email: String
    @State private var phone: String
    @State private var error: String?
    @State private var note: String?
    @State private var busy = false

    init(model: HouseholdViewModel, member: Member) {
        self.model = model
        self.member = member
        _email = State(initialValue: member.email ?? "")
        _phone = State(initialValue: member.phone ?? "")
    }

    private var changed: Bool {
        email.trimmingCharacters(in: .whitespaces) != (member.email ?? "") || phone.trimmingCharacters(in: .whitespaces) != (member.phone ?? "")
    }

    var body: some View {
        Form {
            Section {
                TextField("Email (optional)", text: $email)
                    .keyboardType(.emailAddress).textInputAutocapitalization(.never).autocorrectionDisabled()
                TextField("Phone (optional)", text: $phone).keyboardType(.phonePad)
            } footer: {
                Text("Used to invite them, and later for notifications. Once they join, their account's email is used.")
            }
            Section {
                Button(busy ? "Saving…" : "Save") { Task { await save() } }.disabled(!changed || busy)
                if !email.isEmpty {
                    Button(member.status == .invited ? "Invite again" : "Send invite by email") { Task { await invite() } }
                        .disabled(changed || busy)
                }
            } footer: {
                VStack(alignment: .leading) {
                    if let note { Text(note).foregroundStyle(.green) }
                    ErrorBanner(message: error)
                }
            }
        }
        .navigationTitle(member.displayName)
    }

    private func save() async {
        busy = true
        defer { busy = false }
        do {
            _ = try await APIClient.shared.setContact(memberId: member.id, email: email.trimmingCharacters(in: .whitespaces),
                                                      phone: phone.trimmingCharacters(in: .whitespaces))
            error = nil
            note = "Saved"
            await model.load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    private func invite() async {
        busy = true
        defer { busy = false }
        do {
            let res = try await APIClient.shared.emailInvites(householdId: model.householdId, emails: [email.trimmingCharacters(in: .whitespaces)])
            note = res.emailEnabled ? "Invite emailed" : "Invited — they'll see it when they sign up with this email"
            error = nil
            await model.load()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

// MARK: - Chores

/// Every chore with its rotation; admins add and edit them. Shown in My day → Chores.
struct ChoresSection: View {
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
                            if !chore.isOpen, let who = whoTakesTurns(chore) { Badge(text: who.text, color: who.everyone ? .green : .orange) }
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

    /// "👥 Everyone" · "👥 Everyone except Bea" · "👥 3 of 8": who's in the rotation.
    private func whoTakesTurns(_ chore: Chore) -> (text: String, everyone: Bool)? {
        guard let everyone = model.detail?.members, !everyone.isEmpty else { return nil }
        let inIt = Set(chore.rotation.map(\.id))
        let left = everyone.filter { !inIt.contains($0.id) }
        if left.isEmpty { return ("👥 Everyone", true) }
        if left.count <= 2 && chore.rotation.count > left.count {
            return ("👥 Everyone except " + left.map(\.displayName).joined(separator: " & "), false)
        }
        return ("👥 \(chore.rotation.count) of \(everyone.count)", false)
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
