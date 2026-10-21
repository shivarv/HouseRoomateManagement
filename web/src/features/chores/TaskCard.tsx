import { Badge, Button } from "../../components/ui";
import { formatDay } from "../../lib/format";
import type { Task } from "../../types/api";
import { DoneMenu } from "./DoneMenu";
import { useCompleteTask, useReopenTask } from "./hooks";

export function TaskCard({ task, showHousehold = false, overdue = false }: {
  task: Task;
  showHousehold?: boolean;
  overdue?: boolean;
}) {
  const complete = useCompleteTask();
  const reopen = useReopenTask();
  const busy = complete.isPending || reopen.isPending;
  const done = task.status === "done";
  const weekly = task.chore.frequency === "weekly";
  const covered = done && task.completed_by && task.completed_by.id !== task.member.id;

  const whose = task.is_mine ? "your turn" : `${task.member.display_name}'s turn`;
  const who = whose.charAt(0).toUpperCase() + whose.slice(1);
  const parts = [
    done ? `Done by ${task.completed_by?.display_name ?? task.member.display_name}${covered ? ` · ${whose}` : ""}` : who,
    weekly && !done ? `any day until ${formatDay(task.period_end)}` : null,
    showHousehold ? task.household_name : null,
    task.next_assignee ? `Next: ${task.next_assignee.display_name}` : null,
  ].filter(Boolean);

  return (
    <div
      className={`card-hover group relative flex items-center gap-4 rounded-2xl border bg-white/90 p-4 shadow-sm backdrop-blur ${
        task.is_mine && !done ? "border-indigo-200 ring-1 ring-indigo-100" : "border-white/70 ring-1 ring-slate-900/5"
      }`}
    >
      {(task.is_mine || done || overdue) && (
        <span
          className={`absolute inset-y-0 left-0 w-1 rounded-l-2xl ${
            done ? "bg-emerald-400" : overdue ? "bg-linear-to-b from-amber-400 to-orange-500" : "bg-linear-to-b from-indigo-500 to-fuchsia-500"
          }`}
        />
      )}
      <ChoreAvatar name={task.chore.name} done={done} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`font-medium ${done ? "text-slate-400 line-through" : ""}`}>{task.chore.name}</span>
          {weekly && <Badge>This week</Badge>}
          {overdue && <Badge tone="amber">Missed · {formatDay(task.due_date)}</Badge>}
          {task.is_mine && !overdue && !done && <Badge tone="indigo">You</Badge>}
          {covered && <Badge tone="green">Covered</Badge>}
        </div>
        <p className="truncate text-sm text-slate-500">{parts.join(" · ")}</p>
      </div>
      {done ? (
        <Button variant="secondary" disabled={busy} onClick={() => reopen.mutate(task.id)}>
          Undo
        </Button>
      ) : (
        <DoneMenu
          householdId={task.household_id}
          label={task.is_mine ? "Mark done" : "I did it"}
          disabled={busy}
          onDone={(memberId) => complete.mutate({ id: task.id, completedBy: memberId })}
        />
      )}
    </div>
  );
}

/** Colour-coded gradient tile per kind of chore. */
function choreTone(name: string): string {
  const n = name.toLowerCase();
  if (n.includes("cook")) return "from-amber-300 to-orange-500 shadow-orange-500/30";
  if (n.includes("garbage") || n.includes("trash")) return "from-emerald-300 to-teal-500 shadow-teal-500/30";
  if (n.includes("bath")) return "from-violet-300 to-purple-500 shadow-purple-500/30";
  if (n.includes("clean") || n.includes("hall")) return "from-sky-300 to-blue-500 shadow-blue-500/30";
  return "from-indigo-300 to-indigo-500 shadow-indigo-500/30";
}

export function ChoreAvatar({ name, done = false }: { name: string; done?: boolean }) {
  return (
    <div
      className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-linear-to-br text-xl text-white shadow-md transition-transform duration-200 group-hover:scale-110 group-hover:-rotate-3 ${
        done ? "from-emerald-400 to-green-500 shadow-emerald-500/30" : choreTone(name)
      }`}
    >
      {done ? "✓" : choreIcon(name)}
    </div>
  );
}

export function choreIcon(name: string): string {
  const n = name.toLowerCase();
  if (n.includes("cook")) return "🍳";
  if (n.includes("garbage") || n.includes("trash")) return "🗑️";
  if (n.includes("bath")) return "🛁";
  if (n.includes("clean") || n.includes("hall")) return "🧹";
  return "📋";
}
