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

export interface Chore {
  id: string;
  name: string;
  frequency: "daily";
  is_active: boolean;
  rotation: MemberBrief[];
  today_assignee: MemberBrief | null;
}

export interface Task {
  id: string;
  household_id: string;
  household_name: string;
  chore: { id: string; name: string };
  member: MemberBrief;
  due_date: string; // YYYY-MM-DD
  status: TaskStatus;
  completed_at: string | null;
  next_assignee: MemberBrief | null;
  is_mine: boolean;
}

export interface HouseholdTasksToday {
  date: string;
  tasks: Task[];
}

export interface MyTasksToday {
  tasks: Task[];
  overdue: Task[];
}

export interface ScheduleDay {
  date: string;
  slots: { chore: { id: string; name: string }; member: MemberBrief; status: TaskStatus | null }[];
}
