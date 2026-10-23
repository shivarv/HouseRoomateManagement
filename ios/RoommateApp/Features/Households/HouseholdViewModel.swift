import Foundation
import Observation

@MainActor
@Observable
final class HouseholdViewModel {
    let householdId: UUID

    var detail: HouseholdDetail?
    var todayDate: String?
    var today: [ChoreTask] = []
    var open: [OpenChore] = []
    var swaps: [Swap] = []  // open swap requests
    var chores: [Chore] = []
    var schedule: [ScheduleDay] = []
    var activity: [ActivityEvent] = []
    var report: Report?
    var error: String?
    var isLoading = false

    // History (admins): past months.
    var pastMonths: [String] = []
    var selectedMonth: String?
    var pastReport: Report?

    private let client = APIClient.shared

    init(householdId: UUID) {
        self.householdId = householdId
    }

    var isAdmin: Bool { detail?.isAdmin ?? false }
    var members: [MemberBrief] { detail?.members.map(\.brief) ?? [] }

    func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            async let d = client.household(householdId)
            async let t = client.householdTasksToday(householdId: householdId)
            async let c = client.chores(householdId: householdId)
            async let s = client.schedule(householdId: householdId, days: 14)
            async let a = client.activity(householdId: householdId)
            async let r = client.report(householdId: householdId)
            async let w = client.householdSwaps(householdId: householdId)
            let (detail, today, chores, schedule, activity, report) = try await (d, t, c, s, a, r)
            self.swaps = try await w
            self.detail = detail
            self.todayDate = today.date
            self.today = today.tasks
            self.open = today.open
            self.chores = chores
            self.schedule = schedule.days
            self.activity = activity
            self.report = report
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    func loadHistory() async {
        guard isAdmin else { return }
        do {
            pastMonths = Array(try await client.reportMonths(householdId: householdId).months.dropFirst())
            if selectedMonth == nil { selectedMonth = pastMonths.first }
            if let month = selectedMonth {
                pastReport = try await client.report(householdId: householdId, month: month)
            }
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Runs a change, then reloads everything (any change can affect today, the feed and the report).
    func perform(_ change: @escaping () async throws -> Void) async {
        do {
            try await change()
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    func complete(_ task: ChoreTask, by member: UUID?) async {
        await perform { _ = try await self.client.completeTask(task.id, completedBy: member) }
    }

    func reopen(_ task: ChoreTask) async {
        await perform { _ = try await self.client.reopenTask(task.id) }
    }

    func askForSwap(_ task: ChoreTask, note: String?) async {
        await perform {
            _ = try await self.client.askForSwap(choreId: task.chore.id, dueDate: task.dueDate, note: note)
        }
    }

    func cancelSwap(_ id: UUID) async {
        await perform { _ = try await self.client.cancelSwap(id) }
    }

    /// Reloads after any answer: a 409 means our list was stale.
    func acceptSwap(_ swap: Swap) async -> SwapOutcome {
        let outcome = await SwapOutcome.accept(swap)
        await load()
        return outcome
    }

    func log(_ item: OpenChore, by member: UUID?) async {
        await perform { _ = try await self.client.logChore(item.chore.id, memberId: member) }
    }

    func removeLog(_ log: ChoreLog) async {
        await perform { try await self.client.removeLog(log.id) }
    }

    func removeMember(_ member: Member) async {
        await perform { try await self.client.removeMember(member.id) }
    }

    func toggleAdmin(_ member: Member) async {
        await perform { _ = try await self.client.setRole(memberId: member.id, role: member.role == .admin ? .member : .admin) }
    }

    func addChore(_ name: String, frequency: Frequency, mode: AssignmentMode, target: Int?) async {
        await perform {
            _ = try await self.client.createChore(householdId: self.householdId, name: name, frequency: frequency,
                                                  mode: mode, targetPerWeek: target)
        }
    }

    func setRotation(_ chore: Chore, _ members: [MemberBrief]) async {
        await perform { _ = try await self.client.setRotation(choreId: chore.id, memberIds: members.map(\.id)) }
    }

    func update(_ chore: Chore, _ changes: ChoreChanges) async {
        await perform { _ = try await self.client.updateChore(chore.id, changes) }
    }

    func deleteChore(_ chore: Chore) async {
        await perform { try await self.client.deleteChore(chore.id) }
    }
}
