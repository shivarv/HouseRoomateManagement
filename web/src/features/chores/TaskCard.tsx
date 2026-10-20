import { Badge, Button } from "../../components/ui";
import { formatDay } from "../../lib/format";
import type { Task } from "../../types/api";
import { useToggleTask } from "./hooks";

export function TaskCard({ task, canToggle, showHousehold = false, overdue = false }: {
  task: Task;
  canToggle: boolean;
  showHousehold?: boolean;
  overdue?: boolean;
}) {
  const toggle = useToggleTask();
  const done = task.status === "done";

  return (
    <div
      className={`flex items-center gap-4 rounded-xl border bg-white p-4 shadow-sm ${
        task.is_mine && !done ? "border-indigo-300 ring-1 ring-indigo-100" : "border-slate-200"
      }`}
    >
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-lg ${done ? "bg-emerald-100" : "bg-indigo-50"}`}>
        {done ? "✓" : choreIcon(task.chore.name)}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`font-medium ${done ? "text-slate-400 line-through" : ""}`}>{task.chore.name}</span>
          {overdue && <Badge tone="amber">Overdue · {formatDay(task.due_date)}</Badge>}
          {task.is_mine && !overdue && <Badge tone="indigo">You</Badge>}
        </div>
        <p className="truncate text-sm text-slate-500">
          {task.is_mine ? "Assigned to you" : task.member.display_name}
          {showHousehold && ` · ${task.household_name}`}
          {task.next_assignee && ` · Next: ${task.next_assignee.display_name}`}
        </p>
      </div>
      {canToggle && (
        <Button
          variant={done ? "secondary" : "primary"}
          disabled={toggle.isPending}
          onClick={() => toggle.mutate({ id: task.id, done: !done })}
        >
          {done ? "Undo" : "Mark done"}
        </Button>
      )}
    </div>
  );
}

function choreIcon(name: string): string {
  const n = name.toLowerCase();
  if (n.includes("cook")) return "🍳";
  if (n.includes("garbage") || n.includes("trash")) return "🗑️";
  if (n.includes("clean") || n.includes("hall")) return "🧹";
  return "📋";
}
