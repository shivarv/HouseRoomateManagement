import { useState, type FormEvent } from "react";
import { Badge, Button, Card, Empty, ErrorText, Input, Loading } from "../../components/ui";
import { useChores, useCreateChore, useDeleteChore, useSetRotation, useUpdateChore } from "../../features/chores/hooks";
import type { Chore, MemberBrief } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

export function ChoresTab() {
  const household = useCurrentHousehold();
  const chores = useChores(household.id);
  const create = useCreateChore(household.id);
  const isAdmin = household.my_role === "admin";
  const [name, setName] = useState("");

  const onCreate = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(name.trim(), { onSuccess: () => setName("") });
  };

  if (chores.isLoading) return <Loading />;

  return (
    <div className="space-y-4">
      <ErrorText error={chores.error} />
      {chores.data?.length === 0 && <Empty>No chores yet.</Empty>}
      {chores.data?.map((c) => <ChoreCard key={c.id} chore={c} isAdmin={isAdmin} />)}
      {isAdmin && (
        <Card>
          <h2 className="mb-3 font-semibold">Add a chore</h2>
          <form onSubmit={onCreate} className="flex gap-2">
            <Input placeholder="e.g. Clean bathroom" value={name} onChange={(e) => setName(e.target.value)} required />
            <Button type="submit" disabled={create.isPending}>Add</Button>
          </form>
          <div className="mt-2"><ErrorText error={create.error} /></div>
        </Card>
      )}
    </div>
  );
}

function ChoreCard({ chore, isAdmin }: { chore: Chore; isAdmin: boolean }) {
  const household = useCurrentHousehold();
  const [editing, setEditing] = useState(false);
  const update = useUpdateChore();
  const remove = useDeleteChore();

  return (
    <Card className={chore.is_active ? "" : "opacity-60"}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">{chore.name}</h3>
        <Badge>Daily · round-robin</Badge>
        {!chore.is_active && <Badge tone="amber">Paused</Badge>}
        {isAdmin && !editing && (
          <div className="ml-auto flex gap-2">
            <Button variant="secondary" onClick={() => setEditing(true)}>Edit order</Button>
            <Button variant="ghost" disabled={update.isPending} onClick={() => update.mutate({ id: chore.id, is_active: !chore.is_active })}>
              {chore.is_active ? "Pause" : "Resume"}
            </Button>
            <Button
              variant="danger"
              disabled={remove.isPending}
              onClick={() => confirm(`Delete "${chore.name}" and its history?`) && remove.mutate(chore.id)}
            >
              Delete
            </Button>
          </div>
        )}
      </div>

      {editing ? (
        <RotationEditor chore={chore} everyone={household.members} onDone={() => setEditing(false)} />
      ) : chore.rotation.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">Nobody in the rotation yet.</p>
      ) : (
        <ol className="mt-3 flex flex-wrap items-center gap-1.5 text-sm">
          {chore.rotation.map((m, i) => (
            <li key={m.id} className="flex items-center gap-1.5">
              <span
                className={`rounded-full px-2.5 py-1 ${
                  chore.today_assignee?.id === m.id ? "bg-indigo-600 text-white" : "bg-slate-100 text-slate-700"
                }`}
                title={chore.today_assignee?.id === m.id ? "Today" : undefined}
              >
                {i + 1}. {m.display_name}
              </span>
              {i < chore.rotation.length - 1 && <span className="text-slate-300">→</span>}
            </li>
          ))}
          <span className="ml-1 text-slate-400">↺ repeats</span>
        </ol>
      )}
    </Card>
  );
}

function RotationEditor({ chore, everyone, onDone }: { chore: Chore; everyone: MemberBrief[]; onDone: () => void }) {
  const save = useSetRotation();
  const [order, setOrder] = useState<MemberBrief[]>(chore.rotation);
  const excluded = everyone.filter((m) => !order.some((o) => o.id === m.id));

  const move = (index: number, delta: number) => {
    const next = [...order];
    const [item] = next.splice(index, 1);
    next.splice(index + delta, 0, item);
    setOrder(next);
  };

  return (
    <div className="mt-4 space-y-3">
      <ul className="space-y-1.5">
        {order.map((m, i) => (
          <li key={m.id} className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-1.5 text-sm">
            <span className="w-6 text-slate-400">{i + 1}.</span>
            <span className="flex-1 font-medium">{m.display_name}</span>
            <Button variant="ghost" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Move up">↑</Button>
            <Button variant="ghost" disabled={i === order.length - 1} onClick={() => move(i, 1)} aria-label="Move down">↓</Button>
            <Button variant="ghost" onClick={() => setOrder(order.filter((o) => o.id !== m.id))}>Skip</Button>
          </li>
        ))}
      </ul>
      {excluded.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-slate-500">Not in this rotation:</span>
          {excluded.map((m) => (
            <Button key={m.id} variant="secondary" onClick={() => setOrder([...order, m])}>+ {m.display_name}</Button>
          ))}
        </div>
      )}
      <p className="text-xs text-slate-500">Today's person stays the same. The new order applies from tomorrow.</p>
      <ErrorText error={save.error} />
      <div className="flex gap-2">
        <Button
          disabled={save.isPending}
          onClick={() => save.mutate({ id: chore.id, memberIds: order.map((m) => m.id) }, { onSuccess: onDone })}
        >
          Save order
        </Button>
        <Button variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </div>
  );
}
