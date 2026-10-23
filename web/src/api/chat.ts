import type { ChatMessage, ChatPage } from "../types/api";
import { api } from "./client";

const query = (params: Record<string, string | undefined>) => {
  const q = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => !!e[1])).toString();
  return q ? `?${q}` : "";
};

export const chatApi = {
  /** Latest messages; `before` pages back; `after` returns what's new or changed since then. */
  page: (householdId: string, opts: { before?: string; after?: string } = {}) =>
    api<ChatPage>(`/households/${householdId}/chat${query(opts)}`),
  send: (householdId: string, body: string) =>
    api<ChatMessage>(`/households/${householdId}/chat`, { method: "POST", body: { body } }),
  edit: (id: string, body: string) => api<ChatMessage>(`/chat-messages/${id}`, { method: "PATCH", body: { body } }),
  remove: (id: string) => api<ChatMessage>(`/chat-messages/${id}`, { method: "DELETE" }),
  markRead: (householdId: string) => api<void>(`/households/${householdId}/chat/read`, { method: "POST" }),
  unread: (householdId: string) => api<{ count: number }>(`/households/${householdId}/chat/unread`),
};
