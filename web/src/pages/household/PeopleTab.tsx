import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { householdsApi } from "../../api/households";
import { Badge, Button, ErrorText } from "../../components/ui";
import { useRemoveMember, useUpdateMember } from "../../features/households/hooks";
import { InvitePanel } from "../../features/households/InvitePanel";
import type { Member } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

const STATUS = {
  added: { label: "Added", tone: "slate", hint: "Hasn't joined yet" },
  invited: { label: "Invited", tone: "amber", hint: "Invite sent — waiting for them to join" },
  joined: { label: "Joined", tone: "indigo", hint: "Has an account — email not confirmed yet" },
  verified: { label: "Verified", tone: "green", hint: "Has an account with a confirmed email" },
} as const;

/** "Beatrice Smith" from their account (the last name is left out when empty). */
const fullName = (m: Member) => [m.first_name, m.last_name].filter(Boolean).join(" ");

/** Everyone in the house, with adding and inviting on top. With `manage` (Household settings,
 * admins only): promote and remove too. Only people with a confirmed email can be admins. */
export function PeopleTab({ manage = false }: { manage?: boolean }) {
  const household = useCurrentHousehold();
  const isAdmin = manage && household.my_role === "admin";
  const remove = useRemoveMember();
  const update = useUpdateMember();
  const queryClient = useQueryClient();
  // Emailed invites, listed with everyone until they join.
  const invitesKey = ["email-invites", household.id];
  const invites = useQuery({ queryKey: invitesKey, queryFn: () => householdsApi.pendingInvites(household.id) });
  const cancel = useMutation({
    mutationFn: householdsApi.cancelInvite,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: invitesKey }),
  });
  const added = new Set(household.members.map((m) => m.email));
  const pending = (invites.data ?? []).filter((p) => !added.has(p.email));

  return (
    <div className="space-y-4">
      {isAdmin && <InvitePanel house={household} />}

      <ErrorText error={remove.error ?? update.error ?? cancel.error} />
      <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-white/70 bg-white/90 shadow-sm ring-1 ring-slate-900/5 backdrop-blur">
        {household.members.map((m) => (
          <li key={m.id} className="flex items-center gap-3 px-4 py-3 transition hover:bg-indigo-50/40">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-linear-to-br from-indigo-400 to-fuchsia-500 text-sm font-semibold text-white shadow-sm">
              {m.display_name.slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{m.display_name}</span>
                {m.id === household.my_member_id && <Badge>You</Badge>}
                {m.role === "admin" && <Badge tone="indigo">Admin</Badge>}
                <Badge tone={STATUS[m.status].tone}>{STATUS[m.status].label}</Badge>
              </div>
              <p className="text-xs text-slate-500">
                {[fullName(m) !== m.display_name ? fullName(m) : null, m.email, m.phone].filter(Boolean).join(" · ") ||
                  STATUS[m.status].hint}
              </p>
            </div>
            {isAdmin && m.id !== household.my_member_id && (
              <div className="flex gap-2">
                {(m.role === "admin" || m.status === "verified") && (
                  <Button
                    variant="ghost"
                    disabled={update.isPending}
                    onClick={() => update.mutate({ id: m.id, role: m.role === "admin" ? "member" : "admin" })}
                  >
                    {m.role === "admin" ? "Make member" : "Make admin"}
                  </Button>
                )}
                <Button
                  variant="danger"
                  disabled={remove.isPending}
                  onClick={() => confirm(`Remove ${m.display_name} from the house and all rotations?`) && remove.mutate(m.id)}
                >
                  Remove
                </Button>
              </div>
            )}
          </li>
        ))}
        {pending.map((p) => (
          <li key={p.id} className="flex items-center gap-3 px-4 py-3 transition hover:bg-indigo-50/40">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-200 text-sm font-semibold text-slate-600 shadow-sm">
              {p.email.slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate font-medium">{p.email}</span>
                <Badge tone="amber">Invited</Badge>
              </div>
              <p className="text-xs text-slate-500">
                {p.invited_by ? `Invited by ${p.invited_by.display_name}` : "Invited"} · waiting to join
              </p>
            </div>
            {p.can_cancel && (
              <Button variant="ghost" disabled={cancel.isPending} onClick={() => cancel.mutate(p.id)}>
                Cancel
              </Button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
