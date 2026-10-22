// Mirrors backend/app/schemas. Keep in sync with docs/API.md.

export type Role = "admin" | "member";
export type TaskStatus = "pending" | "done";

export interface User {
  id: string;
  email: string;
  name: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface MemberBrief {
  id: string;
  display_name: string;
}

export interface Member extends MemberBrief {
  role: Role;
  is_active: boolean;
  has_account: boolean;
}

export interface Household {
  id: string;
  name: string;
  timezone: string;
  invite_code: string;
  my_member_id: string;
  my_role: Role;
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
