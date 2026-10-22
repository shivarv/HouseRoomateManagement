import { useState, type FormEvent } from "react";
import { Badge, Button, Card, ErrorText, Input } from "../../components/ui";
import { useAddMember, useRemoveMember, useUpdateMember } from "../../features/households/hooks";
import { useCurrentHousehold } from "./HouseholdLayout";

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
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{m.display_name}</span>
                {m.id === household.my_member_id && <Badge>You</Badge>}
                {m.role === "admin" && <Badge tone="indigo">Admin</Badge>}
              </div>
              <p className="text-xs text-slate-500">{m.has_account ? "Has an account" : "No account yet"}</p>
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
