import SwiftUI

/// Monthly report: a leaderboard plus one section per chore, sorted by who did it most.
/// Meant to be placed inside a List.
struct ReportSections: View {
    let report: Report
    let myMemberId: UUID?

    private var totalDone: Int { report.leaderboard.reduce(0) { $0 + $1.done } }

    /// Below half of a fair share is called out; it's a nudge, not an accusation.
    private func isLow(_ share: Double) -> Bool { share < report.fairShare / 2 }

    var body: some View {
        Section {
            if totalDone == 0 && report.leaderboard.allSatisfy({ $0.missed == 0 }) {
                Text("Nothing recorded this month yet.").foregroundStyle(.secondary)
            }
            ForEach(Array(report.leaderboard.enumerated()), id: \.element.id) { index, row in
                HStack {
                    Text("\(index + 1)").foregroundStyle(.secondary).frame(width: 22, alignment: .leading)
                    Text(row.member.displayName)
                        .fontWeight(row.member.id == myMemberId ? .semibold : .regular)
                    if !row.isActive { Badge(text: "Left") }
                    if totalDone > 0 && row.isActive && isLow(Double(row.done) / Double(totalDone)) {
                        Badge(text: "Below fair share", color: .orange)
                    }
                    Spacer()
                    VStack(alignment: .trailing, spacing: 0) {
                        Text("\(row.done) done").monospacedDigit()
                        if row.missed > 0 {
                            Text("\(row.missed) missed").font(.caption).foregroundStyle(.orange)
                        }
                    }
                }
            }
        } header: {
            Text("Leaderboard · \(DayFormat.month(report.month))")
        } footer: {
            Text("Fair share is \(Int((report.fairShare * 100).rounded()))% each\(report.isCurrent ? " · month so far" : "").")
        }

        ForEach(report.chores) { chore in
            Section {
                ForEach(chore.rows) { row in
                    ReportRowView(row: row, isOpen: chore.chore.assignmentMode == .open,
                                  low: row.isActive && chore.totalDone > 0 && isLow(row.share),
                                  isMe: row.member.id == myMemberId)
                }
            } header: {
                HStack {
                    Text("\(ChoreIcon.emoji(for: chore.chore.name)) \(chore.chore.name)")
                    Spacer()
                    Text("\(chore.totalDone) done" + (chore.totalMissed.map { $0 > 0 ? " · \($0) missed" : "" } ?? ""))
                }
            }
        }
    }
}

private struct ReportRowView: View {
    let row: ReportRow
    let isOpen: Bool
    let low: Bool
    let isMe: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(row.member.displayName).fontWeight(isMe ? .semibold : .regular)
                if row.done == 0 && row.isActive {
                    Text("not yet").font(.caption).foregroundStyle(.orange)
                }
                Spacer()
                Text("\(row.done) · \(Int((row.share * 100).rounded()))%")
                    .monospacedDigit()
                    .foregroundStyle(.secondary)
            }
            ProgressView(value: row.share)
                .tint(low ? .orange : .accentColor)
            Text(notes).font(.caption).foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }

    private var notes: String {
        if isOpen {
            return row.lastDone.map { "last \(DayFormat.short($0))" } ?? "not this month"
        }
        var parts = ["\(row.turns ?? 0) turn\(row.turns == 1 ? "" : "s")"]
        if let missed = row.missed, missed > 0 { parts.append("\(missed) missed") }
        if let n = row.coveredByOthers, n > 0 { parts.append("\(n) covered by others") }
        if let n = row.coveredForOthers, n > 0 { parts.append("covered \(n)") }
        return parts.joined(separator: " · ")
    }
}
