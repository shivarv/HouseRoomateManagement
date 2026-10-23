import { useState } from "react";
import { useSearchParams } from "react-router";
import { ApiError } from "../api/client";
import { Badge, Button, Empty, ErrorText, Loading, PageTitle } from "../components/ui";
import { HelpForm } from "../features/help/HelpForm";
import { useHelpRequests, useMarkHelpDone, useReopenHelp, useWithdrawHelp } from "../features/help/hooks";
import { helpIcon } from "../features/help/presets";
import { useHouseholds } from "../features/households/hooks";
import { formatTime, localIsoDate, relativeDay } from "../lib/format";
import type { HelpRequest } from "../types/api";

type Notice = { message: string; lost: boolean }; // lost: someone else got there first (409)

function when(iso: string): string {
  return `${relativeDay(localIsoDate(new Date(iso)), localIsoDate())}, ${formatTime(iso)}`;
}

/** Per-card messages, kept above the cards: a card moves between sections when its status changes. */
function useNotices() {
  const [notices, setNotices] = useState<Record<string, Notice>>({});
  const setNotice = (id: string, notice: Notice | null) =>
    setNotices(({ [id]: _, ...rest }) => (notice ? { ...rest, [id]: notice } : rest));
  return { notices, setNotice };
}

type Filter = "all" | "mine";

/**
 * 🔔 Notifications: everything asked in my houses, with Ask for help on top. "All" is the feed:
 * others' requests can be marked done, my own only withdrawn. "Mine" is what I asked for, where I
 * can also edit them and mark them done.
 */
export function NotificationsPage() {
  const households = useHouseholds();
  const help = useHelpRequests();
  const { notices, setNotice } = useNotices();
  const [params, setParams] = useSearchParams();
  const filter: Filter = params.get("filter") === "mine" ? "mine" : "all";
  const [asking, setAsking] = useState(false);
  const [editing, setEditing] = useState<HelpRequest | null>(null);

  if (households.isLoading || help.isLoading) return <Loading />;
  const all = help.data ?? [];
  const shown = filter === "mine" ? all.filter((r) => r.is_mine) : all;
  const open = shown.filter((r) => r.status === "open");
  const done = shown.filter((r) => r.status === "done");
  const multiHouse = (households.data?.length ?? 0) > 1;
  const noHouse = households.data?.length === 0;
  const mineOpen = all.filter((r) => r.is_mine && r.status === "open").length;
  const card = (r: HelpRequest) => (
    <HelpCard
      key={r.id}
      req={r}
      inFeed={filter === "all"}
      showHousehold={multiHouse}
      onEdit={filter === "mine" ? setEditing : undefined}
      notice={notices[r.id]}
      setNotice={(n) => setNotice(r.id, n)}
    />
  );
  const tab = (value: Filter, label: string) => (
    <button
      key={value}
      onClick={() => setParams(value === "all" ? {} : { filter: value }, { replace: true })}
      className={`rounded-xl px-3.5 py-1.5 text-sm font-semibold transition ${
        filter === value ? "bg-linear-to-r from-indigo-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30" : "text-slate-600 hover:bg-white/70"
      }`}
    >
      {label}
    </button>
  );

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <PageTitle title="Notifications" subtitle="What your roommates need, and what you've asked for. Help out, then mark it done." />
        {!noHouse && !asking && !editing && <Button onClick={() => setAsking(true)}>🙋 Ask for help</Button>}
      </div>
      <ErrorText error={help.error} />
      {noHouse && <Empty>Join a household first, then you can ask your roommates for help.</Empty>}
      {(asking || editing) && households.data && (
        <div className="mb-8">
          <HelpForm
            key={editing?.id ?? "new"}
            households={households.data}
            editing={editing ?? undefined}
            onDone={() => {
              setAsking(false);
              setEditing(null);
            }}
          />
        </div>
      )}

      {!noHouse && (
        <>
          <div className="mb-6 inline-flex gap-1 rounded-2xl bg-slate-100/80 p-1">
            {tab("all", "All")}
            {tab("mine", mineOpen ? `Asked by me · ${mineOpen}` : "Asked by me")}
          </div>
          <div className="space-y-8">
            <section className="space-y-3">
              <h2 className="section-title">
                {filter === "mine" ? "Waiting for help" : "Needs a hand"} · {open.length}
              </h2>
              {open.length === 0 ? (
                <Empty>{filter === "mine" ? "Nothing open. Use “🙋 Ask for help” when you need a hand." : "Nobody needs help right now 🎉"}</Empty>
              ) : (
                open.map(card)
              )}
            </section>
            {done.length > 0 && (
              <section className="space-y-3">
                <h2 className="section-title">{filter === "mine" ? `Done · ${done.length}` : "Recently done"}</h2>
                {done.map(card)}
              </section>
            )}
          </div>
        </>
      )}
    </>
  );
}

function HelpCard({
  req,
  inFeed = false,
  showHousehold,
  onEdit,
  notice,
  setNotice,
}: {
  req: HelpRequest;
  /** The "All" feed: my own requests can only be withdrawn there, not marked done. */
  inFeed?: boolean;
  showHousehold: boolean;
  onEdit?: (r: HelpRequest) => void;
  notice?: Notice;
  setNotice: (n: Notice | null) => void;
}) {
  const done = useMarkHelpDone();
  const reopen = useReopenHelp();
  const withdraw = useWithdrawHelp();
  const busy = done.isPending || reopen.isPending || withdraw.isPending;
  const isDone = req.status === "done";
  // The list refetches after every answer, so a 409 just says what happened.
  const handlers = {
    onSuccess: () => setNotice(null),
    onError: (error: Error) =>
      setNotice({ message: error.message, lost: error instanceof ApiError && error.status === 409 }),
  };

  return (
    <div
      className={`card-hover relative rounded-2xl border bg-white/90 p-4 shadow-sm backdrop-blur ${
        req.is_mine && !isDone ? "border-indigo-200 ring-1 ring-indigo-100" : "border-white/70 ring-1 ring-slate-900/5"
      }`}
    >
      <div className="flex items-start gap-4">
        <div
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-xl shadow-md ${
            isDone ? "bg-linear-to-br from-emerald-400 to-green-500 text-white shadow-emerald-500/30" : "bg-linear-to-br from-amber-200 to-orange-400 shadow-orange-500/30"
          }`}
        >
          {isDone ? "✓" : helpIcon(req.title)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`font-medium ${isDone ? "text-slate-400 line-through" : ""}`}>{req.title}</span>
            {isDone ? <Badge tone="green">Done</Badge> : <Badge tone="amber">Open</Badge>}
            {req.is_mine && <Badge tone="indigo">You asked</Badge>}
          </div>
          {req.details && <p className="mt-0.5 text-sm text-slate-700">{req.details}</p>}
          <p className="mt-1 text-xs text-slate-500">
            {req.is_mine ? "You" : req.requester.display_name} asked · {when(req.created_at)}
            {showHousehold && ` · ${req.household_name}`}
            {isDone && req.done_by && req.done_at && (
              <span className="font-medium text-emerald-700">
                {" "}· Done by {req.done_by.display_name} · {when(req.done_at)}
              </span>
            )}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap justify-end gap-2">
          {!isDone && req.is_mine && (
            <>
              {onEdit && (
                <Button variant="ghost" disabled={busy} onClick={() => onEdit(req)}>
                  Edit
                </Button>
              )}
              <Button
                variant="ghost"
                disabled={busy}
                onClick={() => confirm(`Withdraw “${req.title}”?`) && withdraw.mutate(req.id, handlers)}
              >
                Withdraw
              </Button>
            </>
          )}
          {!isDone && !(inFeed && req.is_mine) && (
            <Button disabled={busy} onClick={() => done.mutate(req.id, handlers)}>
              {done.isPending ? "Saving…" : req.is_mine ? "Mark done" : "I helped ✓"}
            </Button>
          )}
          {isDone && req.can_reopen && (
            <Button variant="secondary" disabled={busy} onClick={() => reopen.mutate(req.id, handlers)}>
              Undo
            </Button>
          )}
        </div>
      </div>
      {notice && (
        <div
          className={`mt-3 flex items-center gap-2 rounded-xl px-3 py-2 text-sm ring-1 ${
            notice.lost ? "bg-slate-50 text-slate-600 ring-slate-200" : "bg-red-50 text-red-700 ring-red-100"
          }`}
        >
          <span className="flex-1">{notice.message}</span>
          <button className="opacity-60 hover:opacity-100" aria-label="Dismiss" onClick={() => setNotice(null)}>
            ×
          </button>
        </div>
      )}
    </div>
  );
}
