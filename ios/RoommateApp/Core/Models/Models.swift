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
    let swap: TaskSwap?  // this turn changed hands through a swap
    let swapRequestId: UUID?  // an open "Ask for a swap" on this turn

    var isDone: Bool { status == .done }
    var isWeekly: Bool { chore.frequency == .weekly }
    var wasCovered: Bool { isDone && completedBy != nil && completedBy?.id != member.id }
}

/// How a turn changed hands through a swap.
struct TaskSwap: Decodable, Hashable {
    enum Role: String, Decodable { case given, payback }

    let id: UUID
    let role: Role  // given: took it over from `other`; payback: paying `other` back
    let other: MemberBrief
    let canCancel: Bool
}

enum SwapStatus: String, Decodable {
    case open, accepted, cancelled, expired
}

/// "Ask for a swap": someone offers one of their turns; the first person to accept takes it
/// and gives back their own next turn of the same chore.
struct Swap: Decodable, Identifiable, Hashable {
    let id: UUID
    let householdId: UUID
    let householdName: String
    let chore: ChoreBrief
    let givenDate: String  // the turn being given away (period start)
    let periodEnd: String
    let requester: MemberBrief
    let acceptor: MemberBrief?
    let paybackDate: String?  // once accepted: the acceptor's turn the requester now does
    let status: SwapStatus
    let note: String?
    let createdAt: String
    let isMine: Bool  // I asked
    let canAccept: Bool
    let paybackPreview: String?  // the turn I'd give back if I took it
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
    let swappedWith: MemberBrief?  // set when this turn changed hands through a swap
}

struct ScheduleDay: Decodable, Identifiable {
    let date: String
    let slots: [ScheduleSlot]

    var id: String { date }
}

struct ScheduleResponse: Decodable {
    let days: [ScheduleDay]
}

enum ShoppingCategory: String, Codable, CaseIterable, Identifiable {
    case groceries, toiletries, cleaning, household, other
    var id: Self { self }

    var label: String { rawValue.capitalized }
    var icon: String {
        switch self {
        case .groceries: "🥚"
        case .toiletries: "🧴"
        case .cleaning: "🧼"
        case .household: "🧻"
        case .other: "🛍️"
        }
    }
}

/// Something the house needs to buy. Anyone can mark it bought.
struct ShoppingItem: Decodable, Identifiable, Hashable {
    let id: UUID
    let name: String
    let quantity: String?  // free text: "2 dozen", "1 L"
    let category: ShoppingCategory
    let note: String?
    let status: String  // needed | bought
    let addedBy: MemberBrief?
    let boughtBy: MemberBrief?
    let boughtAt: String?
    let createdAt: String
    let canUndo: Bool  // bought, and I bought it or added it
}

struct ShoppingList: Decodable {
    let needed: [ShoppingItem]  // oldest first
    let recentlyBought: [ShoppingItem]  // last 14 days, newest first
    let suggestions: [String]  // bought before, not on the list now
}

enum HelpStatus: String, Decodable {
    case open, done
}

/// Someone asks the house for a hand; anyone in the house can mark it done.
struct HelpRequest: Decodable, Identifiable, Hashable {
    let id: UUID
    let householdId: UUID
    let householdName: String
    let requester: MemberBrief
    let title: String  // a preset or the person's own words
    let details: String?
    let status: HelpStatus
    let doneBy: MemberBrief?
    let doneAt: String?
    let createdAt: String
    let updatedAt: String
    let isMine: Bool  // I asked: I can edit or withdraw it while it's open
    let canReopen: Bool  // I asked, or I marked it done

    var isDone: Bool { status == .done }
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
