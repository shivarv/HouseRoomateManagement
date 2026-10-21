import { useState, type FormEvent } from "react";
import type { ChoreSettings } from "../../api/chores";
import { Badge, Button, Card, Empty, ErrorText, Input, Loading } from "../../components/ui";
import { useChores, useCreateChore, useDeleteChore, useSetRotation, useUpdateChore } from "../../features/chores/hooks";
import type { AssignmentMode, Chore, Frequency, MemberBrief } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

const selectClass = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm";

export function ChoresTab() {
  const household = useCurrentHousehold();
  const chores = useChores(household.id);
  const isAdmin = household.my_role === "admin";

  if (chores.isLoading) return <Loading />;

  return (
    <div className="space-y-4">
      <ErrorText error={chores.error} />
      {chores.data?.length === 0 && <Empty>No chores yet.</Empty>}
      {chores.data?.map((c) => <ChoreCard key={c.id} chore={c} isAdmin={isAdmin} />)}
      {isAdmin && <AddChore householdId={household.id} />}
    </div>
  );
}

function AddChore({ householdId }: { householdId: string }) {
  const create = useCreateChore(householdId);
  const [name, setName] = useState("");
  const [settings, setSettings] = useState<Required<Pick<ChoreSettings, "frequency" | "assignment_mode">> & { target_per_week: number | null }>({
    frequency: "daily",
    assignment_mode: "rotation",
    target_per_week: null,
  });

  const onCreate = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      { name: name.trim(), ...settings, target_per_week: settings.assignment_mode === "open" ? settings.target_per_week : null },
      { onSuccess: () => setName("") },
    );
  };

  return (
    <Card>
      <h2 className="mb-1 font-semibold">Add a chore</h2>
      <p className="mb-3 text-sm text-slate-500">Need it twice a day? Add two chores, e.g. "Cooking – Lunch" and "Cooking – Dinner".</p>
      <form onSubmit={onCreate} className="space-y-3">
        <Input placeholder="e.g. Clean bathroom" value={name} onChange={(e) => setName(e.target.value)} required />
        <SettingsFields value={settings} onChange={(v) => setSettings({ ...settings, ...v })} />
        <ErrorText error={create.error} />
        <Button type="submit" disabled={create.isPending}>Add chore</Button>
      </form>
    </Card>
  );
}

function SettingsFields({
  value,
  onChange,
}: {
  value: { frequency: Frequency; assignment_mode: AssignmentMode; target_per_week: number | null };
  onChange: (v: Partial<{ frequency: Frequency; assignment_mode: AssignmentMode; target_per_week: number | null }>) => void;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3 text-sm">
      <label className="space-y-1">
        <span className="block font-medium text-slate-700">How often</span>
        <select className={selectClass} value={value.frequency} onChange={(e) => onChange({ frequency: e.target.value as Frequency })}>
          <option value="daily">Every day</option>
          <option value="weekly">Once a week (any day)</option>
        </select>
      </label>
      <label className="space-y-1">
        <span className="block font-medium text-slate-700">Who does it</span>
        <select
          className={selectClass}
          value={value.assignment_mode}
          onChange={(e) => onChange({ assignment_mode: e.target.value as AssignmentMode })}
        >
          <option value="rotation">Take turns (rotation)</option>
          <option value="open">Anyone — whoever does it logs it</option>
        </select>
      </label>
      {value.assignment_mode === "open" && (
        <label className="space-y-1">
          <span className="block font-medium text-slate-700">Target per week</span>
          <input
            type="number"
            min={1}
            max={100}
            placeholder="optional"
            className={`${selectClass} w-28`}
            value={value.target_per_week ?? ""}
            onChange={(e) => onChange({ target_per_week: e.target.value ? Number(e.target.value) : null })}
          />
        </label>
      )}
    </div>
  );
}

function ChoreCard({ chore, isAdmin }: { chore: Chore; isAdmin: boolean }) {
  const household = useCurrentHousehold();
  const [mode, setMode] = useState<"view" | "order" | "settings">("view");
  const update = useUpdateChore();
  const remove = useDeleteChore();
  const isOpen = chore.assignment_mode === "open";

  return (
    <Card className={chore.is_active ? "" : "opacity-60"}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">{chore.name}</h3>
        <Badge>{chore.frequency === "weekly" ? "Weekly" : "Daily"}</Badge>
        <Badge tone={isOpen ? "green" : "slate"}>{isOpen ? "Anyone" : "Rotation"}</Badge>
        {isOpen && chore.target_per_week && <Badge>{chore.target_per_week}× / week</Badge>}
        {!chore.is_active && <Badge tone="amber">Paused</Badge>}
        {isAdmin && mode === "view" && (
          <div className="ml-auto flex flex-wrap gap-2">
            {!isOpen && <Button variant="secondary" onClick={() => setMode("order")}>Edit order</Button>}
            <Button variant="secondary" onClick={() => setMode("settings")}>Settings</Button>
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

      {mode === "order" && <RotationEditor chore={chore} everyone={household.members} onDone={() => setMode("view")} />}
      {mode === "settings" && <SettingsEditor chore={chore} onDone={() => setMode("view")} />}
      {mode === "view" &&
        (isOpen ? (
          <p className="mt-3 text-sm text-slate-500">Nobody is assigned. Whoever does it taps "I did it"; the Report tab shows who did it how often.</p>
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
                  title={chore.today_assignee?.id === m.id ? (chore.frequency === "weekly" ? "This week" : "Today") : undefined}
                >
                  {i + 1}. {m.display_name}
                </span>
                {i < chore.rotation.length - 1 && <span className="text-slate-300">→</span>}
              </li>
            ))}
            <span className="ml-1 text-slate-400">↺ {chore.frequency === "weekly" ? "one person per week" : "one person per day"}</span>
          </ol>
        ))}
    </Card>
  );
}

function SettingsEditor({ chore, onDone }: { chore: Chore; onDone: () => void }) {
  const update = useUpdateChore();
  const [name, setName] = useState(chore.name);
  const [value, setValue] = useState({
    frequency: chore.frequency,
    assignment_mode: chore.assignment_mode,
    target_per_week: chore.target_per_week,
  });

  const save = () =>
    update.mutate(
      {
        id: chore.id,
        name: name.trim(),
        frequency: value.frequency,
        assignment_mode: value.assignment_mode,
        target_per_week: value.assignment_mode === "open" ? value.target_per_week ?? 0 : undefined,
      },
      { onSuccess: onDone },
    );

  return (
    <div className="mt-4 space-y-3">
      <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} />
      <SettingsFields value={value} onChange={(v) => setValue({ ...value, ...v })} />
      {(value.frequency !== chore.frequency || value.assignment_mode !== chore.assignment_mode) && (
        <p className="text-xs text-amber-700">The change applies from today. History is kept.</p>
      )}
      <ErrorText error={update.error} />
      <div className="flex gap-2">
        <Button disabled={update.isPending || !name.trim()} onClick={save}>Save</Button>
        <Button variant="ghost" onClick={onDone}>Cancel</Button>
      </div>
    </div>
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
      <p className="text-xs text-slate-500">The current person keeps their turn. The new order applies after that.</p>
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
