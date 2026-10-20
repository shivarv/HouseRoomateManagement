import SwiftUI

@MainActor
@Observable
final class MyDayViewModel {
    var tasks: [ChoreTask] = []
    var overdue: [ChoreTask] = []
    var householdCount = 0
    var isLoading = false
    var hasLoaded = false
    var error: String?

    var pendingCount: Int { tasks.filter { !$0.isDone }.count }

    func load() async {
        isLoading = true
        defer { isLoading = false; hasLoaded = true }
        do {
            async let mine = APIClient.shared.myTasksToday()
            async let houses = APIClient.shared.households()
            let (m, h) = try await (mine, houses)
            tasks = m.tasks
            overdue = m.overdue
            householdCount = h.count
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func toggle(_ task: ChoreTask) async {
        do {
            _ = try await APIClient.shared.setTask(task.id, done: !task.isDone)
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }
}

/// First screen after login: the in-app reminder of what the signed-in person has to do today.
struct MyDayView: View {
    @Environment(Session.self) private var session
    @Environment(\.scenePhase) private var scenePhase
    @State private var model = MyDayViewModel()

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

                if model.hasLoaded && model.householdCount == 0 {
                    ContentUnavailableView(
                        "No household yet",
                        systemImage: "house",
                        description: Text("Create one or join with an invite code in the Households tab.")
                    )
                } else {
                    Section("Your tasks today") {
                        if model.tasks.isEmpty && model.hasLoaded {
                            Text("Enjoy your day off 🎉").foregroundStyle(.secondary)
                        }
                        ForEach(model.tasks) { task in
                            TaskRow(task: task, canToggle: true, showHousehold: model.householdCount > 1) {
                                Task { await model.toggle(task) }
                            }
                        }
                    }
                    if !model.overdue.isEmpty {
                        Section("Missed earlier") {
                            ForEach(model.overdue) { task in
                                TaskRow(task: task, canToggle: true, showHousehold: model.householdCount > 1, overdue: true) {
                                    Task { await model.toggle(task) }
                                }
                            }
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

    private var headline: String {
        if !model.hasLoaded { return "Loading your chores…" }
        if model.tasks.isEmpty { return "Nothing assigned to you today." }
        if model.pendingCount == 0 { return "All done for today. Nice!" }
        return "You have \(model.pendingCount) chore\(model.pendingCount > 1 ? "s" : "") to do today."
    }
}
