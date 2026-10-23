import Foundation

// Mirrors backend/app/schemas. JSON keys are snake_case; APIClient converts them to camelCase.

struct User: Codable, Identifiable, Hashable {
    let id: UUID
    let email: String
    let name: String
    /// The house the app opens on. May be one I've since left; then fall back to my first.
    var lastHouseholdId: UUID?
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
    /// nil only on houses created before addresses were required.
    let address: String?
    let timezone: String
    let inviteCode: String
    let myMemberId: UUID
    let myRole: Role
    /// Names are unique per creator: I can't have two houses with the same name.
    let createdByMe: Bool?
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

/// A section of the house's shopping list. The house admin configures them; "other" always exists.
struct GroceryCategory: Decodable, Identifiable, Hashable {
    let id: UUID
    let key: String  // what items store; never changes
    let label: String
    let icon: String
    let position: Int
    let canDelete: Bool  // false only for "other", the fallback
}

/// A quick-add item chosen by the house admin.
struct GroceryPreset: Decodable, Identifiable, Hashable {
    let id: UUID
    let name: String
    let categoryKey: String
    let position: Int
}

/// Something people added that isn't a quick-add item yet (admin only).
struct GrocerySuggestion: Decodable, Identifiable, Hashable {
    let name: String
    let timesAdded: Int
    let categoryKey: String
    var id: String { name.lowercased() }
}

/// The house's grocery set-up, for the admin's Groceries tab.
struct GrocerySettings: Decodable {
    let categories: [GroceryCategory]
    let presets: [GroceryPreset]
    let suggestions: [GrocerySuggestion]  // most added first
}

/// Something the house needs to buy. Anyone can mark it bought.
struct ShoppingItem: Decodable, Identifiable, Hashable {
    let id: UUID
    let name: String
    let quantity: String?  // free text: "2 dozen", "1 L"
    let category: String  // a GroceryCategory.key
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
    let categories: [GroceryCategory]  // display order
    let quickAdd: [GroceryPreset]  // chosen by the admin, in order
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

// MARK: - Reminders (bills)

/// one: a named person pays · anyone: the first to pay settles it · everyone: each pays a share
enum PayerMode: String, Codable, CaseIterable, Identifiable {
    case one, anyone, everyone
    var id: Self { self }
    var label: String {
        switch self {
        case .one: "One person pays"
        case .anyone: "Anyone can pay"
        case .everyone: "Everyone pays their share"
        }
    }
}

enum BillFrequency: String, Codable, CaseIterable, Identifiable {
    case monthly, weekly, daily
    var id: Self { self }
    var label: String {
        switch self {
        case .monthly: "Every month"
        case .weekly: "Every week"
        case .daily: "Every day"
        }
    }
    var current: String {
        switch self {
        case .monthly: "This month"
        case .weekly: "This week"
        case .daily: "Today"
        }
    }
}

/// fixed: the amount repeats · variable: an admin enters each period's amount (gas, electricity)
enum AmountType: String, Codable, CaseIterable, Identifiable {
    case fixed, variable
    var id: Self { self }
}

enum BillStatus: String, Decodable {
    case paid, due, overdue, upcoming
    var label: String {
        switch self {
        case .paid: "Paid"
        case .due: "Due soon"
        case .overdue: "Overdue"
        case .upcoming: "Upcoming"
        }
    }
    /// Bills lead with the most urgent.
    var urgency: Int {
        switch self {
        case .overdue: 0
        case .due: 1
        case .upcoming: 2
        case .paid: 3
        }
    }
}

struct BillPayment: Decodable, Identifiable, Hashable {
    let id: UUID
    let member: MemberBrief  // who paid
    let recordedBy: MemberBrief?
    let paidAt: String
    let canUndo: Bool
}

/// One occurrence of a bill: this month's rent, this week's cleaner, today's milk money.
struct BillPeriod: Decodable, Hashable {
    let period: String  // start: month start, Monday, or the day
    let periodEnd: String
    let label: String  // "Oct 2026", "Week of Oct 19", "Mon, Oct 19"
    let dueDate: String
    let status: BillStatus
    let amountCents: Int?  // fixed: the bill's; variable: this period's, once set
    let shareCents: Int?  // everyone mode: each person's part
    let payments: [BillPayment]
    let paidCount: Int
    let expectedCount: Int
    let iPaid: Bool
    let isCurrent: Bool  // not a future period, so it can be paid
}

struct Bill: Decodable, Identifiable, Hashable {
    let id: UUID
    let name: String
    let icon: String
    let payerMode: PayerMode
    let payer: MemberBrief?
    let frequency: BillFrequency
    let dueDay: Int  // monthly: day of the month · weekly: 1 = Mon … 7 = Sun · daily: unused
    let amountType: AmountType
    let amountCents: Int?  // fixed bills
    let lastAmountCents: Int?  // variable bills: the latest amount before this period
    let currency: String
    let note: String?
    let position: Int
    let isActive: Bool
    let current: BillPeriod

    static let weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    /// Stored as 31; the backend uses each month's own last day.
    static let lastDay = 31

    var dueText: String {
        switch frequency {
        case .daily: "Every day"
        case .weekly: "Every \(Self.weekdays[max(0, min(6, dueDay - 1))])"
        case .monthly: dueDay > 28 ? "Monthly on the last day" : "Monthly on day \(dueDay)"
        }
    }
}

struct BillList: Decodable {
    let today: String
    let bills: [Bill]
}

enum Money {
    /// 125050 + "USD" → "$1,250.50". Money is always integer cents.
    static func format(_ cents: Int, _ currency: String) -> String {
        (Decimal(cents) / 100).formatted(.currency(code: currency))
    }

    /// "1,250.50" → 125050. Empty → nil. Not a number → -1.
    static func cents(_ text: String) -> Int? {
        let cleaned = text.replacingOccurrences(of: ",", with: "").trimmingCharacters(in: .whitespaces)
        guard !cleaned.isEmpty else { return nil }
        guard let value = Double(cleaned), value >= 0 else { return -1 }
        return Int((value * 100).rounded())
    }
}

// MARK: - Guided set-up of a new house

struct SetupChore: Codable, Hashable {
    var name: String
    var frequency: Frequency
    var assignmentMode: AssignmentMode
    var people: [String]? = nil  // who takes turns, by name; nil = everyone
}

struct SetupGrocery: Codable, Hashable {
    var name: String
    var categoryKey: String
}

struct SetupBill: Codable, Hashable {
    var name: String
    var icon: String
    var payerMode: PayerMode
    var payerName: String?  // payerMode .one: me or a roommate, by name
    var frequency: BillFrequency
    var dueDay: Int
    var amountType: AmountType
    var amountCents: Int?
}

struct SetupCategory: Decodable, Hashable, Identifiable {
    let key: String
    let label: String
    let icon: String
    var id: String { key }
}

/// Defaults to prefill the set-up with, up to `maxItems` of each.
struct SetupTemplate: Decodable {
    let maxItems: Int
    let chores: [SetupChore]
    let groceries: [SetupGrocery]
    let bills: [SetupBill]
    let categories: [SetupCategory]
}

/// Everything a new house starts with, created in one go.
struct HouseholdSetup: Encodable {
    let name: String
    let address: String
    let timezone: String
    let roommates: [String]  // besides me
    let chores: [SetupChore]
    let groceries: [SetupGrocery]
    let bills: [SetupBill]
    let currency: String
}
