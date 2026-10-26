import SwiftUI

@MainActor
@Observable
final class MyDayViewModel {
    var tasks: [ChoreTask] = []
    var overdue: [ChoreTask] = []
    var open: [OpenChore] = []
    var swaps: [Swap] = []  // open swap requests in my households
    var households: [Household] = []
    var membersByHousehold: [UUID: [MemberBrief]] = [:]
    var isLoading = false
    var hasLoaded = false
    var error: String?

    private let client = APIClient.shared

    var pendingCount: Int { tasks.filter { !$0.isDone }.count }

    func myMemberId(in householdId: UUID) -> UUID? {
        households.first { $0.id == householdId }?.myMemberId
    }

    func load() async {
        isLoading = true
        defer { isLoading = false; hasLoaded = true }
        do {
            async let mine = client.myTasksToday()
            async let houses = client.households()
            async let openSwaps = client.mySwaps()
            let (m, h, s) = try await (mine, houses, openSwaps)
            tasks = m.tasks
            overdue = m.overdue
            open = m.open
            swaps = s
            households = h
            error = nil
            // Members power the "someone else did it" menu.
            for house in h where membersByHousehold[house.id] == nil {
                membersByHousehold[house.id] = try? await client.household(house.id).members.map(\.brief)
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Reloads after any answer: a 409 means our list was stale.
    func acceptSwap(_ swap: Swap) async -> SwapOutcome {
        let outcome = await SwapOutcome.accept(swap)
        await load()
        return outcome
    }

    func perform(_ change: @escaping () async throws -> Void) async {
        do {
            try await change()
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// First screen after login: the in-app reminder of what the signed-in person has to do.
struct MyDayView: View {
    @Environment(Session.self) private var session
    @Environment(\.scenePhase) private var scenePhase
    @State private var model = MyDayViewModel()
    /// ☀️ Today: my turns across my houses · 🧹 Chores: every chore of my current house.
    @State private var mode: Mode = .today
    enum Mode: String, CaseIterable { case today = "☀️ Today", chores = "🧹 Chores" }

    private var multiHouse: Bool { model.households.count > 1 }

    var body: some View {
        NavigationStack {
            List {
                if !model.households.isEmpty {
                    Picker("View", selection: $mode) {
                        ForEach(Mode.allCases, id: \.self) { Text($0.rawValue).tag($0) }
                    }
                    .pickerStyle(.segmented)
                    .listRowBackground(Color.clear)
                    .listRowInsets(EdgeInsets())
                }
                if mode == .chores, let houseId = session.preferredHousehold(in: model.households) {
                    MyDayChores(householdId: houseId).id(houseId)  // a new house, a fresh list
                } else {
                Section {
                    DaySummaryCard(headline: headline, pending: model.pendingCount, total: model.tasks.count,
                                   loaded: model.hasLoaded)
                    ErrorBanner(message: model.error)
                }
                .listRowBackground(Color.clear)
                .listRowInsets(EdgeInsets(top: 4, leading: 0, bottom: 4, trailing: 0))

                if model.hasLoaded && model.households.isEmpty {
                    ContentUnavailableView(
                        "No household yet",
                        systemImage: "house",
                        description: Text("Create one or join with an invite code in the Households tab.")
                    )
                } else {
                    SwapRequestsSection(swaps: model.swaps, showHousehold: multiHouse) { swap in
                        await model.acceptSwap(swap)
                    }
                    Section {
                        if model.tasks.isEmpty && model.hasLoaded {
                            Text("Enjoy your day off 🎉").foregroundStyle(.secondary)
                        }
                        ForEach(model.tasks) { taskRow($0) }
                    } header: {
                        IconHeader(title: "Your turns", systemImage: "person.fill.checkmark", color: Brand.indigo)
                    }
                    if !model.open.isEmpty {
                        Section {
                            ForEach(model.open) { item in
                                OpenChoreRow(
                                    item: item,
                                    myMemberId: model.myMemberId(in: item.householdId),
                                    showHousehold: multiHouse,
                                    onLog: { who in Task { await model.perform { _ = try await APIClient.shared.logChore(item.chore.id, memberId: who) } } },
                                    onRemove: { log in Task { await model.perform { try await APIClient.shared.removeLog(log.id) } } }
                                )
                            }
                        } header: {
                            IconHeader(title: "Anyone can do", systemImage: "sparkles", color: Brand.teal)
                        }
                    }
                    if !model.overdue.isEmpty {
                        Section {
                            ForEach(model.overdue) { taskRow($0, overdue: true) }
                        } header: {
                            IconHeader(title: "Missed earlier", systemImage: "clock.badge.exclamationmark", color: .orange)
                        }
                    }
                }
                }
            }
            .brandBackground()
            .navigationTitle("Hi \(session.user?.name ?? "") 👋")
            .profileToolbar()
            .overlay { if model.isLoading && !model.hasLoaded { ProgressView() } }
            .refreshable { await model.load() }
            .task { await model.load() }
            // "Today" changes at midnight; refresh whenever the app comes back to the foreground.
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { Task { await model.load() } }
            }
        }
    }

    private func taskRow(_ task: ChoreTask, overdue: Bool = false) -> some View {
        TaskRow(
            task: task,
            members: model.membersByHousehold[task.householdId] ?? [],
            myMemberId: model.myMemberId(in: task.householdId),
            showHousehold: multiHouse,
            overdue: overdue,
            onDone: { who in Task { await model.perform { _ = try await APIClient.shared.completeTask(task.id, completedBy: who) } } },
            onUndo: { Task { await model.perform { _ = try await APIClient.shared.reopenTask(task.id) } } },
            onAskSwap: { note in
                Task {
                    await model.perform {
                        _ = try await APIClient.shared.askForSwap(choreId: task.chore.id, dueDate: task.dueDate, note: note)
                    }
                }
            },
            onCancelSwap: { id in Task { await model.perform { _ = try await APIClient.shared.cancelSwap(id) } } }
        )
    }

    private var headline: String {
        if !model.hasLoaded { return "Loading your chores…" }
        if model.tasks.isEmpty { return "No turns for you right now." }
        if model.pendingCount == 0 { return "All your turns are done. Nice!" }
        return "You have \(model.pendingCount) chore\(model.pendingCount > 1 ? "s" : "") to do."
    }
}

/// The top of Today: how my day is going, on the brand gradient, with a ring that fills as turns get done.
private struct DaySummaryCard: View {
    let headline: String
    let pending: Int
    let total: Int
    let loaded: Bool

    private var progress: Double { total == 0 ? 1 : Double(total - pending) / Double(total) }

    var body: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text(Date.now, format: .dateTime.weekday(.wide).month().day())
                    .font(.caption.weight(.semibold))
                    .textCase(.uppercase)
                    .foregroundStyle(.white.opacity(0.8))
                Text(headline)
                    .font(.title3.weight(.bold))
                    .foregroundStyle(.white)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
            if loaded && total > 0 {
                ZStack {
                    Circle().stroke(.white.opacity(0.25), lineWidth: 6)
                    Circle().trim(from: 0, to: progress)
                        .stroke(.white, style: StrokeStyle(lineWidth: 6, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                    Text("\(total - pending)/\(total)")
                        .font(.caption.weight(.bold).monospacedDigit())
                        .foregroundStyle(.white)
                }
                .frame(width: 54, height: 54)
                .animation(.snappy, value: progress)
            }
        }
        .padding(18)
        .background(Brand.diagonal, in: RoundedRectangle(cornerRadius: 22))
        .shadow(color: Brand.indigo.opacity(0.3), radius: 14, y: 6)
    }
}

/// My day → Chores: the chores of my current house (the one I picked or opened last).
private struct MyDayChores: View {
    let householdId: UUID
    @State private var model: HouseholdViewModel

    init(householdId: UUID) {
        self.householdId = householdId
        _model = State(initialValue: HouseholdViewModel(householdId: householdId))
    }

    var body: some View {
        Group {
            if let name = model.detail?.name {
                Section {
                    Text("Every chore in \(name) and whose turn it is.").font(.subheadline).foregroundStyle(.secondary)
                }
                .listRowBackground(Color.clear)
            }
            ErrorBanner(message: model.error)
            ChoresSection(model: model)
        }
        .task { await model.load() }
    }
}
