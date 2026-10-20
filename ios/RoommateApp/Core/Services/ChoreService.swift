import Foundation

extension APIClient {
    private struct ChoreBody: Encodable { let name: String }
    private struct ActiveBody: Encodable { let isActive: Bool }
    private struct RotationBody: Encodable { let memberIds: [UUID] }

    func chores(householdId: UUID) async throws -> [Chore] {
        try await get("/households/\(householdId)/chores")
    }

    func createChore(householdId: UUID, name: String) async throws -> Chore {
        try await send("POST", "/households/\(householdId)/chores", body: ChoreBody(name: name))
    }

    func setChoreActive(_ choreId: UUID, _ isActive: Bool) async throws -> Chore {
        try await send("PATCH", "/chores/\(choreId)", body: ActiveBody(isActive: isActive))
    }

    func setRotation(choreId: UUID, memberIds: [UUID]) async throws -> Chore {
        try await send("PUT", "/chores/\(choreId)/rotation", body: RotationBody(memberIds: memberIds))
    }

    func deleteChore(_ choreId: UUID) async throws {
        try await sendNoContent("DELETE", "/chores/\(choreId)")
    }

    func schedule(householdId: UUID, days: Int = 7) async throws -> ScheduleResponse {
        try await get("/households/\(householdId)/schedule?days=\(days)")
    }

    // MARK: Tasks

    func myTasksToday() async throws -> MyTasksToday {
        try await get("/me/tasks/today")
    }

    func householdTasksToday(householdId: UUID) async throws -> HouseholdTasksToday {
        try await get("/households/\(householdId)/tasks/today")
    }

    func setTask(_ taskId: UUID, done: Bool) async throws -> ChoreTask {
        try await send("POST", "/tasks/\(taskId)/\(done ? "complete" : "reopen")", body: Optional<String>.none)
    }
}
