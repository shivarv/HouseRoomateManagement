import Foundation
import SwiftUI
import Observation

/// 🧾 Reminders: what needs doing now, most important first — bills, then today's turns for a
/// specific person, then chores anyone can do. Mirrors web RemindersTab.tsx.
@MainActor
@Observable
final class RemindersModel {
    var households: [Household] = []
    var householdId: UUID?
    var bills: [Bill] = []
    /// Today's turns, open chores, people and the chore actions come from the house's own model.
    private(set) var house: HouseholdViewModel?
    var history: [UUID: [BillPeriod]] = [:]
    var error: String?
    /// Per-bill messages, e.g. "Bea already paid it" after losing a race.
    var notices: [UUID: String] = [:]
    var hasLoaded = false

    private let client = APIClient.shared

    /// For one house, sharing that house's own model with the screen it's on.
    init(house: HouseholdViewModel) {
        self.house = house
        self.householdId = house.householdId
    }

    var isAdmin: Bool { house?.isAdmin ?? false }
    var members: [Member] { house?.detail?.members ?? [] }
    var myMemberId: UUID? { house?.detail?.myMemberId }
    var urgentCount: Int { bills.filter { $0.current.status == .overdue || $0.current.status == .due }.count }

    /// For the Reminders tab: red with the overdue count, orange with the due-soon count, or a
    /// green tick when nothing needs paying. Nothing until the bills have loaded.
    var badge: ChipBadge? { BillsBadge.chip(for: bills, loaded: hasLoaded) }

    /// Mine first, then still to do before done.
    var tasks: [ChoreTask] {
        (house?.today ?? []).sorted {
            if $0.isDone != $1.isDone { return !$0.isDone }
            return $0.isMine && !$1.isMine
        }
    }

    func load(preferred: ([Household]) -> UUID? = { $0.first?.id }) async {
        defer { hasLoaded = true }
        do {
            households = try await client.households()
            if householdId == nil || !households.contains(where: { $0.id == householdId }) {
                householdId = preferred(households)
            }
            guard let householdId else { return }
            if house?.householdId != householdId { house = HouseholdViewModel(householdId: householdId) }
            async let list = client.bills(householdId: householdId)
            await house?.load()
            bills = try await list.bills.sorted {
                ($0.current.status.urgency, $0.position) < ($1.current.status.urgency, $1.position)
            }
            history = [:]
            error = house?.error
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Runs a bill action, then reloads. A 409 is shown on that bill, not as an error.
    private func act(on bill: Bill, _ action: @escaping () async throws -> Void) async {
        do {
            try await action()
            notices[bill.id] = nil
        } catch {
            notices[bill.id] = error.localizedDescription
        }
        let hadHistory = history[bill.id] != nil  // load() clears it
        await load()
        if hadHistory { await loadHistory(bill) }
    }

    func pay(_ bill: Bill, for member: UUID? = nil, period: BillPeriod) async {
        await act(on: bill) { _ = try await self.client.payBill(bill.id, memberId: member, period: period.period) }
    }

    func undo(_ payment: BillPayment, on bill: Bill) async {
        await act(on: bill) { try await self.client.undoBillPayment(payment.id) }
    }

    func setAmount(_ bill: Bill, cents: Int?, period: BillPeriod) async {
        await act(on: bill) { _ = try await self.client.setBillAmount(bill.id, cents: cents, period: period.period) }
    }

    /// A variable bill in one go: its amount for the period (when it changed), then who paid it.
    func payWithAmount(_ bill: Bill, cents: Int, for member: UUID? = nil, period: BillPeriod) async {
        await act(on: bill) {
            if cents != period.amountCents {
                _ = try await self.client.setBillAmount(bill.id, cents: cents, period: period.period)
            }
            _ = try await self.client.payBill(bill.id, memberId: member, period: period.period)
        }
    }

    func loadHistory(_ bill: Bill) async {
        do {
            history[bill.id] = try await client.billHistory(bill.id)
        } catch {
            notices[bill.id] = error.localizedDescription
        }
    }
}

/// How the house's bills look at a glance, for the tab badges.
enum BillsBadge {
    static func chip(for bills: [Bill], loaded: Bool) -> ChipBadge? {
        guard loaded, !bills.isEmpty else { return nil }
        let overdue = bills.filter { $0.current.status == .overdue }.count
        let due = bills.filter { $0.current.status == .due }.count
        if overdue > 0 { return ChipBadge(text: "\(overdue)", color: .red) }
        if due > 0 { return ChipBadge(text: "\(due)", color: .orange) }
        return ChipBadge(text: "✓", color: .green)
    }

    /// The House tab in the tab bar: how many bills are overdue or due soon (iOS draws it red).
    static func needingPayment(_ bills: [Bill]) -> Int {
        bills.filter { $0.current.status == .overdue || $0.current.status == .due }.count
    }
}
