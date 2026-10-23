import SwiftUI

/// 🧾 Reminders: bills (loud when due), then today's turns, then chores anyone can do.
/// Everything is for the current day, week or month, so yesterday's reminders give way to today's.
struct RemindersView: View {
    @State private var model = RemindersModel()
    @Environment(\.scenePhase) private var scenePhase
    @Environment(Session.self) private var session

    var body: some View {
        NavigationStack {
            List {
                if model.households.count > 1 {
                    Picker("House", selection: $model.householdId) {
                        ForEach(model.households) { Text($0.name).tag(Optional($0.id)) }
                    }
                    .onChange(of: model.householdId) { _, id in
                        if let id { session.rememberHousehold(id) }
                        Task { await model.load() }
                    }
                }
                ErrorBanner(message: model.error)

                if model.hasLoaded && model.households.isEmpty {
                    Text("Join a household first.").foregroundStyle(.secondary)
                } else {
                    billsSection
                    turnsSection
                    openSection
                }
            }
            .navigationTitle("Reminders")
            .refreshable { await model.load() }
            .task { await model.load(preferred: session.preferredHousehold) }
            .onChange(of: scenePhase) { _, phase in
                if phase == .active { Task { await model.load() } }
            }
            .overlay { if !model.hasLoaded { ProgressView() } }
        }
    }

    private var billsSection: some View {
        Section {
            if model.bills.isEmpty && model.hasLoaded {
                Text(model.isAdmin ? "No bills yet. Add them in the house's Bills tab." : "No bills yet.")
                    .foregroundStyle(.secondary)
            }
            ForEach(model.bills) { BillReminderRow(model: model, bill: $0) }
        } header: {
            GroupHeader(icon: "💸", title: "Bills",
                        count: model.urgentCount > 0 ? "\(model.urgentCount) to pay" : "\(model.bills.count)",
                        loud: model.urgentCount > 0)
        }
    }

    @ViewBuilder private var turnsSection: some View {
        if let house = model.house {
            Section {
                if model.tasks.isEmpty && model.hasLoaded {
                    Text("Nobody has a turn today.").foregroundStyle(.secondary)
                }
                ForEach(model.tasks) { task in
                    TaskRow(
                        task: task, members: house.members, myMemberId: model.myMemberId,
                        onDone: { who in Task { await house.complete(task, by: who); await model.load() } },
                        onUndo: { Task { await house.reopen(task); await model.load() } },
                        onAskSwap: { note in Task { await house.askForSwap(task, note: note); await model.load() } },
                        onCancelSwap: { id in Task { await house.cancelSwap(id); await model.load() } }
                    )
                }
            } header: {
                GroupHeader(icon: "👤", title: "Turns today",
                            count: "\(model.tasks.filter { !$0.isDone }.count) to do")
            }
        }
    }

    @ViewBuilder private var openSection: some View {
        if let house = model.house {
            Section {
                if house.open.isEmpty && model.hasLoaded {
                    Text("No open chores.").foregroundStyle(.secondary)
                }
                ForEach(house.open) { item in
                    OpenChoreRow(
                        item: item, myMemberId: model.myMemberId, today: house.todayDate,
                        onLog: { who in Task { await house.log(item, by: who); await model.load() } },
                        onRemove: { log in Task { await house.removeLog(log); await model.load() } }
                    )
                }
            } header: {
                GroupHeader(icon: "🙌", title: "Anyone can do", count: "\(house.open.count)")
            }
        }
    }
}

private struct GroupHeader: View {
    let icon: String
    let title: String
    let count: String
    var loud = false

    var body: some View {
        HStack(spacing: 6) {
            Text(icon)
            Text(title).font(.subheadline.weight(.bold))
            Text(count)
                .font(.caption.weight(.semibold))
                .padding(.horizontal, 7).padding(.vertical, 2)
                .background(loud ? Color.red : Color.secondary.opacity(0.15), in: Capsule())
                .foregroundStyle(loud ? Color.white : Color.secondary)
        }
        .textCase(nil)
    }
}

// MARK: - A bill

private struct BillReminderRow: View {
    let model: RemindersModel
    let bill: Bill
    @State private var showHistory = false

    private var period: BillPeriod { bill.current }
    private var urgent: Bool { period.status == .overdue || period.status == .due }
    private var tint: Color { period.status == .overdue ? .red : period.status == .due ? .orange : .clear }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 12) {
                Text(bill.icon)
                    .font(.title2)
                    .frame(width: 46, height: 46)
                    .background((urgent ? tint : Color.accentColor).opacity(0.15), in: RoundedRectangle(cornerRadius: 12))
                    .overlay(alignment: .topTrailing) {
                        if urgent { Circle().fill(.red).frame(width: 10, height: 10).offset(x: 3, y: -3) }
                    }
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        Text(bill.name).font(.headline)
                        StatusCapsule(status: period.status)
                    }
                    Text(amountLine(bill, period) ?? (bill.amountType == .variable ? "Amount not set yet" : ""))
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(amountLine(bill, period) == nil ? .orange : .primary)
                    Text("\(bill.frequency.current) (\(period.label)) · due \(DayFormat.short(period.dueDate)) · \(payerLine)")
                        .font(.caption).foregroundStyle(.secondary)
                    if let note = bill.note { Text(note).font(.caption).foregroundStyle(.secondary) }
                }
            }

            PeriodActions(model: model, bill: bill, period: period)

            if model.isAdmin && bill.amountType == .variable {
                AmountField(model: model, bill: bill, period: period, hint: bill.lastAmountCents)
            }
            if let notice = model.notices[bill.id] {
                Text(notice).font(.footnote).foregroundStyle(.secondary)
            }

            DisclosureGroup("History", isExpanded: $showHistory) {
                if let past = model.history[bill.id] {
                    ForEach(past, id: \.period) { p in
                        VStack(alignment: .leading, spacing: 6) {
                            HStack {
                                Text(p.label).font(.subheadline.weight(.medium))
                                StatusCapsule(status: p.status)
                                Spacer()
                                if let amount = amountLine(bill, p) { Text(amount).font(.caption).foregroundStyle(.secondary) }
                            }
                            if p.status != .paid { PeriodActions(model: model, bill: bill, period: p) }
                            if model.isAdmin && bill.amountType == .variable && p.amountCents == nil {
                                AmountField(model: model, bill: bill, period: p, hint: nil)
                            }
                        }
                        .padding(.vertical, 4)
                    }
                } else {
                    ProgressView()
                }
            }
            .font(.caption)
            .onChange(of: showHistory) { _, open in
                if open && model.history[bill.id] == nil { Task { await model.loadHistory(bill) } }
            }
        }
        .padding(.vertical, 6)
        // Bills on due are the loudest thing on the screen.
        .listRowBackground(
            HStack(spacing: 0) {
                Rectangle().fill(tint).frame(width: urgent ? 5 : 0)
                (urgent ? tint.opacity(0.08) : Color(.secondarySystemGroupedBackground))
            }
        )
        .opacity(period.status == .paid ? 0.75 : 1)
    }

    private var payerLine: String {
        switch bill.payerMode {
        case .one: "\(bill.payer?.displayName ?? "Someone") pays"
        case .anyone: "anyone can pay"
        case .everyone: "everyone pays · \(period.paidCount) of \(period.expectedCount)"
        }
    }
}

private func amountLine(_ bill: Bill, _ period: BillPeriod) -> String? {
    guard let amount = period.amountCents else { return nil }
    let total = Money.format(amount, bill.currency)
    if bill.payerMode == .everyone, let share = period.shareCents {
        return "\(total) · \(Money.format(share, bill.currency)) each"
    }
    return total
}

private struct StatusCapsule: View {
    let status: BillStatus

    var body: some View {
        Text(status.label)
            .font(.caption2.weight(.bold))
            .padding(.horizontal, 7).padding(.vertical, 2)
            .background(background, in: Capsule())
            .foregroundStyle(status == .overdue || status == .due ? Color.white : color)
    }

    private var color: Color { status == .paid ? .green : .secondary }
    private var background: Color {
        switch status {
        case .overdue: .red
        case .due: .orange
        case .paid: .green.opacity(0.15)
        case .upcoming: .secondary.opacity(0.15)
        }
    }
}

/// Paying for one period: one button (one person / anyone), or a chip per person (everyone).
private struct PeriodActions: View {
    let model: RemindersModel
    let bill: Bill
    let period: BillPeriod

    var body: some View {
        if bill.payerMode == .everyone {
            VStack(alignment: .leading, spacing: 6) {
                ProgressView(value: Double(period.paidCount), total: Double(max(1, period.expectedCount)))
                    .tint(.green)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 6) {
                        ForEach(people) { member in chip(member) }
                    }
                }
            }
        } else if let first = period.payments.first {
            HStack {
                Label("\(first.member.id == model.myMemberId ? "You" : first.member.displayName) paid · \(DayFormat.time(first.paidAt))",
                      systemImage: "checkmark.circle.fill")
                    .font(.subheadline).foregroundStyle(.green)
                Spacer()
                if first.canUndo {
                    Button("Undo") { Task { await model.undo(first, on: bill) } }
                        .buttonStyle(.bordered).tint(.gray)
                }
            }
        } else if bill.payerMode == .one, let payer = bill.payer, payer.id != model.myMemberId {
            Button("\(payer.displayName) paid ✓") { Task { await model.pay(bill, for: payer.id, period: period) } }
                .buttonStyle(.bordered)
                .disabled(!period.isCurrent)
        } else {
            Button("I paid it ✓") { Task { await model.pay(bill, period: period) } }
                .buttonStyle(.borderedProminent)
                .disabled(!period.isCurrent)
        }
    }

    /// Me first.
    private var people: [Member] {
        model.members.sorted { ($0.id == model.myMemberId ? 0 : 1) < ($1.id == model.myMemberId ? 0 : 1) }
    }

    private func chip(_ member: Member) -> some View {
        let payment = period.payments.first { $0.member.id == member.id }
        let mine = member.id == model.myMemberId
        return Button {
            Task {
                if let payment { await model.undo(payment, on: bill) } else { await model.pay(bill, for: mine ? nil : member.id, period: period) }
            }
        } label: {
            Text((payment != nil ? "✓ " : "") + (mine ? "You" : member.displayName))
                .font(.caption.weight(.medium))
                .padding(.horizontal, 10).padding(.vertical, 5)
                .background(payment != nil ? Color.green.opacity(0.15) : Color.secondary.opacity(0.1), in: Capsule())
                .foregroundStyle(payment != nil ? Color.green : mine ? Color.accentColor : Color.primary)
        }
        .buttonStyle(.plain)
        .disabled(!period.isCurrent || (payment.map { !$0.canUndo } ?? false))
    }
}

/// Admins: enter a variable bill's amount for a period when it arrives.
private struct AmountField: View {
    let model: RemindersModel
    let bill: Bill
    let period: BillPeriod
    let hint: Int?
    @State private var text = ""

    var body: some View {
        HStack {
            TextField(hint.map { "Last time \(Money.format($0, bill.currency))" } ?? "\(period.label) amount", text: $text)
                .keyboardType(.decimalPad)
                .textFieldStyle(.roundedBorder)
            Button("Save amount") {
                let cents = Money.cents(text)
                Task { await model.setAmount(bill, cents: cents, period: period) }
            }
            .buttonStyle(.bordered)
            .disabled((Money.cents(text) ?? 0) < 0 || Money.cents(text) == period.amountCents)
        }
        .onAppear {
            if let amount = period.amountCents { text = String(format: "%.2f", Double(amount) / 100) }
        }
    }
}
