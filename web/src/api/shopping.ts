import type { GroceryCategory, GroceryPreset, GrocerySettings, ShoppingCategory, ShoppingItem, ShoppingList } from "../types/api";
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

/** Admin only: the house's categories and quick-add items. */
export const grocerySettingsApi = {
  get: (householdId: string) => api<GrocerySettings>(`/households/${householdId}/grocery-settings`),
  restore: (householdId: string) =>
    api<GrocerySettings>(`/households/${householdId}/grocery-settings/restore`, { method: "POST" }),

  addCategory: (householdId: string, body: { label: string; icon?: string }) =>
    api<GroceryCategory>(`/households/${householdId}/grocery-categories`, { method: "POST", body }),
  updateCategory: (id: string, body: { label?: string; icon?: string }) =>
    api<GroceryCategory>(`/grocery-categories/${id}`, { method: "PATCH", body }),
  deleteCategory: (id: string) => api<void>(`/grocery-categories/${id}`, { method: "DELETE" }),
  orderCategories: (householdId: string, ids: string[]) =>
    api<void>(`/households/${householdId}/grocery-categories/order`, { method: "PUT", body: { ids } }),

  addPreset: (householdId: string, body: { name: string; category_key?: ShoppingCategory }) =>
    api<GroceryPreset>(`/households/${householdId}/grocery-presets`, { method: "POST", body }),
  updatePreset: (id: string, body: { name?: string; category_key?: ShoppingCategory }) =>
    api<GroceryPreset>(`/grocery-presets/${id}`, { method: "PATCH", body }),
  removePreset: (id: string) => api<void>(`/grocery-presets/${id}`, { method: "DELETE" }),

  dismissSuggestion: (householdId: string, name: string) =>
    api<void>(`/households/${householdId}/grocery-suggestions/dismiss`, { method: "POST", body: { name } }),
};
