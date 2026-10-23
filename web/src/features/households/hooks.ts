import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMatch, useNavigate } from "react-router";
import { householdsApi } from "../../api/households";
import { lastHousehold, useLastHousehold } from "../../lib/lastHousehold";
import { unsavedChanges } from "../../lib/unsavedChanges";

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
    mutationFn: ({ name, address, timezone }: { name: string; address: string; timezone: string }) =>
      householdsApi.create(name, address, timezone),
    onSuccess: invalidate,
  });
}

export function useUpdateHousehold(id: string) {
  const invalidate = useInvalidateEverything();
  return useMutation({
    mutationFn: (changes: { name?: string; address?: string; timezone?: string }) =>
      householdsApi.update(id, changes),
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
    mutationFn: ({
      id,
      ...changes
    }: {
      id: string;
      display_name?: string;
      role?: "admin" | "member";
      email?: string;
      phone?: string;
    }) => householdsApi.updateMember(id, changes),
    onSuccess: invalidate,
  });
}

/** My default house (last picked or visited, else the first) and all my houses. */
export function useDefaultHousehold() {
  const households = useHouseholds();
  const last = useLastHousehold();
  const list = households.data ?? [];
  return { households, house: list.find((h) => h.id === last) ?? list[0] };
}

/** Switch the house the tabs act on. On a house page, stay on the same tab of the new house. */
export function useSwitchHousehold() {
  const navigate = useNavigate();
  const match = useMatch("/households/:householdId/*");
  const onHousePage = match && match.params.householdId !== "new";
  return (id: string) => {
    if (!unsavedChanges.confirmLeave()) return; // the dropdown is controlled, so it snaps back
    lastHousehold.set(id);
    if (onHousePage) navigate(`/households/${id}/${match.params["*"] ?? ""}`);
  };
}

/** Deleting a house touches everything (lists, tasks, bills), so refetch all. */
export function useDeleteHousehold() {
  const invalidate = useInvalidateEverything();
  return useMutation({ mutationFn: householdsApi.remove, onSuccess: invalidate });
}
