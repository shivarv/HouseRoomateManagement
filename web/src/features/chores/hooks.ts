import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { choresApi, tasksApi } from "../../api/chores";

export const choreKeys = {
  list: (householdId: string) => ["chores", householdId] as const,
  schedule: (householdId: string, days: number) => ["schedule", householdId, days] as const,
  householdToday: (householdId: string) => ["tasks", "household", householdId] as const,
  mine: ["tasks", "mine"] as const,
};

// Refresh when the user comes back to the tab, so "today" rolls over after midnight.
const live = { refetchOnWindowFocus: true, refetchInterval: 5 * 60_000 } as const;

export function useChores(householdId: string) {
  return useQuery({ queryKey: choreKeys.list(householdId), queryFn: () => choresApi.list(householdId) });
}

export function useSchedule(householdId: string, days: number) {
  return useQuery({
    queryKey: choreKeys.schedule(householdId, days),
    queryFn: () => choresApi.schedule(householdId, days),
    ...live,
  });
}

export function useHouseholdToday(householdId: string) {
  return useQuery({
    queryKey: choreKeys.householdToday(householdId),
    queryFn: () => tasksApi.householdToday(householdId),
    ...live,
  });
}

export function useMyTasksToday() {
  return useQuery({ queryKey: choreKeys.mine, queryFn: tasksApi.mine, ...live });
}

function useInvalidateChoreData() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      ["chores", "schedule", "tasks"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
    );
}

export function useToggleTask() {
  const invalidate = useInvalidateChoreData();
  return useMutation({
    mutationFn: ({ id, done }: { id: string; done: boolean }) =>
      done ? tasksApi.complete(id) : tasksApi.reopen(id),
    onSuccess: invalidate,
  });
}

export function useCreateChore(householdId: string) {
  const invalidate = useInvalidateChoreData();
  return useMutation({ mutationFn: (name: string) => choresApi.create(householdId, name), onSuccess: invalidate });
}

export function useUpdateChore() {
  const invalidate = useInvalidateChoreData();
  return useMutation({
    mutationFn: ({ id, ...changes }: { id: string; name?: string; is_active?: boolean }) =>
      choresApi.update(id, changes),
    onSuccess: invalidate,
  });
}

export function useSetRotation() {
  const invalidate = useInvalidateChoreData();
  return useMutation({
    mutationFn: ({ id, memberIds }: { id: string; memberIds: string[] }) => choresApi.setRotation(id, memberIds),
    onSuccess: invalidate,
  });
}

export function useDeleteChore() {
  const invalidate = useInvalidateChoreData();
  return useMutation({ mutationFn: choresApi.remove, onSuccess: invalidate });
}
