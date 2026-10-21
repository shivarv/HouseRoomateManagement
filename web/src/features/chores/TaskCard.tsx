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
      className={`flex items-center gap-4 rounded-xl border bg-white p-4 shadow-sm ${
        task.is_mine && !done ? "border-indigo-300 ring-1 ring-indigo-100" : "border-slate-200"
      }`}
    >
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

export function ChoreAvatar({ name, done = false }: { name: string; done?: boolean }) {
  return (
    <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg ${done ? "bg-emerald-100" : "bg-indigo-50"}`}>
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
