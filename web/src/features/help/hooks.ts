import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { helpApi } from "../../api/help";

export const helpKeys = { all: ["help"] as const };

/** Polls so new requests show up in the top-bar badge without a reload. */
export function useHelpRequests() {
  return useQuery({
    queryKey: helpKeys.all,
    queryFn: helpApi.list,
    refetchOnWindowFocus: true,
    refetchInterval: 60_000,
  });
}

/** Requests and the activity feed change together. Refetch on errors too: a 409 means stale data. */
function useInvalidateHelp() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(["help", "activity"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
}

export function useCreateHelp() {
  const invalidate = useInvalidateHelp();
  return useMutation({
    mutationFn: ({ householdId, title, details }: { householdId: string; title: string; details?: string }) =>
      helpApi.create(householdId, title, details),
    onSuccess: invalidate,
  });
}

export function useUpdateHelp() {
  const invalidate = useInvalidateHelp();
  return useMutation({
    mutationFn: ({ id, ...changes }: { id: string; title?: string; details?: string }) => helpApi.update(id, changes),
    onSettled: invalidate,
  });
}

export function useMarkHelpDone() {
  const invalidate = useInvalidateHelp();
  return useMutation({ mutationFn: helpApi.done, onSettled: invalidate });
}

export function useReopenHelp() {
  const invalidate = useInvalidateHelp();
  return useMutation({ mutationFn: helpApi.reopen, onSettled: invalidate });
}

export function useWithdrawHelp() {
  const invalidate = useInvalidateHelp();
  return useMutation({ mutationFn: helpApi.withdraw, onSettled: invalidate });
}
