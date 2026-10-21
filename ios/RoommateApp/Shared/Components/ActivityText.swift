import Foundation

/// One readable sentence per activity event. Mirrors web/src/features/chores/activityText.ts.
enum ActivityText {
    static func describe(_ e: ActivityEvent) -> (icon: String, text: String) {
        let actor = e.actor?.displayName ?? "Someone"
        let subject = e.subject?.displayName ?? "someone"
        let chore = e.choreName ?? "a chore"
        let forDay = e.dueDate.map { " (\(DayFormat.short($0)))" } ?? ""
        let byOther = (e.actor != nil && e.subject != nil && e.actor?.id != e.subject?.id)
            ? " · marked by \(actor)" : ""

        switch e.action {
        case "completed":
            let cover = (e.assignee != nil && e.subject != nil && e.assignee?.id != e.subject?.id)
                ? " · \(e.assignee!.displayName)'s turn" : ""
            return ("✅", "\(subject) did \(chore)\(forDay)\(cover)\(byOther)")
        case "reopened":
            return ("↩️", "\(actor) undid \(chore)\(forDay)" + (e.subject != nil ? " (was done by \(subject))" : ""))
        case "logged":
            return ("✅", "\(subject) did \(chore)\(byOther)")
        case "log_removed":
            return ("🗑", "\(actor) removed \(subject)'s \(chore) entry\(forDay)")
        case "chore_created":
            return ("➕", "\(actor) added the chore \(chore)" + (e.detail.map { " (\($0))" } ?? ""))
        case "chore_updated":
            return ("⚙️", "\(actor) updated \(chore)" + (e.detail.map { ": \($0)" } ?? ""))
        case "chore_deleted":
            return ("✖️", "\(actor) deleted the chore \(chore)")
        case "rotation_changed":
            return ("🔀", "\(actor) changed the order of \(chore)")
        case "member_added":
            return ("👋", "\(actor) added \(subject) to the house")
        case "member_removed":
            return ("🚪", "\(actor) removed \(subject) from the house")
        case "member_joined":
            return ("🎉", "\(subject) joined the house")
        default:
            return ("•", "\(actor): \(e.action)")
        }
    }
}
