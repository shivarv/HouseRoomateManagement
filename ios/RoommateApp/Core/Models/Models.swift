import Foundation

// Mirrors backend/app/schemas. JSON keys are snake_case; APIClient converts them to camelCase.

struct User: Codable, Identifiable, Hashable {
    let id: UUID
    let email: String
    let name: String
}

struct TokenResponse: Decodable {
    let accessToken: String
    let user: User
}

enum Role: String, Codable {
    case admin, member
}

struct MemberBrief: Codable, Identifiable, Hashable {
    let id: UUID
    let displayName: String
}

struct Member: Codable, Identifiable, Hashable {
    let id: UUID
    let displayName: String
    let role: Role
    let isActive: Bool
    let hasAccount: Bool

    var brief: MemberBrief { MemberBrief(id: id, displayName: displayName) }
}

struct Household: Codable, Identifiable, Hashable {
    let id: UUID
    let name: String
    let timezone: String
    let inviteCode: String
    let myMemberId: UUID
    let myRole: Role
}

struct HouseholdDetail: Decodable {
    let id: UUID
    let name: String
    let timezone: String
    let inviteCode: String
    let myMemberId: UUID
    let myRole: Role
    let members: [Member]

    var isAdmin: Bool { myRole == .admin }
}

struct InvitePreview: Decodable {
    let householdId: UUID
    let householdName: String
    let unclaimedMembers: [MemberBrief]
}

enum Frequency: String, Codable, CaseIterable, Identifiable {
    case daily, weekly
    var id: Self { self }
    var label: String { self == .daily ? "Every day" : "Once a week (any day)" }
}

enum AssignmentMode: String, Codable, CaseIterable, Identifiable {
    case rotation, open
    var id: Self { self }
    var label: String { self == .rotation ? "Take turns (rotation)" : "Anyone — whoever does it logs it" }
}

struct Chore: Decodable, Identifiable, Hashable {
    let id: UUID
    let name: String
    let frequency: Frequency
    let assignmentMode: AssignmentMode
    let targetPerWeek: Int?
    let isActive: Bool
    let rotation: [MemberBrief]
    let todayAssignee: MemberBrief?  // whose turn it is this period

    var isOpen: Bool { assignmentMode == .open }
}

struct ChoreBrief: Codable, Hashable {
    let id: UUID
    let name: String
    let frequency: Frequency
    let assignmentMode: AssignmentMode
}

enum TaskStatus: String, Codable {
    case pending, done
}

struct ChoreTask: Decodable, Identifiable, Hashable {
    let id: UUID
    let householdId: UUID
    let householdName: String
    let chore: ChoreBrief
    let member: MemberBrief  // whose turn it is
    let dueDate: String  // period start, YYYY-MM-DD in the household's timezone
    let periodEnd: String  // same day (daily) or Sunday (weekly)
    let status: TaskStatus
    let completedAt: String?
    let completedBy: MemberBrief?
    let nextAssignee: MemberBrief?
    let isMine: Bool

    var isDone: Bool { status == .done }
    var isWeekly: Bool { chore.frequency == .weekly }
    var wasCovered: Bool { isDone && completedBy != nil && completedBy?.id != member.id }
}

struct ChoreLog: Decodable, Identifiable, Hashable {
    let id: UUID
    let member: MemberBrief
    let loggedBy: MemberBrief?
    let doneOn: String
    let createdAt: String
}

/// A chore nobody is assigned to: whoever does it logs it.
struct OpenChore: Decodable, Identifiable, Hashable {
    let householdId: UUID
    let householdName: String
    let chore: ChoreBrief
    let targetPerWeek: Int?
    let todayLogs: [ChoreLog]
    let thisWeekCount: Int
    let lastDone: ChoreLog?
    let people: [OpenChoreCount]  // everyone, fewest this year first
    let suggested: MemberBrief?  // first in `people` — a hint, not an assignment
    let suggestedReason: String?

    var id: UUID { chore.id }
}

struct OpenChoreCount: Decodable, Identifiable, Hashable {
    let member: MemberBrief
    let thisYear: Int
    let thisMonth: Int
    let lastDone: String?

    var id: UUID { member.id }
}

struct HouseholdTasksToday: Decodable {
    let date: String
    let tasks: [ChoreTask]
    let open: [OpenChore]
}

struct MyTasksToday: Decodable {
    let tasks: [ChoreTask]
    let overdue: [ChoreTask]
    let open: [OpenChore]
}

struct ScheduleSlot: Decodable, Hashable {
    let chore: ChoreBrief
    let member: MemberBrief
    let status: TaskStatus?
}

struct ScheduleDay: Decodable, Identifiable {
    let date: String
    let slots: [ScheduleSlot]

    var id: String { date }
}

struct ScheduleResponse: Decodable {
    let days: [ScheduleDay]
}

struct ActivityEvent: Decodable, Identifiable, Hashable {
    let id: UUID
    let action: String
    let createdAt: String
    let actor: MemberBrief?
    let subject: MemberBrief?
    let assignee: MemberBrief?
    let choreId: UUID?
    let choreName: String?
    let dueDate: String?
    let detail: String?
}

struct ReportRow: Decodable, Identifiable, Hashable {
    let member: MemberBrief
    let isActive: Bool
    let done: Int
    let share: Double
    let turns: Int?
    let missed: Int?
    let coveredByOthers: Int?
    let coveredForOthers: Int?
    let lastDone: String?

    var id: UUID { member.id }
}

struct ChoreReport: Decodable, Identifiable, Hashable {
    let chore: ChoreBrief
    let isActive: Bool
    let totalDone: Int
    let totalMissed: Int?
    let rows: [ReportRow]

    var id: UUID { chore.id }
}

struct LeaderboardRow: Decodable, Identifiable, Hashable {
    let member: MemberBrief
    let isActive: Bool
    let done: Int
    let missed: Int
    let coveredForOthers: Int

    var id: UUID { member.id }
}

struct Report: Decodable {
    let month: String
    let start: String
    let end: String
    let isCurrent: Bool
    let fairShare: Double
    let chores: [ChoreReport]
    let leaderboard: [LeaderboardRow]
}

struct ReportMonths: Decodable {
    let months: [String]
}
