import type { Bill, BillFields, BillList, BillPayment, BillPeriod } from "../types/api";
import { api } from "./client";

export const billsApi = {
  list: (householdId: string, includePaused = false) =>
    api<BillList>(`/households/${householdId}/bills${includePaused ? "?include_paused=true" : ""}`),
  /** The periods before the current one, newest first. */
  history: (id: string, limit = 6) => api<BillPeriod[]>(`/bills/${id}/history?limit=${limit}`),

  /** Admin only. */
  create: (householdId: string, fields: BillFields & { name: string }) =>
    api<Bill>(`/households/${householdId}/bills`, { method: "POST", body: fields }),
  update: (id: string, fields: BillFields) => api<Bill>(`/bills/${id}`, { method: "PATCH", body: fields }),
  remove: (id: string) => api<void>(`/bills/${id}`, { method: "DELETE" }),
  /** Admin only: a variable bill's amount for one period (default: the current one). */
  setAmount: (id: string, amountCents: number | null, period?: string) =>
    api<Bill>(`/bills/${id}/amount`, { method: "PUT", body: { amount_cents: amountCents, period } }),

  /** Anyone in the house, for themselves (default) or someone else. Already paid → 409 saying who. */
  pay: (id: string, body: { member_id?: string; period?: string }) =>
    api<BillPayment>(`/bills/${id}/pay`, { method: "POST", body }),
  undo: (paymentId: string) => api<void>(`/bill-payments/${paymentId}`, { method: "DELETE" }),
};
