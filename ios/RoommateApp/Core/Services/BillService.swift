import Foundation

/// The fields of a bill, as the admin's form sends them. Every key is sent, so nil clears it.
struct BillFields: Encodable {
    var name: String
    var icon: String
    var payerMode: PayerMode
    var payerId: UUID?
    var frequency: BillFrequency
    var dueDay: Int
    var amountType: AmountType
    var amountCents: Int?
    var currency: String
    var note: String

    private enum CodingKeys: String, CodingKey {
        case name, icon, payerMode, payerId, frequency, dueDay, amountType, amountCents, currency, note
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(name, forKey: .name)
        try c.encode(icon, forKey: .icon)
        try c.encode(payerMode, forKey: .payerMode)
        try c.encode(payerId, forKey: .payerId)  // null when nobody's named
        try c.encode(frequency, forKey: .frequency)
        try c.encode(dueDay, forKey: .dueDay)
        try c.encode(amountType, forKey: .amountType)
        try c.encode(amountCents, forKey: .amountCents)  // null clears it
        try c.encode(currency, forKey: .currency)
        try c.encode(note, forKey: .note)
    }
}

extension APIClient {
    private struct ActiveBody: Encodable { let isActive: Bool }
    private struct PayBody: Encodable { let memberId: UUID?; let period: String? }
    private struct AmountBody: Encodable {
        let amountCents: Int?
        let period: String?
        func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(amountCents, forKey: .amountCents)  // null clears it
            try c.encodeIfPresent(period, forKey: .period)
        }
        private enum CodingKeys: String, CodingKey { case amountCents, period }
    }

    /// Each bill with its current period (this month, this week or today).
    func bills(householdId: UUID, includePaused: Bool = false) async throws -> BillList {
        try await get("/households/\(householdId)/bills\(includePaused ? "?include_paused=true" : "")")
    }

    /// The periods before the current one, newest first.
    func billHistory(_ id: UUID, limit: Int = 6) async throws -> [BillPeriod] {
        try await get("/bills/\(id)/history?limit=\(limit)")
    }

    func createBill(householdId: UUID, _ fields: BillFields) async throws -> Bill {
        try await send("POST", "/households/\(householdId)/bills", body: fields)
    }

    func updateBill(_ id: UUID, _ fields: BillFields) async throws -> Bill {
        try await send("PATCH", "/bills/\(id)", body: fields)
    }

    func setBillActive(_ id: UUID, _ isActive: Bool) async throws -> Bill {
        try await send("PATCH", "/bills/\(id)", body: ActiveBody(isActive: isActive))
    }

    func deleteBill(_ id: UUID) async throws {
        try await sendNoContent("DELETE", "/bills/\(id)")
    }

    /// Admins: a variable bill's amount for one period (default: the current one).
    func setBillAmount(_ id: UUID, cents: Int?, period: String? = nil) async throws -> Bill {
        try await send("PUT", "/bills/\(id)/amount", body: AmountBody(amountCents: cents, period: period))
    }

    /// Anyone in the house, for themselves (nil) or someone else. Already paid → 409 saying who.
    func payBill(_ id: UUID, memberId: UUID? = nil, period: String? = nil) async throws -> BillPayment {
        try await send("POST", "/bills/\(id)/pay", body: PayBody(memberId: memberId, period: period))
    }

    func undoBillPayment(_ id: UUID) async throws {
        try await sendNoContent("DELETE", "/bill-payments/\(id)")
    }
}
