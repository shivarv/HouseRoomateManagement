import { formatDay } from "../../lib/format";
import type { ActivityEvent } from "../../types/api";

/** One readable sentence per activity event. Mirrored in iOS (ActivityText.swift). */
export function activityText(e: ActivityEvent): { icon: string; text: string } {
  const actor = e.actor?.display_name ?? "Someone";
  const subject = e.subject?.display_name ?? "someone";
  const chore = e.chore_name ?? "a chore";
  const forDay = e.due_date ? ` (${formatDay(e.due_date)})` : "";
  const byOther = e.actor && e.subject && e.actor.id !== e.subject.id ? ` · marked by ${actor}` : "";

  switch (e.action) {
    case "completed": {
      const cover = e.assignee && e.subject && e.assignee.id !== e.subject.id ? ` · ${e.assignee.display_name}'s turn` : "";
      return { icon: "✅", text: `${subject} did ${chore}${forDay}${cover}${byOther}` };
    }
    case "reopened":
      return { icon: "↩️", text: `${actor} undid ${chore}${forDay}${e.subject ? ` (was done by ${subject})` : ""}` };
    case "logged":
      return { icon: "✅", text: `${subject} did ${chore}${byOther}` };
    case "log_removed":
      return { icon: "🗑", text: `${actor} removed ${subject}'s ${chore} entry${forDay}` };
    case "chore_created":
      return { icon: "➕", text: `${actor} added the chore ${chore}${e.detail ? ` (${e.detail})` : ""}` };
    case "chore_updated":
      return { icon: "⚙️", text: `${actor} updated ${chore}${e.detail ? `: ${e.detail}` : ""}` };
    case "chore_deleted":
      return { icon: "✖️", text: `${actor} deleted the chore ${chore}` };
    case "rotation_changed":
      return { icon: "🔀", text: `${actor} changed the order of ${chore}` };
    case "member_added":
      return { icon: "👋", text: `${actor} added ${subject} to the house` };
    case "member_removed":
      return { icon: "🚪", text: `${actor} removed ${subject} from the house` };
    case "member_joined":
      return { icon: "🎉", text: `${subject} joined the house` };
    default:
      return { icon: "•", text: `${actor}: ${e.action}` };
  }
}
