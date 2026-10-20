import type { TokenResponse, User } from "../types/api";
import { api } from "./client";

export const authApi = {
  login: (email: string, password: string) =>
    api<TokenResponse>("/auth/login", { method: "POST", body: { email, password } }),
  register: (name: string, email: string, password: string) =>
    api<TokenResponse>("/auth/register", { method: "POST", body: { name, email, password } }),
  me: () => api<User>("/auth/me"),
};
