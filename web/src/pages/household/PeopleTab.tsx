import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { householdsApi } from "../../api/households";
import { Badge, Button, Card, ErrorText, Input } from "../../components/ui";
import { useAddMember, useRemoveMember, useUpdateMember } from "../../features/households/hooks";
import { InvitePanel } from "../../features/households/InvitePanel";
import type { Member } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

const STATUS = {
  added: { label: "Added", tone: "slate", hint: "Added by name — invite them to join" },
  invited: { label: "Invited", tone: "amber", hint: "Invite sent — waiting for them to join" },
  joined: { label: "Joined", tone: "green", hint: "Has an account" },
} as const;

/** "Beatrice Smith" from their account (the last name is left out when empty). */
const fullName = (m: Member) => [m.first_name, m.last_name].filter(Boolean).join(" ");

/** Admins: an email and phone for someone who hasn't joined, and an email invite to them. */
function ContactEditor({ member, householdId }: { member: Member; householdId: string }) {
  const update = useUpdateMember();
  const queryClient = useQueryClient();
  const [email, setEmail] = useState(member.email ?? "");
  const [phone, setPhone] = useState(member.phone ?? "");
  const invite = useMutation({
    mutationFn: () => householdsApi.emailInvites(householdId, [email.trim()]),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  const changed = email.trim() !== (member.email ?? "") || phone.trim() !== (member.phone ?? "");
  const field =
    "rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs outline-none transition focus:border-indigo-400";

  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <input className={`${field} w-52`} type="email" placeholder="Email (optional)" value={email} onChange={(e) => setEmail(e.target.value)} aria-label={`${member.display_name}'s email`} />
      <input className={`${field} w-36`} type="tel" placeholder="Phone (optional)" value={phone} onChange={(e) => setPhone(e.target.value)} aria-label={`${member.display_name}'s phone`} />
      {changed && (
        <Button variant="secondary" disabled={update.isPending} onClick={() => update.mutate({ id: member.id, email: email.trim(), phone: phone.trim() })}>
          Save
        </Button>
      )}
      {!changed && member.email && member.status !== "joined" && (
        <Button variant="ghost" disabled={invite.isPending} onClick={() => invite.mutate()}>
          {invite.isSuccess ? "✓ Invited" : member.status === "invited" ? "Invite again" : "✉️ Send invite"}
        </Button>
      )}
      <ErrorText error={update.error ?? invite.error} />
    </div>
  );
}

/** Everyone in the house. With `manage` (Household settings, admins only): add, promote, remove. */
export function PeopleTab({ manage = false }: { manage?: boolean }) {
  const household = useCurrentHousehold();
  const isAdmin = manage && household.my_role === "admin";
  const add = useAddMember(household.id);
  const remove = useRemoveMember();
  const update = useUpdateMember();
  const [name, setName] = useState("");

  const onAdd = (e: FormEvent) => {
    e.preventDefault();
    add.mutate(name.trim(), { onSuccess: () => setName("") });
  };

  return (
    <div className="space-y-4">
      {!manage && <InvitePanel house={household} />}
      {isAdmin && (
        <Card>
          <h2 className="mb-1 font-semibold">Add a roommate</h2>
          <p className="mb-3 text-sm text-slate-500">
            New people join the end of every chore rotation. They can claim their name later with the invite code
            <Badge tone="indigo">{household.invite_code}</Badge>.
          </p>
          <form onSubmit={onAdd} className="flex gap-2">
            <Input placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
            <Button type="submit" disabled={add.isPending}>Add</Button>
          </form>
          <div className="mt-2"><ErrorText error={add.error} /></div>
        </Card>
      )}

      <ErrorText error={remove.error ?? update.error} />
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
              {isAdmin && !m.has_account && <ContactEditor member={m} householdId={household.id} />}
            </div>
            {isAdmin && m.id !== household.my_member_id && (
              <div className="flex gap-2">
                <Button
                  variant="ghost"
                  disabled={update.isPending}
                  onClick={() => update.mutate({ id: m.id, role: m.role === "admin" ? "member" : "admin" })}
                >
                  {m.role === "admin" ? "Make member" : "Make admin"}
                </Button>
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
      </ul>
    </div>
  );
}
