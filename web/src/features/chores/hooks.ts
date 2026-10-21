import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { choresApi, reportsApi, tasksApi, type ChoreSettings } from "../../api/chores";

export const choreKeys = {
  list: (householdId: string) => ["chores", householdId] as const,
  schedule: (householdId: string, days: number) => ["schedule", householdId, days] as const,
  householdToday: (householdId: string) => ["tasks", "household", householdId] as const,
  mine: ["tasks", "mine"] as const,
  activity: (householdId: string) => ["activity", householdId] as const,
  report: (householdId: string, month?: string) => ["report", householdId, month ?? "current"] as const,
  months: (householdId: string) => ["report", householdId, "months"] as const,
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

export function useActivity(householdId: string) {
  return useQuery({ queryKey: choreKeys.activity(householdId), queryFn: () => reportsApi.activity(householdId), ...live });
}

export function useReport(householdId: string, month?: string) {
  return useQuery({ queryKey: choreKeys.report(householdId, month), queryFn: () => reportsApi.report(householdId, month) });
}

export function useReportMonths(householdId: string, enabled: boolean) {
  return useQuery({ queryKey: choreKeys.months(householdId), queryFn: () => reportsApi.months(householdId), enabled });
}

/** Any chore change can affect today's list, the schedule, the feed and the report. */
function useInvalidateChoreData() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      ["chores", "schedule", "tasks", "activity", "report"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
    );
}

export function useCompleteTask() {
  const invalidate = useInvalidateChoreData();
  return useMutation({
    mutationFn: ({ id, completedBy }: { id: string; completedBy?: string }) => tasksApi.complete(id, completedBy),
    onSuccess: invalidate,
  });
}

export function useReopenTask() {
  const invalidate = useInvalidateChoreData();
  return useMutation({ mutationFn: (id: string) => tasksApi.reopen(id), onSuccess: invalidate });
}

export function useLogChore() {
  const invalidate = useInvalidateChoreData();
  return useMutation({
    mutationFn: ({ choreId, memberId }: { choreId: string; memberId?: string }) => choresApi.log(choreId, memberId),
    onSuccess: invalidate,
  });
}

export function useRemoveLog() {
  const invalidate = useInvalidateChoreData();
  return useMutation({ mutationFn: choresApi.removeLog, onSuccess: invalidate });
}

export function useCreateChore(householdId: string) {
  const invalidate = useInvalidateChoreData();
  return useMutation({
    mutationFn: (settings: ChoreSettings & { name: string }) => choresApi.create(householdId, settings),
    onSuccess: invalidate,
  });
}

export function useUpdateChore() {
  const invalidate = useInvalidateChoreData();
  return useMutation({
    mutationFn: ({ id, ...changes }: ChoreSettings & { id: string }) => choresApi.update(id, changes),
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
