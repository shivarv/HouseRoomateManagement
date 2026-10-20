import SwiftUI

struct TaskRow: View {
    let task: ChoreTask
    var canToggle: Bool
    var showHousehold = false
    var overdue = false
    var onToggle: () -> Void = {}

    var body: some View {
        HStack(spacing: 12) {
            Text(task.isDone ? "✓" : ChoreIcon.emoji(for: task.chore.name))
                .font(.title3)
                .frame(width: 40, height: 40)
                .background(task.isDone ? Color.green.opacity(0.15) : Color.accentColor.opacity(0.12), in: Circle())

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(task.chore.name)
                        .font(.headline)
                        .strikethrough(task.isDone)
                        .foregroundStyle(task.isDone ? .secondary : .primary)
                    if overdue {
                        Badge(text: "Overdue · \(DayFormat.short(task.dueDate))", color: .orange)
                    } else if task.isMine {
                        Badge(text: "You", color: .accentColor)
                    }
                }
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer(minLength: 0)

            if canToggle {
                Button(task.isDone ? "Undo" : "Done", action: onToggle)
                    .buttonStyle(.bordered)
                    .tint(task.isDone ? .gray : .accentColor)
            }
        }
        .padding(.vertical, 4)
    }

    private var subtitle: String {
        var parts = [task.isMine ? "Assigned to you" : task.member.displayName]
        if showHousehold { parts.append(task.householdName) }
        if let next = task.nextAssignee { parts.append("Next: \(next.displayName)") }
        return parts.joined(separator: " · ")
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

    /// "Mon, Oct 20" — backend dates are calendar days, so no timezone shifting.
    static func short(_ iso: String) -> String {
        guard let date = parser.date(from: iso) else { return iso }
        return date.formatted(.dateTime.weekday(.abbreviated).month(.abbreviated).day())
    }

    static func long(_ iso: String) -> String {
        guard let date = parser.date(from: iso) else { return iso }
        return date.formatted(.dateTime.weekday(.wide).month(.wide).day())
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
