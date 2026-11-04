import { formatDay, localIsoDate } from "../../lib/format";
import type { ActivityEvent, MemberBrief } from "../../types/api";

/** A sentence as segments, so names and chores can be highlighted. Mirrored in iOS (ActivityText.swift). */
export type Segment = string | { person: MemberBrief } | { chore: string };
export type ActivityKind = "done" | "undo" | "swap" | "help" | "shopping" | "bills" | "settings" | "people";

export interface ActivityLine {
  icon: string;
  kind: ActivityKind;
  parts: Segment[];
}

const who = (m: MemberBrief | null): Segment => (m ? { person: m } : "Someone");

// Done through the assistant rather than the buttons.
const VIA: Record<string, string> = { voice: " · 🎤 via voice", typed: " · ⌨️ via AI chat" };

export function activityText(e: ActivityEvent): ActivityLine {
  const line = describe(e);
  const via = e.via ? VIA[e.via] : undefined;
  return via ? { ...line, parts: [...line.parts, via] } : line;
}

function describe(e: ActivityEvent): ActivityLine {
  const chore: Segment = { chore: e.chore_name ?? "a chore" };
  const actorIsSubject = !e.actor || !e.subject || e.actor.id === e.subject.id;
  // Only mention the day when the chore was for a different day than when it was marked.
  const sameDay = e.due_date && e.due_date === localIsoDate(new Date(e.created_at));
  const forDay: Segment[] = e.due_date && !sameDay ? [` for ${formatDay(e.due_date)}`] : [];
  // Swaps are asked ahead of time, so always name the turn's day.
  const turnDay: Segment[] = e.due_date ? [` (${formatDay(e.due_date)})`] : [];
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
    case "swap_requested":
      return {
        icon: "🔁",
        kind: "swap",
        parts: [who(e.actor), " asked for someone to take ", chore, ...turnDay, e.detail ? ` — “${e.detail}”` : ""],
      };
    case "swap_accepted":
      return {
        icon: "🤝",
        kind: "swap",
        parts: [
          who(e.actor),
          " took ",
          who(e.subject),
          "'s ",
          chore,
          ...turnDay,
          ...(e.detail ? [". ", who(e.subject), ` does ${formatDay(e.detail)} in return`] : []),
        ],
      };
    case "swap_cancelled":
      return {
        icon: "↩️",
        kind: "swap",
        parts: !e.actor
          ? [who(e.assignee), "'s swap for ", chore, ...turnDay, " was withdrawn"]
          : e.subject
            ? [who(e.actor), " cancelled the swap with ", who(e.subject), " for ", chore, ...turnDay]
            : [who(e.actor), " cancelled their swap request for ", chore, ...turnDay],
      };
    case "swap_expired":
      return { icon: "⌛", kind: "swap", parts: ["Nobody took ", who(e.subject), "'s ", chore, ...turnDay] };
    case "help_requested":
      return { icon: "🙋", kind: "help", parts: [who(e.actor), ` asked a favour: “${e.detail ?? "something"}”`] };
    case "help_updated":
      return { icon: "✏️", kind: "help", parts: [who(e.actor), ` edited their favour: “${e.detail ?? ""}”`] };
    case "help_done":
      return {
        icon: "💪",
        kind: "help",
        parts: [who(e.actor), " helped ", who(e.subject), `: “${e.detail ?? "a request"}” is done`],
      };
    case "help_reopened":
      return { icon: "↩️", kind: "help", parts: [who(e.actor), ` reopened the favour “${e.detail ?? ""}”`] };
    case "help_withdrawn":
      return { icon: "🗑", kind: "help", parts: [who(e.actor), ` withdrew their favour “${e.detail ?? ""}”`] };
    case "shopping_added":
      return { icon: "🛒", kind: "shopping", parts: [who(e.actor), ` added “${e.detail ?? "something"}” to the shopping list`] };
    case "shopping_bought":
      return { icon: "🛍️", kind: "shopping", parts: [who(e.actor), ` bought ${e.detail ?? "something"}`] };
    case "shopping_unbought":
      return { icon: "↩️", kind: "shopping", parts: [who(e.actor), ` put “${e.detail ?? ""}” back on the shopping list`] };
    case "shopping_removed":
      return { icon: "🗑", kind: "shopping", parts: [who(e.actor), ` took “${e.detail ?? ""}” off the shopping list`] };
    case "bill_paid":
      return {
        icon: "💸",
        kind: "bills",
        parts: actorIsSubject
          ? [who(e.actor), ` paid ${e.detail ?? "a bill"}`]
          : [who(e.actor), " marked ", who(e.subject), ` as paid for ${e.detail ?? "a bill"}`],
      };
    case "bill_amount_set":
      return { icon: "🧮", kind: "bills", parts: [who(e.actor), ` set the amount for ${e.detail ?? "a bill"}`] };
    case "bill_unpaid":
      return { icon: "↩️", kind: "bills", parts: [who(e.actor), " undid a payment for ", e.detail ?? "a bill"] };
    case "bill_created":
      return { icon: "🧾", kind: "settings", parts: [who(e.actor), ` added the bill “${e.detail ?? ""}”`] };
    case "bill_updated":
      return { icon: "⚙️", kind: "settings", parts: [who(e.actor), ` updated the bill “${e.detail ?? ""}”`] };
    case "bill_deleted":
      return { icon: "✖️", kind: "settings", parts: [who(e.actor), ` deleted the bill “${e.detail ?? ""}”`] };
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
    case "member_left":
      return { icon: "👋", kind: "people", parts: [who(e.subject), " deleted their account and left the house"] };
    case "member_made_admin":
      return { icon: "⭐️", kind: "people", parts: [who(e.subject), " is now an admin"] };
    case "invite_code_reset":
      return { icon: "🔑", kind: "people", parts: [who(e.actor), " made a new invite link (old links no longer work)"] };
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
