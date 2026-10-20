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

struct Chore: Decodable, Identifiable, Hashable {
    let id: UUID
    let name: String
    let frequency: String
    let isActive: Bool
    let rotation: [MemberBrief]
    let todayAssignee: MemberBrief?
}

struct ChoreBrief: Codable, Hashable {
    let id: UUID
    let name: String
}

enum TaskStatus: String, Codable {
    case pending, done
}

struct ChoreTask: Decodable, Identifiable, Hashable {
    let id: UUID
    let householdId: UUID
    let householdName: String
    let chore: ChoreBrief
    let member: MemberBrief
    let dueDate: String  // YYYY-MM-DD in the household's timezone
    let status: TaskStatus
    let completedAt: String?
    let nextAssignee: MemberBrief?
    let isMine: Bool

    var isDone: Bool { status == .done }
}

struct HouseholdTasksToday: Decodable {
    let date: String
    let tasks: [ChoreTask]
}

struct MyTasksToday: Decodable {
    let tasks: [ChoreTask]
    let overdue: [ChoreTask]
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
