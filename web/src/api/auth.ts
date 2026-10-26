import type { RegisterResponse, TokenResponse, User, VerifyEmailResponse } from "../types/api";
import { api } from "./client";

export const authApi = {
  login: (email: string, password: string) =>
    api<TokenResponse>("/auth/login", { method: "POST", body: { email, password } }),
  /** Doesn't sign in: we email a link. `next` is where that link lands afterwards (e.g. an invite). */
  register: (firstName: string, lastName: string, email: string, password: string, next?: string) =>
    api<RegisterResponse>("/auth/register", {
      method: "POST",
      body: { first_name: firstName, last_name: lastName, email, password, next },
    }),
  /** My first and last name (last may be empty). */
  updateProfile: (firstName: string, lastName: string) =>
    api<User>("/auth/me", { method: "PATCH", body: { first_name: firstName, last_name: lastName } }),
  me: () => api<User>("/auth/me"),
  /** For good: homes nobody else is in go with it; elsewhere a roommate takes over as admin. */
  deleteAccount: () => api<void>("/auth/me", { method: "DELETE" }),
  /** The link from the email; works signed out. */
  verifyEmail: (token: string) => api<VerifyEmailResponse>("/auth/verify-email", { method: "POST", body: { token } }),
  /** Signed out. The answer is the same whether or not the account exists. */
  resendVerification: (email: string, next?: string) =>
    api<{ email_enabled: boolean }>("/auth/resend-verification", { method: "POST", body: { email, next } }),
  setLastHousehold: (householdId: string) =>
    api<User>("/auth/me/last-household", { method: "PUT", body: { household_id: householdId } }),
};
