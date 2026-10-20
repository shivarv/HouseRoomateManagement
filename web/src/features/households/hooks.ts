import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { householdsApi } from "../../api/households";

export const householdKeys = {
  all: ["households"] as const,
  detail: (id: string) => ["households", id] as const,
};

export function useHouseholds() {
  return useQuery({ queryKey: householdKeys.all, queryFn: householdsApi.list });
}

export function useHousehold(id: string) {
  return useQuery({ queryKey: householdKeys.detail(id), queryFn: () => householdsApi.get(id) });
}

/** Member and rotation changes affect chores, today's tasks and the schedule, so refetch all. */
function useInvalidateEverything() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries();
}

export function useCreateHousehold() {
  const invalidate = useInvalidateEverything();
  return useMutation({
    mutationFn: ({ name, timezone }: { name: string; timezone: string }) =>
      householdsApi.create(name, timezone),
    onSuccess: invalidate,
  });
}

export function useAcceptInvite() {
  const invalidate = useInvalidateEverything();
  return useMutation({
    mutationFn: ({ code, memberId }: { code: string; memberId: string | null }) =>
      householdsApi.acceptInvite(code, memberId),
    onSuccess: invalidate,
  });
}

export function useAddMember(householdId: string) {
  const invalidate = useInvalidateEverything();
  return useMutation({
    mutationFn: (displayName: string) => householdsApi.addMember(householdId, displayName),
    onSuccess: invalidate,
  });
}

export function useRemoveMember() {
  const invalidate = useInvalidateEverything();
  return useMutation({ mutationFn: householdsApi.removeMember, onSuccess: invalidate });
}

export function useUpdateMember() {
  const invalidate = useInvalidateEverything();
  return useMutation({
    mutationFn: ({ id, display_name, role }: { id: string; display_name?: string; role?: "admin" | "member" }) =>
      householdsApi.updateMember(id, { display_name, role }),
    onSuccess: invalidate,
  });
}
