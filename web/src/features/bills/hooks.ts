import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { billsApi } from "../../api/bills";

export function useBills(householdId: string, includePaused = false) {
  return useQuery({
    queryKey: ["bills", householdId, includePaused],
    queryFn: () => billsApi.list(householdId, includePaused),
    refetchOnWindowFocus: true,
    refetchInterval: 60_000, // a new day (or week, or month) brings new reminders
  });
}

export function useBillHistory(billId: string, enabled: boolean) {
  return useQuery({ queryKey: ["bills", "history", billId], queryFn: () => billsApi.history(billId), enabled });
}

/** Bills and the activity feed change together. Refetch on errors too: a 409 means stale data. */
export function useBillChange<T>(fn: (arg: T) => Promise<unknown>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSettled: () =>
      Promise.all(["bills", "activity"].map((key) => queryClient.invalidateQueries({ queryKey: [key] }))),
  });
}
