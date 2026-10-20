import Foundation
import Observation

@MainActor
@Observable
final class HouseholdViewModel {
    let householdId: UUID

    var detail: HouseholdDetail?
    var todayDate: String?
    var today: [ChoreTask] = []
    var chores: [Chore] = []
    var schedule: [ScheduleDay] = []
    var error: String?
    var isLoading = false

    private let client = APIClient.shared

    init(householdId: UUID) {
        self.householdId = householdId
    }

    var isAdmin: Bool { detail?.isAdmin ?? false }

    func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            async let d = client.household(householdId)
            async let t = client.householdTasksToday(householdId: householdId)
            async let c = client.chores(householdId: householdId)
            async let s = client.schedule(householdId: householdId, days: 14)
            let (detail, today, chores, schedule) = try await (d, t, c, s)
            self.detail = detail
            self.todayDate = today.date
            self.today = today.tasks
            self.chores = chores
            self.schedule = schedule.days
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Runs a change, then reloads everything (rotation changes affect today and the schedule).
    func perform(_ change: @escaping () async throws -> Void) async {
        do {
            try await change()
            await load()
        } catch {
            self.error = error.localizedDescription
        }
    }

    func toggle(_ task: ChoreTask) async {
        await perform { _ = try await self.client.setTask(task.id, done: !task.isDone) }
    }

    func addMember(_ name: String) async {
        await perform { _ = try await self.client.addMember(householdId: self.householdId, displayName: name) }
    }

    func removeMember(_ member: Member) async {
        await perform { try await self.client.removeMember(member.id) }
    }

    func toggleAdmin(_ member: Member) async {
        await perform { _ = try await self.client.setRole(memberId: member.id, role: member.role == .admin ? .member : .admin) }
    }

    func addChore(_ name: String) async {
        await perform { _ = try await self.client.createChore(householdId: self.householdId, name: name) }
    }

    func setRotation(_ chore: Chore, _ members: [MemberBrief]) async {
        await perform { _ = try await self.client.setRotation(choreId: chore.id, memberIds: members.map(\.id)) }
    }

    func setActive(_ chore: Chore, _ active: Bool) async {
        await perform { _ = try await self.client.setChoreActive(chore.id, active) }
    }

    func deleteChore(_ chore: Chore) async {
        await perform { try await self.client.deleteChore(chore.id) }
    }
}
