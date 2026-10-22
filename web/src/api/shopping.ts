import type { ShoppingCategory, ShoppingItem, ShoppingList } from "../types/api";
import { api } from "./client";

export interface ShoppingFields {
  name?: string;
  quantity?: string;
  category?: ShoppingCategory;
  note?: string;
}

export const shoppingApi = {
  list: (householdId: string) => api<ShoppingList>(`/households/${householdId}/shopping`),
  /** Already on the list (any capitalisation)? The existing item comes back instead of a copy. */
  add: (householdId: string, fields: ShoppingFields & { name: string }) =>
    api<ShoppingItem>(`/households/${householdId}/shopping`, { method: "POST", body: fields }),
  update: (id: string, fields: ShoppingFields) => api<ShoppingItem>(`/shopping/${id}`, { method: "PATCH", body: fields }),
  bought: (id: string) => api<ShoppingItem>(`/shopping/${id}/bought`, { method: "POST" }),
  boughtMany: (householdId: string, itemIds: string[]) =>
    api<ShoppingItem[]>(`/households/${householdId}/shopping/bought`, { method: "POST", body: { item_ids: itemIds } }),
  undo: (id: string) => api<ShoppingItem>(`/shopping/${id}/undo`, { method: "POST" }),
  remove: (id: string) => api<void>(`/shopping/${id}`, { method: "DELETE" }),
};
