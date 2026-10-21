import Foundation

/// Fields to change on a chore; nil fields are left out of the request.
struct ChoreChanges: Encodable {
    var name: String?
    var isActive: Bool?
    var frequency: Frequency?
    var assignmentMode: AssignmentMode?
    var targetPerWeek: Int?  // 0 clears the target
}

extension APIClient {
    private struct CreateChoreBody: Encodable {
        let name: String
        let frequency: Frequency
        let assignmentMode: AssignmentMode
        let targetPerWeek: Int?
    }
    private struct RotationBody: Encodable { let memberIds: [UUID] }
    private struct CompleteBody: Encodable { let completedByMemberId: UUID? }
    private struct LogBody: Encodable { let memberId: UUID? }

    func chores(householdId: UUID) async throws -> [Chore] {
        try await get("/households/\(householdId)/chores")
    }

    func createChore(householdId: UUID, name: String, frequency: Frequency, mode: AssignmentMode,
                     targetPerWeek: Int?) async throws -> Chore {
        let body = CreateChoreBody(name: name, frequency: frequency, assignmentMode: mode,
                                   targetPerWeek: mode == .open ? targetPerWeek : nil)
        return try await send("POST", "/households/\(householdId)/chores", body: body)
    }

    func updateChore(_ choreId: UUID, _ changes: ChoreChanges) async throws -> Chore {
        try await send("PATCH", "/chores/\(choreId)", body: changes)
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

    // MARK: Turns

    func myTasksToday() async throws -> MyTasksToday {
        try await get("/me/tasks/today")
    }

    func householdTasksToday(householdId: UUID) async throws -> HouseholdTasksToday {
        try await get("/households/\(householdId)/tasks/today")
    }

    /// Anyone can mark a turn done; pass `completedBy` when someone else did it.
    func completeTask(_ taskId: UUID, completedBy: UUID? = nil) async throws -> ChoreTask {
        try await send("POST", "/tasks/\(taskId)/complete", body: CompleteBody(completedByMemberId: completedBy))
    }

    func reopenTask(_ taskId: UUID) async throws -> ChoreTask {
        try await send("POST", "/tasks/\(taskId)/reopen", body: Optional<String>.none)
    }

    // MARK: Open chores

    func logChore(_ choreId: UUID, memberId: UUID? = nil) async throws -> ChoreLog {
        try await send("POST", "/chores/\(choreId)/logs", body: LogBody(memberId: memberId))
    }

    func removeLog(_ logId: UUID) async throws {
        try await sendNoContent("DELETE", "/chore-logs/\(logId)")
    }

    // MARK: Activity & report

    func activity(householdId: UUID, limit: Int = 50) async throws -> [ActivityEvent] {
        try await get("/households/\(householdId)/activity?limit=\(limit)")
    }

    func report(householdId: UUID, month: String? = nil) async throws -> Report {
        try await get("/households/\(householdId)/report" + (month.map { "?month=\($0)" } ?? ""))
    }

    func reportMonths(householdId: UUID) async throws -> ReportMonths {
        try await get("/households/\(householdId)/report/months")
    }
}
