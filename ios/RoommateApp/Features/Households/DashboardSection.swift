import Charts
import SwiftUI

/// 📈 Dashboard: the house at a glance this month — chores, fairness, bills, groceries, favours.
/// Mirrors web DashboardTab.tsx. Indigo is chores done; amber is missed, always labelled with its number.
@MainActor
@Observable
final class DashboardModel {
    let householdId: UUID
    var report: Report?
    var bills: [Bill] = []
    var groceriesNeeded = 0
    var favours: [HelpRequest] = []
    var trend: [(month: String, done: Int)] = []
    var error: String?
    var hasLoaded = false

    init(householdId: UUID) { self.householdId = householdId }

    func load() async {
        defer { hasLoaded = true }
        let client = APIClient.shared
        do {
            async let report = client.report(householdId: householdId)
            async let bills = client.bills(householdId: householdId)
            async let shopping = client.shoppingList(householdId: householdId)
            async let help = client.helpRequests()
            self.report = try await report
            self.bills = try await bills.bills.filter(\.isActive)
            self.groceriesNeeded = try await shopping.needed.count
            self.favours = try await help.filter { $0.householdId == householdId }
            error = nil
        } catch {
            self.error = error.localizedDescription
        }
        await loadTrend()
    }

    /// Chores done in each of the last six months that have a report.
    private func loadTrend() async {
        let months = ((try? await APIClient.shared.reportMonths(householdId: householdId).months) ?? []).sorted().suffix(6)
        var points: [(month: String, done: Int)] = []
        for m in months {
            if let r = try? await APIClient.shared.report(householdId: householdId, month: m) {
                points.append((m, r.leaderboard.reduce(0) { $0 + $1.done }))
            }
        }
        trend = points
    }
}

struct DashboardSection: View {
    @State private var model: DashboardModel

    private static let done = Color(red: 0x63 / 255, green: 0x66 / 255, blue: 0xf1 / 255)  // #6366f1
    private static let missed = Color(red: 0xf5 / 255, green: 0x9e / 255, blue: 0x0b / 255)  // #f59e0b

    init(householdId: UUID) {
        _model = State(initialValue: DashboardModel(householdId: householdId))
    }

    var body: some View {
        Group {
            if let r = model.report {
                tiles(r)
                Section {
                    personChart(r)
                } header: {
                    Text("Chores by person")
                } footer: {
                    Text("This month · the line is the fair share (≈ \(Self.share(r.fairShare)) each).")
                }
                Section {
                    choreChart(r)
                } header: {
                    Text("Chores by type")
                } footer: {
                    Text("Done and missed this month.")
                }
                Section("Last 6 months") { trendChart }
                Section("Bills") { billRows }
            } else if let error = model.error {
                ErrorBanner(message: error)
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .task { if !model.hasLoaded { await model.load() } }
    }

    // MARK: Tiles

    private func tiles(_ r: Report) -> some View {
        let totalDone = r.leaderboard.reduce(0) { $0 + $1.done }
        let totalMissed = r.leaderboard.reduce(0) { $0 + $1.missed }
        let active = r.leaderboard.filter(\.isActive)
        let spread = (active.map(\.done).max() ?? 0) - (active.map(\.done).min() ?? 0)
        let monthly = model.bills.filter { $0.frequency == .monthly }
        let paid = monthly.filter { $0.current.status == .paid }.count
        let nextDue = model.bills.filter { $0.current.status != .paid }.min { $0.current.dueDate < $1.current.dueDate }
        let open = model.favours.filter { !$0.isDone }.count
        let doneThisMonth = model.favours.filter { $0.isDone && ($0.doneAt?.hasPrefix(r.month) ?? false) }.count

        return Section {
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)], spacing: 10) {
                tile("Chores done", "\(totalDone)", totalMissed > 0 ? "\(totalMissed) missed" : "none missed 🎉")
                tile("Fairness", active.count < 2 ? "—" : spread <= 2 ? "Even" : "±\(spread)",
                     active.count < 2 ? "needs 2+ people" : spread <= 2 ? "within \(spread) chore\(spread == 1 ? "" : "s")" : "gap between most & least")
                tile("Bills this month", monthly.isEmpty ? "—" : "\(paid)/\(monthly.count)",
                     nextDue.map { "next: \($0.name), \(DayFormat.short($0.current.dueDate))" } ?? (monthly.isEmpty ? "no monthly bills" : "all paid ✓"))
                tile("Groceries needed", "\(model.groceriesNeeded)", model.groceriesNeeded > 0 ? "on the list now" : "list is empty")
                tile("Favours", "\(open)", "open · \(doneThisMonth) done this month")
            }
            .padding(.vertical, 4)
        }
        .listRowBackground(Color.clear)
        .listRowInsets(EdgeInsets())
    }

    private func tile(_ label: String, _ value: String, _ sub: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased()).font(.caption2.weight(.semibold)).foregroundStyle(.secondary)
            Text(value).font(.title2.bold()).monospacedDigit()
            Text(sub).font(.caption).foregroundStyle(.secondary).lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(.secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 14))
    }

    // MARK: Charts

    private func personChart(_ r: Report) -> some View {
        let rows = r.leaderboard.filter(\.isActive).sorted { $0.done > $1.done }
        return Group {
            if rows.isEmpty {
                Text("Nothing yet this month.").foregroundStyle(.secondary)
            } else {
                Chart {
                    ForEach(rows) { row in
                        BarMark(x: .value("Done", row.done), y: .value("Person", row.member.displayName), width: .fixed(14))
                            .foregroundStyle(Self.done)
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                            .annotation(position: .trailing) {
                                Text("\(row.done)").font(.caption).foregroundStyle(.secondary)
                            }
                    }
                    RuleMark(x: .value("Fair share", r.fairShare))
                        .foregroundStyle(.gray)
                        .lineStyle(StrokeStyle(lineWidth: 2))
                }
                .chartXAxis(.hidden)
                .frame(height: CGFloat(rows.count) * 30 + 10)
                .padding(.vertical, 4)
            }
        }
    }

    private func choreChart(_ r: Report) -> some View {
        let rows = r.chores.filter(\.isActive)
        return Group {
            if rows.isEmpty {
                Text("Nothing yet this month.").foregroundStyle(.secondary)
            } else {
                Chart {
                    ForEach(rows) { c in
                        BarMark(x: .value("Count", c.totalDone), y: .value("Chore", c.chore.name), width: .fixed(14))
                            .foregroundStyle(by: .value("Status", "Done"))
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                        if let missed = c.totalMissed, missed > 0 {
                            BarMark(x: .value("Count", missed), y: .value("Chore", c.chore.name), width: .fixed(14))
                                .foregroundStyle(by: .value("Status", "Missed"))
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                                .annotation(position: .trailing) {
                                    Text("+\(missed) missed").font(.caption).foregroundStyle(.orange)
                                }
                        }
                    }
                }
                .chartForegroundStyleScale(["Done": Self.done, "Missed": Self.missed])
                .chartLegend(position: .top, alignment: .leading)
                .chartXAxis(.hidden)
                .frame(height: CGFloat(rows.count) * 30 + 40)
                .padding(.vertical, 4)
            }
        }
    }

    @ViewBuilder
    private var trendChart: some View {
        if model.trend.count < 2 {
            Text(model.hasLoaded ? "Come back next month to see a trend." : "Loading…").foregroundStyle(.secondary)
        } else {
            Chart {
                ForEach(model.trend, id: \.month) { p in
                    LineMark(x: .value("Month", Self.monthLabel(p.month)), y: .value("Done", p.done))
                        .foregroundStyle(Self.done)
                        .lineStyle(StrokeStyle(lineWidth: 2))
                    PointMark(x: .value("Month", Self.monthLabel(p.month)), y: .value("Done", p.done))
                        .foregroundStyle(Self.done)
                        .symbolSize(60)
                }
            }
            .chartYAxis { AxisMarks(position: .leading) { _ in AxisGridLine().foregroundStyle(.gray.opacity(0.2)); AxisValueLabel() } }
            .frame(height: 140)
            .padding(.vertical, 4)
        }
    }

    // MARK: Bills

    @ViewBuilder
    private var billRows: some View {
        if model.bills.isEmpty {
            Text("No bills set up yet.").foregroundStyle(.secondary)
        }
        ForEach(model.bills) { b in
            HStack(spacing: 10) {
                Text(b.icon).font(.title3)
                VStack(alignment: .leading, spacing: 1) {
                    Text(b.name).font(.subheadline.weight(.medium))
                    Text("\(b.current.label) · due \(DayFormat.short(b.current.dueDate))"
                         + (b.payerMode == .everyone ? " · \(b.current.paidCount)/\(b.current.expectedCount) paid" : ""))
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                if let cents = b.current.amountCents ?? b.amountCents {
                    Text(Money.format(cents, b.currency)).font(.subheadline).monospacedDigit()
                }
                Badge(text: Self.statusText(b.current.status), color: Self.statusColor(b.current.status))
            }
        }
    }

    private static func statusText(_ s: BillStatus) -> String {
        switch s {
        case .paid: "✓ Paid"
        case .due: "• Due"
        case .overdue: "! Overdue"
        case .upcoming: "… Upcoming"
        }
    }

    private static func statusColor(_ s: BillStatus) -> Color {
        switch s {
        case .paid: .green
        case .due: .orange
        case .overdue: .red
        case .upcoming: .gray
        }
    }

    /// "0.1", "2.5", "12": small fair shares keep a decimal so they don't read as 0.
    static func share(_ n: Double) -> String {
        n < 10 ? String(format: "%.1f", n).replacingOccurrences(of: ".0", with: "") : String(Int(n.rounded()))
    }

    static func monthLabel(_ month: String) -> String {
        guard let date = DayFormat.day("\(month)-01") else { return month }
        return date.formatted(.dateTime.month(.abbreviated))
    }
}
