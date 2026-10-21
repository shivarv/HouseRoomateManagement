import SwiftUI

@MainActor
@Observable
final class MyDayViewModel {
    var tasks: [ChoreTask] = []
    var overdue: [ChoreTask] = []
    var open: [OpenChore] = []
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
            let (m, h) = try await (mine, houses)
            tasks = m.tasks
            overdue = m.overdue
            open = m.open
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

    private var multiHouse: Bool { model.households.count > 1 }

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text(headline)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    ErrorBanner(message: model.error)
                }
                .listRowBackground(Color.clear)

                if model.hasLoaded && model.households.isEmpty {
                    ContentUnavailableView(
                        "No household yet",
                        systemImage: "house",
                        description: Text("Create one or join with an invite code in the Households tab.")
                    )
                } else {
                    Section("Your turns") {
                        if model.tasks.isEmpty && model.hasLoaded {
                            Text("Enjoy your day off 🎉").foregroundStyle(.secondary)
                        }
                        ForEach(model.tasks) { taskRow($0) }
                    }
                    if !model.open.isEmpty {
                        Section("Anyone can do") {
                            ForEach(model.open) { item in
                                OpenChoreRow(
                                    item: item,
                                    myMemberId: model.myMemberId(in: item.householdId),
                                    showHousehold: multiHouse,
                                    onLog: { who in Task { await model.perform { _ = try await APIClient.shared.logChore(item.chore.id, memberId: who) } } },
                                    onRemove: { log in Task { await model.perform { try await APIClient.shared.removeLog(log.id) } } }
                                )
                            }
                        }
                    }
                    if !model.overdue.isEmpty {
                        Section("Missed earlier") {
                            ForEach(model.overdue) { taskRow($0, overdue: true) }
                        }
                    }
                }
            }
            .navigationTitle("Hi \(session.user?.name ?? "") 👋")
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
            onUndo: { Task { await model.perform { _ = try await APIClient.shared.reopenTask(task.id) } } }
        )
    }

    private var headline: String {
        if !model.hasLoaded { return "Loading your chores…" }
        if model.tasks.isEmpty { return "No turns for you right now." }
        if model.pendingCount == 0 { return "All your turns are done. Nice!" }
        return "You have \(model.pendingCount) chore\(model.pendingCount > 1 ? "s" : "") to do."
    }
}
