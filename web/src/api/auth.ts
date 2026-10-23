import type { TokenResponse, User } from "../types/api";
import { api } from "./client";

export const authApi = {
  login: (email: string, password: string) =>
    api<TokenResponse>("/auth/login", { method: "POST", body: { email, password } }),
  register: (firstName: string, lastName: string, email: string, password: string) =>
    api<TokenResponse>("/auth/register", {
      method: "POST",
      body: { first_name: firstName, last_name: lastName, email, password },
    }),
  /** My first and last name (last may be empty). */
  updateProfile: (firstName: string, lastName: string) =>
    api<User>("/auth/me", { method: "PATCH", body: { first_name: firstName, last_name: lastName } }),
  me: () => api<User>("/auth/me"),
  setLastHousehold: (householdId: string) =>
    api<User>("/auth/me/last-household", { method: "PUT", body: { household_id: householdId } }),
};
