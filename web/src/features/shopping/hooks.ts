import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { grocerySettingsApi, shoppingApi, type ShoppingFields } from "../../api/shopping";

export const shoppingKeys = {
  list: (householdId: string) => ["shopping", householdId] as const,
  settings: (householdId: string) => ["grocery-settings", householdId] as const,
};

/** Polls so items others add or buy show up without a reload. */
export function useShoppingList(householdId: string) {
  return useQuery({
    queryKey: shoppingKeys.list(householdId),
    queryFn: () => shoppingApi.list(householdId),
    refetchOnWindowFocus: true,
    refetchInterval: 60_000,
  });
}

/** The list and the activity feed change together. Refetch on errors too: a 409 means stale data. */
function useInvalidateShopping() {
  const queryClient = useQueryClient();
  // Adding items changes the admin's suggestions too.
  return () =>
    Promise.all(
      ["shopping", "activity", "grocery-settings"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
    );
}

export function useAddShopping(householdId: string) {
  const invalidate = useInvalidateShopping();
  return useMutation({
    mutationFn: (fields: ShoppingFields & { name: string }) => shoppingApi.add(householdId, fields),
    onSettled: invalidate,
  });
}

export function useUpdateShopping() {
  const invalidate = useInvalidateShopping();
  return useMutation({
    mutationFn: ({ id, ...fields }: ShoppingFields & { id: string }) => shoppingApi.update(id, fields),
    onSettled: invalidate,
  });
}

export function useBought() {
  const invalidate = useInvalidateShopping();
  return useMutation({ mutationFn: shoppingApi.bought, onSettled: invalidate });
}

export function useBoughtMany(householdId: string) {
  const invalidate = useInvalidateShopping();
  return useMutation({ mutationFn: (ids: string[]) => shoppingApi.boughtMany(householdId, ids), onSettled: invalidate });
}

export function useUndoBought() {
  const invalidate = useInvalidateShopping();
  return useMutation({ mutationFn: shoppingApi.undo, onSettled: invalidate });
}

export function useRemoveShopping() {
  const invalidate = useInvalidateShopping();
  return useMutation({ mutationFn: shoppingApi.remove, onSettled: invalidate });
}

/** Admin: categories, quick-add items and suggestions. */
export function useGrocerySettings(householdId: string) {
  return useQuery({ queryKey: shoppingKeys.settings(householdId), queryFn: () => grocerySettingsApi.get(householdId) });
}

/** Any change to the set-up shows on the Groceries tab too. Errors refetch: a 409 means stale data. */
export function useGrocerySettingsChange<T>(fn: (arg: T) => Promise<unknown>) {
  const invalidate = useInvalidateShopping();
  return useMutation({ mutationFn: fn, onSettled: invalidate });
}
