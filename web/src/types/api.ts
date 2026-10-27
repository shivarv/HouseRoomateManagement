// Mirrors backend/app/schemas. Keep in sync with docs/API.md.

export type Role = "admin" | "member";
export type TaskStatus = "pending" | "done";

export interface User {
  id: string;
  /** null: signed up with Google, Apple or Facebook with only a phone. */
  email: string | null;
  phone: string | null; // contact only for now
  /** How I can sign in: "password", "google", "apple", "facebook". */
  providers: string[];
  first_name: string;
  last_name: string; // may be empty: then it's left out of `name`
  name: string; // "First Last"
  /** Opened the link we emailed. Accounts from before verification count as verified. */
  email_verified: boolean;
  /** May be a house I've since left; the UI then falls back to my first house. */
  last_household_id: string | null;
}

/** Signed up, not signed in: the emailed link confirms the address and signs them in. */
export interface RegisterResponse {
  email: string;
  sent: boolean;
  email_enabled: boolean; // false: no email service set up, so the link is only in the server log
}

export interface VerifyEmailResponse {
  user: User;
  /** Only the first time the link is opened: it signs them in. */
  access_token: string | null;
}

/** Adding someone who hasn't signed up: an email gets the invite right away. */
export interface MemberAdded {
  member: Member;
  emailed: boolean;
  email_enabled: boolean;
  link: string; // their personal invite link, for WhatsApp
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export type SocialProvider = "google" | "apple" | "facebook";

/** Signed in, or a new account that first needs `missing`: "name" and/or "contact" (email or phone). */
export interface OAuthResult {
  access_token: string | null;
  user: User | null;
  missing: ("name" | "contact")[];
  first_name: string;
  last_name: string;
  email: string | null;
}

/** Which "Continue with …" buttons to show (a provider is missing until it's set up). */
export interface AuthProviders {
  google: { web_client_id: string | null; ios_client_id: string | null } | null;
  facebook: { app_id: string } | null;
  apple: { web_services_id: string | null } | null;
}

/** What the person typed for what the provider didn't share. */
export interface OAuthExtras {
  first_name?: string;
  last_name?: string;
  email?: string;
  phone?: string;
}

export interface MemberBrief {
  id: string;
  display_name: string;
}

export interface Member extends MemberBrief {
  role: Role;
  is_active: boolean;
  has_account: boolean;
  /** added: by name only · invited: an email invite is waiting · joined: has an account */
  status: "added" | "invited" | "joined" | "verified";
  first_name: string; // from their account; empty until they join
  last_name: string;
  email: string | null; // their account's once joined, else what an admin added
  phone: string | null;
}

export interface Household {
  id: string;
  name: string;
  /** null only on houses created before addresses were required. */
  address: string | null;
  timezone: string;
  invite_code: string;
  /** Why I can't delete it (null: I can, unless it's my last home as admin). */
  delete_blocked: string | null;
  my_member_id: string;
  my_role: Role;
  /** Names are unique per creator: I can't have two houses with the same name. */
  created_by_me: boolean;
}

export interface HouseholdDetail extends Household {
  members: Member[];
}

export interface InvitePreview {
  household_id: string;
  household_name: string;
  unclaimed_members: MemberBrief[];
}

export type Frequency = "daily" | "weekly";
export type AssignmentMode = "rotation" | "open";

export interface ChoreBrief {
  id: string;
  name: string;
  frequency: Frequency;
  assignment_mode: AssignmentMode;
}

export interface Chore {
  id: string;
  name: string;
  frequency: Frequency;
  assignment_mode: AssignmentMode;
  target_per_week: number | null;
  is_active: boolean;
  rotation: MemberBrief[];
  today_assignee: MemberBrief | null; // whose turn it is this period
}

export interface Task {
  id: string;
  household_id: string;
  household_name: string;
  chore: ChoreBrief;
  member: MemberBrief; // whose turn it is
  due_date: string; // YYYY-MM-DD, period start
  period_end: string; // same day (daily) or Sunday (weekly)
  status: TaskStatus;
  completed_at: string | null;
  completed_by: MemberBrief | null;
  next_assignee: MemberBrief | null;
  is_mine: boolean;
  swap: TaskSwap | null; // this turn changed hands through a swap
  swap_request_id: string | null; // an open "Ask for a swap" on this turn
}

export interface TaskSwap {
  id: string;
  role: "given" | "payback"; // given: took it over from `other`; payback: paying `other` back
  other: MemberBrief;
  can_cancel: boolean;
}

export type SwapStatus = "open" | "accepted" | "cancelled" | "expired";

export interface Swap {
  id: string;
  household_id: string;
  household_name: string;
  chore: ChoreBrief;
  given_date: string; // the turn being given away (period start)
  period_end: string;
  requester: MemberBrief;
  acceptor: MemberBrief | null;
  payback_date: string | null; // once accepted: the acceptor's turn the requester now does
  status: SwapStatus;
  note: string | null;
  created_at: string;
  is_mine: boolean; // I asked
  can_accept: boolean;
  payback_preview: string | null; // the turn I'd give back if I took it
}

export interface ChoreLog {
  id: string;
  member: MemberBrief;
  logged_by: MemberBrief | null;
  done_on: string;
  created_at: string;
}

export interface OpenChore {
  household_id: string;
  household_name: string;
  chore: ChoreBrief;
  target_per_week: number | null;
  today_logs: ChoreLog[];
  this_week_count: number;
  last_done: ChoreLog | null;
  people: OpenChoreCount[]; // everyone, fewest this year first
  suggested: MemberBrief | null; // first in `people` — a hint, not an assignment
  suggested_reason: string | null;
}

export interface OpenChoreCount {
  member: MemberBrief;
  this_year: number;
  this_month: number;
  last_done: string | null;
}

export interface HouseholdTasksToday {
  date: string;
  tasks: Task[];
  open: OpenChore[];
}

export interface UpcomingTurn {
  household_id: string;
  household_name: string;
  chore: ChoreBrief;
  due_date: string;
}

export interface MyTasksToday {
  tasks: Task[]; // my turns now
  others: Task[]; // everyone else's turns now
  upcoming: UpcomingTurn[]; // my next turn per rotation chore, soonest first
  overdue: Task[];
  open: OpenChore[];
}

export interface ScheduleDay {
  date: string;
  slots: { chore: ChoreBrief; member: MemberBrief; status: TaskStatus | null; swapped_with: MemberBrief | null }[];
}

/** A GroceryCategory.key of the house. Admins configure the categories; "other" always exists. */
export type ShoppingCategory = string;

export interface GroceryCategory {
  id: string;
  key: ShoppingCategory; // what items store; never changes, so renaming is free
  label: string;
  icon: string;
  position: number;
  can_delete: boolean; // false only for "other", the fallback
}

export interface GroceryPreset {
  id: string;
  name: string;
  category_key: ShoppingCategory;
  position: number;
}

/** Something people added that isn't a quick-add item yet. */
export interface GrocerySuggestion {
  name: string;
  times_added: number;
  category_key: ShoppingCategory;
}

export interface GrocerySettings {
  categories: GroceryCategory[];
  presets: GroceryPreset[];
  suggestions: GrocerySuggestion[]; // most added first
}

export interface ShoppingItem {
  id: string;
  name: string;
  quantity: string | null; // free text: "2 dozen", "1 L"
  category: ShoppingCategory;
  note: string | null;
  status: "needed" | "bought";
  added_by: MemberBrief | null;
  bought_by: MemberBrief | null;
  bought_at: string | null;
  created_at: string;
  can_undo: boolean; // bought, and I bought it or added it
}

export interface ShoppingList {
  needed: ShoppingItem[]; // oldest first
  recently_bought: ShoppingItem[]; // last 14 days, newest first
  categories: GroceryCategory[]; // display order
  quick_add: GroceryPreset[]; // chosen by the admin, in order
}

export type HelpStatus = "open" | "done";

export interface HelpRequest {
  id: string;
  household_id: string;
  household_name: string;
  requester: MemberBrief;
  title: string; // a preset or the person's own words
  details: string | null;
  status: HelpStatus;
  done_by: MemberBrief | null;
  done_at: string | null;
  created_at: string;
  updated_at: string;
  is_mine: boolean; // I asked: I can edit or withdraw it while it's open
  can_reopen: boolean; // I asked, or I marked it done
}

export interface ActivityEvent {
  id: string;
  action: string;
  created_at: string;
  actor: MemberBrief | null;
  subject: MemberBrief | null;
  assignee: MemberBrief | null;
  chore_id: string | null;
  chore_name: string | null;
  due_date: string | null;
  detail: string | null;
}

export interface ReportRow {
  member: MemberBrief;
  is_active: boolean;
  done: number;
  share: number;
  turns: number | null;
  missed: number | null;
  covered_by_others: number | null;
  covered_for_others: number | null;
  last_done: string | null;
}

export interface ChoreReport {
  chore: ChoreBrief;
  is_active: boolean;
  total_done: number;
  total_missed: number | null;
  rows: ReportRow[];
}

export interface Report {
  month: string;
  start: string;
  end: string;
  is_current: boolean;
  fair_share: number;
  chores: ChoreReport[];
  leaderboard: { member: MemberBrief; is_active: boolean; done: number; missed: number; covered_for_others: number }[];
}

/** anyone: one payment settles it (whoever pays first) · everyone: split, each pays a share */
export type PayerMode = "anyone" | "everyone";
export type BillFrequency = "monthly" | "weekly" | "daily";
/** fixed: the amount repeats · variable: an admin enters each period's amount (gas, electricity) */
export type AmountType = "fixed" | "variable";
export type BillStatus = "paid" | "due" | "overdue" | "upcoming";

export interface BillPayment {
  id: string;
  member: MemberBrief; // who paid
  recorded_by: MemberBrief | null;
  paid_at: string;
  can_undo: boolean;
}

/** One occurrence of a bill: this month's rent, this week's cleaner, today's milk money. */
export interface BillPeriod {
  period: string; // start: month start, Monday, or the day
  period_end: string;
  label: string; // "Oct 2026", "Week of Oct 19", "Mon, Oct 19"
  due_date: string;
  status: BillStatus;
  amount_cents: number | null; // fixed: the bill's; variable: this period's, once an admin sets it
  share_cents: number | null; // everyone mode: each person's part
  payments: BillPayment[];
  paid_count: number;
  expected_count: number; // everyone: active people in the house; otherwise 1
  i_paid: boolean;
  is_current: boolean; // not a future period, so it can be paid
}

export interface Bill {
  id: string;
  name: string;
  icon: string;
  payer_mode: PayerMode;
  frequency: BillFrequency;
  due_day: number; // monthly: day of the month · weekly: 1 = Mon … 7 = Sun · daily: unused
  amount_type: AmountType;
  amount_cents: number | null; // fixed bills
  last_amount_cents: number | null; // variable bills: the latest amount before this period
  currency: string;
  note: string | null;
  position: number;
  is_active: boolean;
  current: BillPeriod;
}

export interface BillList {
  today: string;
  bills: Bill[];
}

export interface BillFields {
  name?: string;
  icon?: string;
  payer_mode?: PayerMode;
  frequency?: BillFrequency;
  due_day?: number;
  amount_type?: AmountType;
  amount_cents?: number | null;
  currency?: string;
  note?: string;
  is_active?: boolean;
}

// --- Guided set-up of a new house -------------------------------------------------------------

export interface SetupChore {
  name: string;
  frequency: Frequency; // daily | weekly
  assignment_mode: AssignmentMode; // rotation | open
  people?: string[]; // who takes turns, in order, by name; left out = everyone
}

export interface SetupGrocery {
  name: string;
  category_key: string;
}

export interface SetupBill {
  name: string;
  icon: string;
  payer_mode: PayerMode;
  frequency: BillFrequency;
  due_day: number;
  amount_type: AmountType;
  amount_cents: number | null;
}

/** Defaults to prefill the set-up with, up to `max_items` of each. */
export interface SetupTemplate {
  max_items: number;
  chores: SetupChore[];
  groceries: SetupGrocery[];
  bills: SetupBill[];
  categories: { key: string; label: string; icon: string }[];
}

export interface HouseholdSetup {
  name: string;
  address: string;
  timezone: string;
  roommates: string[]; // besides me
  chores: SetupChore[];
  groceries: SetupGrocery[];
  bills: SetupBill[];
  currency: string;
}

// --- Invites by email ---------------------------------------------------------------------------

export interface EmailInvite {
  id: string;
  email: string;
  invited_by: MemberBrief | null;
  created_at: string;
  last_sent_at: string | null; // null: saved, but not emailed (no email service set up)
  can_cancel: boolean;
}

export interface EmailInviteResults {
  // sent: emailed now · saved: kept, but emailing isn't set up · member: already in the house
  results: {
    email: string;
    // saved: kept but email isn't set up · failed: kept but the email didn't go out (see reason)
    status: "sent" | "saved" | "failed" | "member";
    reason: "bad_address" | "unavailable" | "refused" | null;
  }[];
  link: string;
  email_enabled: boolean;
}

export interface MyInvite {
  household_name: string;
  invite_code: string;
  token: string; // the private invite link: /invite/{token}
  invited_by: string | null;
  created_at: string;
}

// --- House chat -----------------------------------------------------------------------------------

export interface ChatMessage {
  id: string;
  author: MemberBrief | null; // null if they left the house
  body: string; // "" once deleted
  created_at: string;
  edited_at: string | null;
  changed_at: string; // sent, edited or deleted, whichever is latest
  deleted: boolean;
  is_mine: boolean;
  can_edit: boolean;
  can_delete: boolean;
}

export interface ChatPage {
  messages: ChatMessage[]; // oldest first
  has_more: boolean;
}

/** What a private invite link shows before signing in. */
export interface InviteLinkPublic {
  household_name: string;
  people: number;
  email: string; // who it's for
  invited_by: string | null; // who sent it
}
