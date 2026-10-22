import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { shoppingApi, type ShoppingFields } from "../../api/shopping";

export const shoppingKeys = { list: (householdId: string) => ["shopping", householdId] as const };

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
  return () => Promise.all(["shopping", "activity"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
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
