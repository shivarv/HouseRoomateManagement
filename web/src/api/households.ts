import type { EmailInvite, EmailInviteResults, Household, HouseholdDetail, HouseholdSetup, InvitePreview, Member, MyInvite, SetupTemplate } from "../types/api";
import { api } from "./client";

export const householdsApi = {
  list: () => api<Household[]>("/households"),
  get: (id: string) => api<HouseholdDetail>(`/households/${id}`),
  create: (name: string, address: string, timezone: string) =>
    api<Household>("/households", { method: "POST", body: { name, address, timezone } }),
  /** Guided set-up: defaults to prefill, then the whole house created in one go. */
  /** Admins only, for everyone in it. The last home you're an admin of can't be deleted (409). */
  remove: (id: string) => api<void>(`/households/${id}`, { method: "DELETE" }),
  /** No sign-in needed: the house name and how many live there, for an invite link's landing page. */
  invitePublic: (code: string) => api<{ household_name: string; people: number }>(`/invites/${encodeURIComponent(code)}/public`),
  /** Invite by email: each address is saved as pending, and emailed when email is set up. */
  emailInvites: (householdId: string, emails: string[]) =>
    api<EmailInviteResults>(`/households/${householdId}/email-invites`, { method: "POST", body: { emails } }),
  pendingInvites: (householdId: string) => api<EmailInvite[]>(`/households/${householdId}/email-invites`),
  cancelInvite: (id: string) => api<void>(`/email-invites/${id}`, { method: "DELETE" }),
  /** Houses that invited my email and I haven't joined yet. */
  myInvites: () => api<MyInvite[]>("/me/invites"),
  setupTemplate: () => api<SetupTemplate>("/households/setup/template"),
  setup: (body: HouseholdSetup) => api<Household>("/households/setup", { method: "POST", body }),
  update: (id: string, changes: { name?: string; address?: string; timezone?: string }) =>
    api<Household>(`/households/${id}`, { method: "PATCH", body: changes }),

  addMember: (householdId: string, displayName: string) =>
    api<Member>(`/households/${householdId}/members`, {
      method: "POST",
      body: { display_name: displayName },
    }),
  /** `email: ""` / `phone: ""` clear them. A joined member's email comes from their account. */
  updateMember: (memberId: string, changes: { display_name?: string; role?: Member["role"]; email?: string; phone?: string }) =>
    api<Member>(`/members/${memberId}`, { method: "PATCH", body: changes }),
  removeMember: (memberId: string) => api<void>(`/members/${memberId}`, { method: "DELETE" }),

  previewInvite: (code: string) => api<InvitePreview>(`/invites/${encodeURIComponent(code)}`),
  acceptInvite: (code: string, memberId: string | null) =>
    api<Household>(`/invites/${encodeURIComponent(code)}/accept`, {
      method: "POST",
      body: { member_id: memberId },
    }),
};
