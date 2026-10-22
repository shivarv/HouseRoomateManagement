import { useState } from "react";
import { Badge, Button, ErrorText } from "../../components/ui";
import { formatDay } from "../../lib/format";
import type { Task } from "../../types/api";
import { DoneMenu, type MenuAction } from "./DoneMenu";
import { useAskSwap, useCancelSwap, useCompleteTask, useReopenTask } from "./hooks";

export function TaskCard({ task, showHousehold = false, overdue = false }: {
  task: Task;
  showHousehold?: boolean;
  overdue?: boolean;
}) {
  const complete = useCompleteTask();
  const reopen = useReopenTask();
  const cancelSwap = useCancelSwap();
  const [asking, setAsking] = useState(false);
  const busy = complete.isPending || reopen.isPending || cancelSwap.isPending;
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

  const actions: MenuAction[] = [];
  if (task.is_mine && !overdue && !task.swap_request_id) {
    actions.push({ label: "⇄ Ask for a swap", title: "Ask the house to take this turn", onClick: () => setAsking(true) });
  }
  if (task.is_mine && task.swap_request_id) {
    const id = task.swap_request_id;
    actions.push({ label: "Cancel swap request", onClick: () => cancelSwap.mutate(id) });
  }
  if (task.swap?.can_cancel) {
    const id = task.swap.id;
    actions.push({ label: "Cancel swap", title: "Both turns go back to who had them before", onClick: () => cancelSwap.mutate(id) });
  }

  return (
    <div
      className={`card-hover group relative rounded-2xl border bg-white/90 p-4 shadow-sm backdrop-blur has-[[data-open]]:z-10 ${
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
      <div className="flex items-center gap-4">
        <ChoreAvatar name={task.chore.name} done={done} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`font-medium ${done ? "text-slate-400 line-through" : ""}`}>{task.chore.name}</span>
            {weekly && <Badge>This week</Badge>}
            {overdue && <Badge tone="amber">Missed · {formatDay(task.due_date)}</Badge>}
            {task.is_mine && !overdue && !done && <Badge tone="indigo">You</Badge>}
            {covered && <Badge tone="green">Covered</Badge>}
            {task.swap && (
              <Badge tone="indigo">
                {task.swap.role === "given" ? `⇄ from ${task.swap.other.display_name}` : `⇄ paying back ${task.swap.other.display_name}`}
              </Badge>
            )}
            {task.swap_request_id && !done && <Badge tone="amber">Swap requested · waiting</Badge>}
          </div>
          <p className="truncate text-sm text-slate-500">{parts.join(" · ")}</p>
        </div>
        {done ? (
          <Button variant="secondary" disabled={busy} onClick={() => reopen.mutate(task.id)}>
            Undo
          </Button>
        ) : (
          <div className="flex shrink-0 items-center gap-2">
            {!task.is_mine && (
              <Button
                variant="secondary"
                disabled={busy}
                onClick={() => complete.mutate({ id: task.id, completedBy: task.member.id })}
                title={`${task.member.display_name} did it`}
              >
                It's done
              </Button>
            )}
            <DoneMenu
              householdId={task.household_id}
              label={task.is_mine ? "Mark done" : "I did it"}
              disabled={busy}
              onDone={(memberId) => complete.mutate({ id: task.id, completedBy: memberId })}
              actions={actions}
            />
          </div>
        )}
      </div>
      {cancelSwap.error && (
        <div className="mt-3">
          <ErrorText error={cancelSwap.error} />
        </div>
      )}
      {asking && <AskSwapPanel task={task} onClose={() => setAsking(false)} />}
    </div>
  );
}

/** Confirm sheet for "Ask for a swap": the whole house sees the request, first yes wins. */
function AskSwapPanel({ task, onClose }: { task: Task; onClose: () => void }) {
  const ask = useAskSwap();
  const [note, setNote] = useState("");
  const when = task.chore.frequency === "weekly" ? `week of ${formatDay(task.due_date)}` : formatDay(task.due_date);
  return (
    <form
      className="mt-4 space-y-3 rounded-xl border border-indigo-100 bg-indigo-50/60 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        ask.mutate({ choreId: task.chore.id, dueDate: task.due_date, note: note.trim() }, { onSuccess: onClose });
      }}
    >
      <div>
        <p className="text-sm font-semibold text-slate-800">
          Swap {task.chore.name} · {when}?
        </p>
        <p className="text-xs text-slate-600">
          Everyone in the house sees this. Whoever accepts first takes this turn, and you'll do their next{" "}
          {task.chore.name} turn in return.
        </p>
      </div>
      <input
        className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15"
        placeholder="Optional note, e.g. travelling"
        maxLength={200}
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <ErrorText error={ask.error} />
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onClose}>
          Never mind
        </Button>
        <Button type="submit" disabled={ask.isPending}>
          {ask.isPending ? "Sending…" : "Send to the house"}
        </Button>
      </div>
    </form>
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
