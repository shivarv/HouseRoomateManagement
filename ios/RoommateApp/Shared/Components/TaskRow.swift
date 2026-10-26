import SwiftUI

/// One rotation turn. Anyone can mark it done, for themselves or for someone else.
/// On my own turn the menu also offers "Ask for a swap".
struct TaskRow: View {
    let task: ChoreTask
    var members: [MemberBrief] = []  // for "someone else did it"
    var myMemberId: UUID?
    var showHousehold = false
    var overdue = false
    var onDone: (UUID?) -> Void = { _ in }
    var onUndo: () -> Void = {}
    var onAskSwap: ((String?) -> Void)?  // note
    var onCancelSwap: ((UUID) -> Void)?  // swap or request id

    @State private var askingSwap = false
    @State private var note = ""

    var body: some View {
        HStack(spacing: 12) {
            ChoreAvatar(name: task.chore.name, done: task.isDone)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(task.chore.name)
                        .font(.headline)
                        .strikethrough(task.isDone)
                        .foregroundStyle(task.isDone ? .secondary : .primary)
                    if task.isWeekly { Badge(text: "This week") }
                    if overdue {
                        Badge(text: "Missed · \(DayFormat.short(task.dueDate))", color: .orange)
                    } else if task.isMine && !task.isDone {
                        Badge(text: "You", color: .accentColor)
                    }
                    if task.wasCovered { Badge(text: "Covered", color: .green) }
                }
                if let swap = task.swap {
                    Badge(text: swap.role == .given ? "⇄ from \(swap.other.displayName)"
                                                     : "⇄ paying back \(swap.other.displayName)",
                          color: .indigo)
                }
                if task.swapRequestId != nil && !task.isDone {
                    Badge(text: "Swap requested · waiting", color: .orange)
                }
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer(minLength: 0)

            if task.isDone {
                Button("Undo", action: onUndo)
                    .buttonStyle(.bordered)
                    .tint(.gray)
            } else {
                DoneButton(title: task.isMine ? "Done" : "I did it",
                           others: members.filter { $0.id != myMemberId },
                           actions: menuActions,
                           onDone: onDone)
            }
        }
        .padding(.vertical, 4)
        .sensoryFeedback(.success, trigger: task.isDone) { _, done in done }
        .alert("Swap \(task.chore.name) · \(turnLabel)?", isPresented: $askingSwap) {
            TextField("Optional note, e.g. travelling", text: $note)
            Button("Send to the house") {
                let trimmed = note.trimmingCharacters(in: .whitespaces)
                onAskSwap?(trimmed.isEmpty ? nil : trimmed)
                note = ""
            }
            Button("Never mind", role: .cancel) { note = "" }
        } message: {
            Text("Everyone in the house sees this. Whoever accepts first takes this turn, and you'll do their next \(task.chore.name) turn in return.")
        }
    }

    private var turnLabel: String {
        task.isWeekly ? "week of \(DayFormat.short(task.dueDate))" : DayFormat.short(task.dueDate)
    }

    private var menuActions: [DoneButton.Action] {
        var actions: [DoneButton.Action] = []
        if !task.isMine {
            // "It's done": the person whose turn it is did it.
            actions.append(.init(title: "It's done (\(task.member.displayName) did it)", systemImage: "checkmark.circle") {
                onDone(task.member.id)
            })
        }
        if task.isMine && !overdue && task.swapRequestId == nil, onAskSwap != nil {
            actions.append(.init(title: "Ask for a swap", systemImage: "arrow.left.arrow.right") { askingSwap = true })
        }
        if task.isMine, let id = task.swapRequestId, let onCancelSwap {
            actions.append(.init(title: "Cancel swap request", systemImage: "xmark", role: .destructive) { onCancelSwap(id) })
        }
        if let swap = task.swap, swap.canCancel, let onCancelSwap {
            actions.append(.init(title: "Cancel swap", systemImage: "arrow.uturn.backward", role: .destructive) {
                onCancelSwap(swap.id)
            })
        }
        return actions
    }

    private var subtitle: String {
        let turn = task.isMine ? "Your turn" : "\(task.member.displayName)'s turn"
        let whose = task.isMine ? "your turn" : turn
        var parts: [String] = []
        if task.isDone {
            let doer = task.completedBy?.displayName ?? task.member.displayName
            parts.append("Done by \(doer)" + (task.wasCovered ? " · \(whose)" : ""))
        } else {
            parts.append(turn)
            if task.isWeekly { parts.append("any day until \(DayFormat.short(task.periodEnd))") }
        }
        if showHousehold { parts.append(task.householdName) }
        if let next = task.nextAssignee { parts.append("Next: \(next.displayName)") }
        return parts.joined(separator: " · ")
    }
}

/// Tap: done by me. Long-press (or the menu): pick who actually did it, or another action.
struct DoneButton: View {
    struct Action: Identifiable {
        let title: String
        let systemImage: String
        var role: ButtonRole?
        let run: () -> Void

        var id: String { title }

        init(title: String, systemImage: String, role: ButtonRole? = nil, run: @escaping () -> Void) {
            self.title = title
            self.systemImage = systemImage
            self.role = role
            self.run = run
        }
    }

    let title: String
    let others: [MemberBrief]
    var actions: [Action] = []
    let onDone: (UUID?) -> Void

    var body: some View {
        if others.isEmpty && actions.isEmpty {
            Button(title) { onDone(nil) }
                .buttonStyle(.borderedProminent)
        } else {
            Menu {
                Button("I did it", systemImage: "checkmark") { onDone(nil) }
                if !others.isEmpty {
                    Section("Someone else did it") {
                        ForEach(others) { m in
                            Button(m.displayName) { onDone(m.id) }
                        }
                    }
                }
                if !actions.isEmpty {
                    Section {
                        ForEach(actions) { a in
                            Button(a.title, systemImage: a.systemImage, role: a.role, action: a.run)
                        }
                    }
                }
            } label: {
                Text(title)
            } primaryAction: {
                onDone(nil)
            }
            .menuStyle(.button)
            .buttonStyle(.borderedProminent)
        }
    }
}

/// A chore nobody is assigned to (e.g. garbage): one button per person, fewest this year first.
/// Whoever did it taps their own name.
struct OpenChoreRow: View {
    let item: OpenChore
    var myMemberId: UUID?
    var today: String?
    var showHousehold = false
    var onLog: (UUID) -> Void = { _ in }
    var onRemove: (ChoreLog) -> Void = { _ in }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 12) {
                ChoreAvatar(name: item.chore.name)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(item.chore.name).font(.headline)
                        Badge(text: "Anyone", color: .green)
                        if let target = item.targetPerWeek {
                            Badge(text: "\(item.thisWeekCount)/\(target) this week",
                                  color: item.thisWeekCount >= target ? .green : .orange)
                        }
                    }
                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }

            Text("Who did it? Tap your name." + (item.suggested.map { " Suggested next: \($0.displayName)." } ?? ""))
                .font(.caption)
                .foregroundStyle(.secondary)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    ForEach(Array(item.people.enumerated()), id: \.element.id) { index, person in
                        Button {
                            onLog(person.member.id)
                        } label: {
                            VStack(alignment: .leading, spacing: 1) {
                                Text(person.member.displayName + (person.member.id == myMemberId ? " (you)" : ""))
                                    .font(.subheadline.weight(.medium))
                                Text("\(person.thisYear) this year" + (index == 0 ? " · next" : ""))
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                            .padding(.horizontal, 10).padding(.vertical, 6)
                            .background(index == 0 ? Color.accentColor.opacity(0.12) : Color.secondary.opacity(0.08),
                                        in: RoundedRectangle(cornerRadius: 8))
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            if !item.todayLogs.isEmpty {
                HStack(spacing: 6) {
                    Text("Today:").font(.caption).foregroundStyle(.secondary)
                    ForEach(item.todayLogs) { log in
                        Menu {
                            Button("Remove this entry", systemImage: "trash", role: .destructive) { onRemove(log) }
                        } label: {
                            Text("✓ \(log.member.displayName) · \(DayFormat.time(log.createdAt))")
                                .font(.caption)
                                .padding(.horizontal, 6).padding(.vertical, 2)
                                .background(Color.green.opacity(0.12), in: Capsule())
                                .foregroundStyle(.green)
                        }
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }

    private var subtitle: String {
        var parts: [String] = []
        if let last = item.lastDone {
            parts.append("Last done by \(last.member.displayName), \(DayFormat.relative(last.doneOn, today: today))")
        } else {
            parts.append("Not done yet")
        }
        if item.targetPerWeek == nil { parts.append("\(item.thisWeekCount) this week") }
        if showHousehold { parts.append(item.householdName) }
        return parts.joined(separator: " · ")
    }
}

struct ChoreAvatar: View {
    let name: String
    var done = false

    var body: some View {
        Text(done ? "✓" : ChoreIcon.emoji(for: name))
            .font(.title3)
            .frame(width: 40, height: 40)
            .background(done ? Color.green.opacity(0.15) : Color.accentColor.opacity(0.12), in: Circle())
    }
}

struct Badge: View {
    let text: String
    var color: Color = .gray

    var body: some View {
        Text(text)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.15), in: Capsule())
            .foregroundStyle(color)
    }
}

enum ChoreIcon {
    static func emoji(for name: String) -> String {
        let n = name.lowercased()
        if n.contains("cook") { return "🍳" }
        if n.contains("garbage") || n.contains("trash") { return "🗑️" }
        if n.contains("bath") { return "🛁" }
        if n.contains("clean") || n.contains("hall") { return "🧹" }
        return "📋"
    }
}

enum DayFormat {
    private static let parser: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    private static let isoFractional: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()

    private static let iso = ISO8601DateFormatter()

    static func day(_ iso: String) -> Date? { parser.date(from: iso) }

    static func timestamp(_ value: String) -> Date? {
        isoFractional.date(from: value) ?? iso.date(from: value)
    }

    /// "Mon, Oct 20" — backend dates are calendar days, so no timezone shifting.
    static func short(_ iso: String) -> String {
        guard let date = day(iso) else { return iso }
        return date.formatted(.dateTime.weekday(.abbreviated).month(.abbreviated).day())
    }

    static func long(_ iso: String) -> String {
        guard let date = day(iso) else { return iso }
        return date.formatted(.dateTime.weekday(.wide).month(.wide).day())
    }

    /// "today" / "yesterday" / "Mon, Oct 20", relative to the household's today when known.
    static func relative(_ iso: String, today: String? = nil) -> String {
        guard let date = day(iso) else { return iso }
        let reference = today.flatMap(day) ?? Calendar.current.startOfDay(for: .now)
        let days = Calendar.current.dateComponents([.day], from: date, to: reference).day ?? 0
        if days == 0 { return "today" }
        if days == 1 { return "yesterday" }
        return short(iso)
    }

    static func time(_ value: String) -> String {
        timestamp(value)?.formatted(date: .omitted, time: .shortened) ?? ""
    }

    static func month(_ yyyyMM: String) -> String {
        guard let date = day(yyyyMM + "-01") else { return yyyyMM }
        return date.formatted(.dateTime.month(.wide).year())
    }
}

struct ErrorBanner: View {
    let message: String?

    var body: some View {
        if let message {
            Label(message, systemImage: "exclamationmark.triangle.fill")
                .font(.footnote)
                .foregroundStyle(.red)
        }
    }
}
