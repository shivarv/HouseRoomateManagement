import SwiftUI

/// Admins: the house's bills. Add or edit one in a form with its own Save. Mirrors web BillSettings.tsx.
@MainActor
@Observable
final class BillSettingsModel {
    let householdId: UUID
    var bills: [Bill] = []
    var error: String?
    var hasLoaded = false
    private let client = APIClient.shared

    init(householdId: UUID) {
        self.householdId = householdId
    }

    func load() async {
        defer { hasLoaded = true }
        do {
            bills = try await client.bills(householdId: householdId, includePaused: true).bills
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// Returns an error message to show in the form, or nil once saved.
    func save(_ fields: BillFields, editing bill: Bill?) async -> String? {
        do {
            if let bill { _ = try await client.updateBill(bill.id, fields) } else { _ = try await client.createBill(householdId: householdId, fields) }
            await load()
            return nil
        } catch {
            return error.localizedDescription
        }
    }

    func setActive(_ bill: Bill, _ active: Bool) async {
        await perform { _ = try await self.client.setBillActive(bill.id, active) }
    }

    func delete(_ bill: Bill) async {
        await perform { try await self.client.deleteBill(bill.id) }
    }

    private func perform(_ action: @escaping () async throws -> Void) async {
        do {
            try await action()
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        await load()
    }
}

/// One-tap starters for a new bill.
private struct Starter: Identifiable {
    let name: String
    let icon: String
    let payerMode: PayerMode
    let amountType: AmountType
    var id: String { name }
}

private let starters = [
    Starter(name: "Rent", icon: "🏠", payerMode: .everyone, amountType: .fixed),
    Starter(name: "Electricity", icon: "⚡", payerMode: .anyone, amountType: .variable),
    Starter(name: "WiFi", icon: "📶", payerMode: .anyone, amountType: .fixed),
    Starter(name: "Gas", icon: "🔥", payerMode: .anyone, amountType: .variable),
    Starter(name: "Water", icon: "💧", payerMode: .anyone, amountType: .variable),
    Starter(name: "Cleaner", icon: "🧹", payerMode: .everyone, amountType: .fixed),
]

/// What the form opens with: a bill to edit, a starter, or a blank one.
private struct FormTarget: Identifiable {
    let id = UUID()
    var bill: Bill?
    var starter: Starter?
}

struct BillSettingsSection: View {
    let model: BillSettingsModel
    let members: [Member]
    @State private var form: FormTarget?
    @State private var pendingDelete: Bill?

    var body: some View {
        Group {
            Section {
                Button("Add a bill", systemImage: "plus") { form = FormTarget() }
                let missing = starters.filter { s in !model.bills.contains { $0.name.lowercased() == s.name.lowercased() } }
                if !missing.isEmpty {
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: 6) {
                            ForEach(missing) { s in
                                Button("+ \(s.icon) \(s.name)") { form = FormTarget(starter: s) }
                                    .font(.caption)
                                    .padding(.horizontal, 10).padding(.vertical, 5)
                                    .background(Color.secondary.opacity(0.12), in: Capsule())
                                    .buttonStyle(.plain)
                            }
                        }
                    }
                }
                ErrorBanner(message: model.error)
            } footer: {
                Text("Bills show up on Reminders at the start of each month, week or day. Fixed amounts repeat on their own; amounts that change (gas, electricity) are entered on Reminders when the bill arrives.")
            }

            Section("Bills") {
                if model.bills.isEmpty && model.hasLoaded {
                    Text("No bills yet.").foregroundStyle(.secondary)
                }
                ForEach(model.bills) { bill in
                    Button { form = FormTarget(bill: bill) } label: { row(bill) }
                        .buttonStyle(.plain)
                        .swipeActions {
                            Button("Delete", role: .destructive) { pendingDelete = bill }
                            Button(bill.isActive ? "Pause" : "Resume") { Task { await model.setActive(bill, !bill.isActive) } }
                                .tint(.orange)
                        }
                }
            }
        }
        .task { if !model.hasLoaded { await model.load() } }
        .sheet(item: $form) { target in
            BillFormView(model: model, members: members, bill: target.bill, starter: target.starter)
        }
        .confirmationDialog("Delete “\(pendingDelete?.name ?? "")” and its payment history?",
                            isPresented: Binding(get: { pendingDelete != nil }, set: { if !$0 { pendingDelete = nil } }),
                            titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                if let bill = pendingDelete { Task { await model.delete(bill) } }
            }
        } message: {
            Text("Pause it instead to hide it and keep its history.")
        }
    }

    private func row(_ bill: Bill) -> some View {
        HStack(spacing: 12) {
            Text(bill.icon).font(.title3)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(bill.name).font(.headline)
                    if bill.amountType == .fixed, let cents = bill.amountCents {
                        Badge(text: Money.format(cents, bill.currency))
                    }
                    if bill.amountType == .variable { Badge(text: "Amount changes", color: .indigo) }
                    if !bill.isActive { Badge(text: "Paused", color: .orange) }
                }
                Text("\(bill.dueText) · \(bill.payerMode == .one ? "\(bill.payer?.displayName ?? "?") pays" : bill.payerMode.label)")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right").font(.caption).foregroundStyle(.tertiary)
        }
        .contentShape(Rectangle())
        .opacity(bill.isActive ? 1 : 0.6)
    }
}

/// Add or edit one bill. Nothing is saved until "Save"; closing with changes asks first.
private struct BillFormView: View {
    let model: BillSettingsModel
    let members: [Member]
    let bill: Bill?

    @Environment(\.dismiss) private var dismiss
    @State private var name: String
    @State private var icon: String
    @State private var payerMode: PayerMode
    @State private var payerId: UUID?
    @State private var frequency: BillFrequency
    @State private var dueDay: Int
    @State private var amountType: AmountType
    @State private var amount: String
    @State private var currency: String
    @State private var note: String
    @State private var error: String?
    @State private var saving = false
    @State private var confirmDiscard = false
    private let original: BillFields

    init(model: BillSettingsModel, members: [Member], bill: Bill?, starter: Starter?) {
        self.model = model
        self.members = members
        self.bill = bill
        let fields = BillFields(
            name: bill?.name ?? starter?.name ?? "",
            icon: bill?.icon ?? starter?.icon ?? "🧾",
            payerMode: bill?.payerMode ?? starter?.payerMode ?? .anyone,
            payerId: bill?.payer?.id,
            frequency: bill?.frequency ?? .monthly,
            dueDay: bill?.dueDay ?? 1,
            amountType: bill?.amountType ?? starter?.amountType ?? .fixed,
            amountCents: bill?.amountCents,
            currency: bill?.currency ?? "USD",
            note: bill?.note ?? ""
        )
        // A starter is unsaved from the start; an edit is unchanged until touched.
        original = bill == nil ? BillFields(name: "", icon: "", payerMode: .anyone, payerId: nil, frequency: .monthly, dueDay: 1, amountType: .fixed, amountCents: nil, currency: "USD", note: "") : fields
        _name = State(initialValue: fields.name)
        _icon = State(initialValue: fields.icon)
        _payerMode = State(initialValue: fields.payerMode)
        _payerId = State(initialValue: fields.payerId)
        _frequency = State(initialValue: fields.frequency)
        _dueDay = State(initialValue: fields.dueDay)
        _amountType = State(initialValue: fields.amountType)
        _amount = State(initialValue: fields.amountCents.map { String(format: "%.2f", Double($0) / 100) } ?? "")
        _currency = State(initialValue: fields.currency)
        _note = State(initialValue: fields.note)
    }

    private var fields: BillFields {
        BillFields(
            name: name.trimmingCharacters(in: .whitespaces),
            icon: icon.trimmingCharacters(in: .whitespaces).isEmpty ? "🧾" : icon.trimmingCharacters(in: .whitespaces),
            payerMode: payerMode,
            payerId: payerMode == .one ? payerId : nil,
            frequency: frequency,
            dueDay: frequency == .daily ? 1 : dueDay,
            amountType: amountType,
            amountCents: amountType == .fixed ? Money.cents(amount) : nil,
            currency: currency.trimmingCharacters(in: .whitespaces).uppercased(),
            note: note.trimmingCharacters(in: .whitespaces)
        )
    }

    private var dirty: Bool { bill == nil || !same(fields, original) }

    private var problem: String? {
        if fields.name.isEmpty { return "Give the bill a name" }
        if payerMode == .one && payerId == nil { return "Pick who pays it" }
        if amountType == .fixed && (Money.cents(amount) ?? 0) < 0 { return "Amount must be a number, like 60 or 1250.50" }
        if fields.currency.count != 3 || !fields.currency.allSatisfy(\.isLetter) { return "Currency is a 3-letter code, like USD or INR" }
        return nil
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    HStack {
                        TextField("🧾", text: $icon).frame(width: 44).multilineTextAlignment(.center)
                        TextField("Name, e.g. WiFi", text: $name)
                    }
                    TextField("Note (optional), e.g. pay on the landlord's portal", text: $note, axis: .vertical)
                }
                Section("Who pays") {
                    Picker("Who pays", selection: $payerMode) {
                        ForEach(PayerMode.allCases) { Text($0.label).tag($0) }
                    }
                    if payerMode == .one {
                        Picker("Person", selection: $payerId) {
                            Text("Pick someone").tag(UUID?.none)
                            ForEach(members) { Text($0.displayName).tag(Optional($0.id)) }
                        }
                    }
                }
                Section {
                    Picker("Repeats", selection: $frequency) {
                        ForEach(BillFrequency.allCases) { Text($0.label).tag($0) }
                    }
                    .onChange(of: frequency) { _, f in if f == .weekly && dueDay > 7 { dueDay = 1 } }
                    switch frequency {
                    case .monthly:
                        Stepper("Due on day \(dueDay)", value: $dueDay, in: 1...31)
                    case .weekly:
                        Picker("Due on", selection: $dueDay) {
                            ForEach(1...7, id: \.self) { Text(Bill.weekdays[$0 - 1]).tag($0) }
                        }
                    case .daily:
                        Text("Due the same day").foregroundStyle(.secondary)
                    }
                } header: {
                    Text("When")
                } footer: {
                    if frequency == .monthly { Text("Days 29–31 use the last day of shorter months.") }
                }
                Section("Amount") {
                    Picker("Amount", selection: $amountType) {
                        Text("Same every time").tag(AmountType.fixed)
                        Text("Changes each time").tag(AmountType.variable)
                    }
                    .pickerStyle(.segmented)
                    if amountType == .fixed {
                        TextField("Amount (optional)", text: $amount).keyboardType(.decimalPad)
                    } else {
                        Text("You'll enter it on Reminders when the bill arrives.").font(.footnote).foregroundStyle(.secondary)
                    }
                    TextField("Currency", text: $currency)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                }
                if let message = error ?? (dirty ? problem : nil) {
                    Section { ErrorBanner(message: message) }
                }
            }
            .navigationTitle(bill == nil ? "New bill" : "Edit bill")
            .navigationBarTitleDisplayMode(.inline)
            .interactiveDismissDisabled(dirty)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { if dirty { confirmDiscard = true } else { dismiss() } }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(saving ? "Saving…" : "Save") {
                        Task {
                            saving = true
                            error = await model.save(fields, editing: bill)
                            saving = false
                            if error == nil { dismiss() }
                        }
                    }
                    .disabled(saving || !dirty || problem != nil)
                }
            }
            .confirmationDialog("Discard your changes?", isPresented: $confirmDiscard, titleVisibility: .visible) {
                Button("Discard changes", role: .destructive) { dismiss() }
            }
        }
    }

    private func same(_ a: BillFields, _ b: BillFields) -> Bool {
        a.name == b.name && a.icon == b.icon && a.payerMode == b.payerMode && a.payerId == b.payerId
            && a.frequency == b.frequency && a.dueDay == b.dueDay && a.amountType == b.amountType
            && a.amountCents == b.amountCents && a.currency == b.currency && a.note == b.note
    }
}
