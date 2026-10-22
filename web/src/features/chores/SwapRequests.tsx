import { useState, type ReactNode } from "react";
import { ApiError } from "../../api/client";
import { Button } from "../../components/ui";
import { formatDay } from "../../lib/format";
import type { Swap } from "../../types/api";
import { useAcceptSwap } from "./hooks";

const HIDDEN_KEY = "roommate.hiddenSwaps";

/** "Not me" only hides a request in this browser; nothing is sent, others still see it. */
function readHidden(): string[] {
  try {
    return JSON.parse(localStorage.getItem(HIDDEN_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function writeHidden(ids: string[]) {
  try {
    localStorage.setItem(HIDDEN_KEY, JSON.stringify(ids.slice(-100)));
  } catch {
    // Storage unavailable (private mode): hiding just won't survive a reload.
  }
}

type Outcome =
  | { kind: "won"; swap: Swap }
  | { kind: "lost"; swap: Swap; message: string } // someone else got there first
  | { kind: "failed"; swap: Swap; message: string }; // network or other error: can retry

function turnLabel(swap: Swap, date = swap.given_date) {
  return swap.chore.frequency === "weekly" ? `week of ${formatDay(date)}` : formatDay(date);
}

/** Swap requests I can take. The first person to accept wins; the server decides who that is. */
export function SwapRequests({ swaps, showHousehold = false }: { swaps: Swap[]; showHousehold?: boolean }) {
  const accept = useAcceptSwap();
  const [hidden, setHidden] = useState(readHidden);
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});

  const offers = swaps.filter((s) => s.can_accept && !hidden.includes(s.id) && !outcomes[s.id]);
  // Keep showing results after the request drops out of the open list.
  const results = Object.values(outcomes);
  if (offers.length === 0 && results.length === 0) return null;

  const take = (swap: Swap) =>
    accept.mutate(swap.id, {
      onSuccess: (result) => setOutcomes((o) => ({ ...o, [swap.id]: { kind: "won", swap: result } })),
      onError: (error) =>
        setOutcomes((o) => ({
          ...o,
          [swap.id]:
            error instanceof ApiError && error.status === 409
              ? { kind: "lost", swap, message: error.message }
              : {
                  kind: "failed",
                  swap,
                  message: error instanceof ApiError ? error.message : "Couldn't reach the server, try again",
                },
        })),
    });
  const hide = (id: string) => {
    const next = [...hidden, id];
    setHidden(next);
    writeHidden(next);
  };
  const dismiss = (id: string) =>
    setOutcomes((o) => {
      const { [id]: _, ...rest } = o;
      return rest;
    });

  return (
    <section className="mb-8 space-y-2">
      <h2 className="section-title">Swap requests</h2>
      {results.map((r) =>
        r.kind === "won" ? (
          <Row key={r.swap.id} tone="green" onDismiss={() => dismiss(r.swap.id)}>
            🤝 You took <strong>{r.swap.requester.display_name}</strong>'s {r.swap.chore.name} ({turnLabel(r.swap)}).{" "}
            {r.swap.requester.display_name} does your turn on{" "}
            <strong>{r.swap.payback_date ? turnLabel(r.swap, r.swap.payback_date) : "your next turn"}</strong>.
          </Row>
        ) : r.kind === "lost" ? (
          <Row key={r.swap.id} tone="slate" onDismiss={() => dismiss(r.swap.id)}>
            {r.swap.requester.display_name}'s {r.swap.chore.name} ({turnLabel(r.swap)}): {r.message}
          </Row>
        ) : (
          <Row key={r.swap.id} tone="red" onDismiss={() => dismiss(r.swap.id)}>
            {r.message}
            <Button
              variant="secondary"
              className="ml-2 py-1"
              onClick={() => {
                dismiss(r.swap.id);
                take(r.swap); // safe to retry: accepting twice returns the same result
              }}
            >
              Try again
            </Button>
          </Row>
        ),
      )}
      {offers.map((swap) => {
        const pending = accept.isPending && accept.variables === swap.id;
        return (
          <div
            key={swap.id}
            className="flex flex-wrap items-center gap-3 rounded-2xl border border-indigo-100 bg-white/90 p-4 shadow-sm ring-1 ring-indigo-50"
          >
            <span className="text-xl">🔁</span>
            <div className="min-w-0 flex-1 text-sm">
              <p className="text-slate-800">
                <strong>{swap.requester.display_name}</strong> needs someone for <strong>{swap.chore.name}</strong> ·{" "}
                {turnLabel(swap)}
                {showHousehold && ` · ${swap.household_name}`}
                {swap.note && <span className="text-slate-500"> — “{swap.note}”</span>}
              </p>
              {swap.payback_preview && (
                <p className="text-xs text-slate-500">
                  You'd give back your {swap.chore.name} turn on{" "}
                  <span className="font-semibold text-slate-700">{turnLabel(swap, swap.payback_preview)}</span>.
                </p>
              )}
            </div>
            <div className="flex shrink-0 gap-2">
              <Button variant="ghost" disabled={pending} onClick={() => hide(swap.id)}>
                Not me
              </Button>
              <Button disabled={pending} onClick={() => take(swap)}>
                {pending ? "Taking…" : "I'll take it"}
              </Button>
            </div>
          </div>
        );
      })}
    </section>
  );
}

function Row({ tone, onDismiss, children }: { tone: "green" | "slate" | "red"; onDismiss: () => void; children: ReactNode }) {
  const tones = {
    green: "bg-emerald-50 text-emerald-800 ring-emerald-200",
    slate: "bg-slate-50 text-slate-600 ring-slate-200",
    red: "bg-red-50 text-red-700 ring-red-100",
  };
  return (
    <div className={`flex items-center gap-2 rounded-2xl px-4 py-3 text-sm ring-1 ${tones[tone]}`}>
      <div className="flex-1">{children}</div>
      <button className="text-lg leading-none opacity-60 transition hover:opacity-100" aria-label="Dismiss" onClick={onDismiss}>
        ×
      </button>
    </div>
  );
}
