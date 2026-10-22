import Foundation

/// One readable sentence per activity event. Mirrors web/src/features/chores/activityText.ts.
enum ActivityText {
    static func describe(_ e: ActivityEvent) -> (icon: String, text: String) {
        let actor = e.actor?.displayName ?? "Someone"
        let subject = e.subject?.displayName ?? "someone"
        let chore = e.choreName ?? "a chore"
        let forDay = e.dueDate.map { " (\(DayFormat.short($0)))" } ?? ""
        let markedBySomeoneElse = e.actor != nil && e.subject != nil && e.actor?.id != e.subject?.id
        let didIt = markedBySomeoneElse ? "\(actor) marked that \(subject) did" : "\(subject) did"

        switch e.action {
        case "completed":
            let cover = (e.assignee != nil && e.subject != nil && e.assignee?.id != e.subject?.id)
                ? " · \(e.assignee!.displayName)'s turn" : ""
            return ("✅", "\(didIt) \(chore)\(forDay)\(cover)")
        case "reopened":
            return ("↩️", "\(actor) undid \(chore)\(forDay)" + (e.subject != nil ? " (it was marked done for \(subject))" : ""))
        case "logged":
            return ("✅", "\(didIt) \(chore)")
        case "log_removed":
            return ("🗑", "\(actor) removed the entry “\(subject) did \(chore)”\(forDay)")
        case "swap_requested":
            return ("🔁", "\(actor) asked for someone to take \(chore)\(forDay)" + (e.detail.map { " — “\($0)”" } ?? ""))
        case "swap_accepted":
            let payback = e.detail.map { ". \(subject) does \(DayFormat.short($0)) in return" } ?? ""
            return ("🤝", "\(actor) took \(subject)'s \(chore)\(forDay)\(payback)")
        case "swap_cancelled":
            if e.actor == nil {
                return ("↩️", "\(e.assignee?.displayName ?? "Someone")'s swap for \(chore)\(forDay) was withdrawn")
            }
            return ("↩️", e.subject != nil
                ? "\(actor) cancelled the swap with \(subject) for \(chore)\(forDay)"
                : "\(actor) cancelled their swap request for \(chore)\(forDay)")
        case "swap_expired":
            return ("⌛", "Nobody took \(subject)'s \(chore)\(forDay)")
        case "help_requested":
            return ("🙋", "\(actor) asked for help: “\(e.detail ?? "something")”")
        case "help_updated":
            return ("✏️", "\(actor) edited their help request: “\(e.detail ?? "")”")
        case "help_done":
            return ("💪", "\(actor) helped \(subject): “\(e.detail ?? "a request")” is done")
        case "help_reopened":
            return ("↩️", "\(actor) reopened the help request “\(e.detail ?? "")”")
        case "help_withdrawn":
            return ("🗑", "\(actor) withdrew their help request “\(e.detail ?? "")”")
        case "shopping_added":
            return ("🛒", "\(actor) added “\(e.detail ?? "something")” to the shopping list")
        case "shopping_bought":
            return ("🛍️", "\(actor) bought \(e.detail ?? "something")")
        case "shopping_unbought":
            return ("↩️", "\(actor) put “\(e.detail ?? "")” back on the shopping list")
        case "shopping_removed":
            return ("🗑", "\(actor) took “\(e.detail ?? "")” off the shopping list")
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
