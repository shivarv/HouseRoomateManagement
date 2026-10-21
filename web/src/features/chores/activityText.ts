import { formatDay, localIsoDate } from "../../lib/format";
import type { ActivityEvent, MemberBrief } from "../../types/api";

/** A sentence as segments, so names and chores can be highlighted. Mirrored in iOS (ActivityText.swift). */
export type Segment = string | { person: MemberBrief } | { chore: string };
export type ActivityKind = "done" | "undo" | "settings" | "people";

export interface ActivityLine {
  icon: string;
  kind: ActivityKind;
  parts: Segment[];
}

const who = (m: MemberBrief | null): Segment => (m ? { person: m } : "Someone");

export function activityText(e: ActivityEvent): ActivityLine {
  const chore: Segment = { chore: e.chore_name ?? "a chore" };
  const actorIsSubject = !e.actor || !e.subject || e.actor.id === e.subject.id;
  // Only mention the day when the chore was for a different day than when it was marked.
  const sameDay = e.due_date && e.due_date === localIsoDate(new Date(e.created_at));
  const forDay: Segment[] = e.due_date && !sameDay ? [` for ${formatDay(e.due_date)}`] : [];
  const turn: Segment[] =
    e.assignee && e.subject && e.assignee.id !== e.subject.id ? [" · ", { person: e.assignee }, "'s turn"] : [];

  switch (e.action) {
    case "completed":
    case "logged":
      return {
        icon: "✅",
        kind: "done",
        parts: actorIsSubject
          ? [who(e.subject ?? e.actor), " did ", chore, ...forDay, ...turn]
          : [who(e.actor), " marked that ", who(e.subject), " did ", chore, ...forDay, ...turn],
      };
    case "reopened":
      return {
        icon: "↩️",
        kind: "undo",
        parts: [
          who(e.actor),
          " undid ",
          chore,
          ...forDay,
          ...(e.subject ? [" (it was marked done for ", { person: e.subject }, ")"] : []),
        ],
      };
    case "log_removed":
      return {
        icon: "🗑",
        kind: "undo",
        parts: [who(e.actor), " removed the entry “", who(e.subject), " did ", chore, "”", ...forDay],
      };
    case "chore_created":
      return { icon: "➕", kind: "settings", parts: [who(e.actor), " added the chore ", chore, e.detail ? ` (${e.detail})` : ""] };
    case "chore_updated":
      return { icon: "⚙️", kind: "settings", parts: [who(e.actor), " updated ", chore, e.detail ? `: ${e.detail}` : ""] };
    case "chore_deleted":
      return { icon: "✖️", kind: "settings", parts: [who(e.actor), " deleted the chore ", chore] };
    case "rotation_changed":
      return { icon: "🔀", kind: "settings", parts: [who(e.actor), " changed the order of ", chore] };
    case "member_added":
      return { icon: "👋", kind: "people", parts: [who(e.actor), " added ", who(e.subject), " to the house"] };
    case "member_removed":
      return { icon: "🚪", kind: "people", parts: [who(e.actor), " removed ", who(e.subject), " from the house"] };
    case "member_joined":
      return { icon: "🎉", kind: "people", parts: [who(e.subject), " joined the house"] };
    default:
      return { icon: "•", kind: "settings", parts: [who(e.actor), `: ${e.action}`] };
  }
}

/** Plain-text version (titles, accessibility). */
export function activityPlainText(line: ActivityLine): string {
  return line.parts
    .map((p) => (typeof p === "string" ? p : "person" in p ? p.person.display_name : p.chore))
    .join("");
}
