import { useQueries } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link } from "react-router";
import { reportsApi } from "../../api/chores";
import { Card, ErrorText, Loading } from "../../components/ui";
import { useBills } from "../../features/bills/hooks";
import { choreKeys, useReport, useReportMonths } from "../../features/chores/hooks";
import { useHelpRequests } from "../../features/help/hooks";
import { useShoppingList } from "../../features/shopping/hooks";
import { formatDay, formatMoney } from "../../lib/format";
import type { Bill, BillStatus } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

/*
 * Chart colours: the app's indigo for chores done, amber for missed (a state, always labelled with
 * its number since amber is light on white). Validated as a pair with the dataviz checker.
 */
const DONE = "#6366f1";
const MISSED = "#f59e0b";
/** "0.1", "2.5", "12": small fair shares keep a decimal so they don't read as 0. */
const share = (n: number) => (n < 10 ? n.toFixed(1).replace(/\.0$/, "") : String(Math.round(n)));

/** 📊 Dashboard: the house at a glance this month — chores, fairness, bills, groceries, favours. */
export function DashboardTab() {
  const house = useCurrentHousehold();
  const report = useReport(house.id);
  const bills = useBills(house.id);
  const shopping = useShoppingList(house.id);
  const help = useHelpRequests();

  if (report.isLoading) return <Loading />;
  if (!report.data) return <ErrorText error={report.error} />;
  const r = report.data;

  const totalDone = r.leaderboard.reduce((n, row) => n + row.done, 0);
  const totalMissed = r.leaderboard.reduce((n, row) => n + row.missed, 0);
  const active = r.leaderboard.filter((row) => row.is_active);
  const spread = active.length ? Math.max(...active.map((x) => x.done)) - Math.min(...active.map((x) => x.done)) : 0;
  const billList = (bills.data?.bills ?? []).filter((b) => b.is_active);
  const thisMonth = billList.filter((b) => b.frequency === "monthly");
  const paid = thisMonth.filter((b) => b.current.status === "paid").length;
  const nextDue = billList
    .filter((b) => b.current.status !== "paid")
    .sort((a, b) => a.current.due_date.localeCompare(b.current.due_date))[0];
  const favours = (help.data ?? []).filter((h) => h.household_id === house.id);
  const openFavours = favours.filter((h) => h.status === "open").length;
  const doneFavours = favours.filter((h) => h.status === "done" && h.done_at?.startsWith(r.month)).length;
  const needed = shopping.data?.needed.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Tile label="Chores done" value={totalDone} sub={totalMissed ? `${totalMissed} missed` : "none missed 🎉"} to="../report" />
        <Tile
          label="Fairness"
          value={active.length < 2 ? "—" : spread <= 2 ? "Even" : `±${spread}`}
          sub={active.length < 2 ? "needs 2+ people" : spread <= 2 ? `within ${spread} chore${spread === 1 ? "" : "s"}` : "gap between most & least"}
          to="../report"
        />
        <Tile
          label="Bills this month"
          value={thisMonth.length ? `${paid}/${thisMonth.length}` : "—"}
          sub={nextDue ? `next: ${nextDue.name}, ${formatDay(nextDue.current.due_date)}` : thisMonth.length ? "all paid ✓" : "no monthly bills"}
          to="../../reminders"
        />
        <Tile label="Groceries needed" value={needed} sub={needed ? "on the list now" : "list is empty"} to="../../groceries" />
        <Tile label="Favours" value={openFavours} sub={`open · ${doneFavours} done this month`} to="/notifications" />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Chores by person" subtitle={`This month · fair share ≈ ${share(r.fair_share)} each`} to="../report">
          <PersonBars rows={active.map((x) => ({ name: x.member.display_name, done: x.done }))} fairShare={r.fair_share} />
        </Panel>
        <Panel title="Chores by type" subtitle="Done and missed this month" to="../report" legend>
          <ChoreBars rows={r.chores.filter((c) => c.is_active).map((c) => ({ name: c.chore.name, done: c.total_done, missed: c.total_missed ?? 0 }))} />
        </Panel>
        <Panel title="Last 6 months" subtitle="Chores done each month">
          <Trend householdId={house.id} />
        </Panel>
        <Panel title="Bills" subtitle="Where each one stands now" to="../../reminders">
          {bills.isLoading ? <Loading /> : <BillList bills={billList} />}
        </Panel>
      </div>
    </div>
  );
}

function Tile({ label, value, sub, to }: { label: string; value: ReactNode; sub: string; to: string }) {
  return (
    <Link to={to} className="card-hover rounded-2xl border border-white/70 bg-white/85 p-4 shadow-sm ring-1 ring-slate-900/5 backdrop-blur">
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-extrabold tabular-nums tracking-tight text-slate-900">{value}</p>
      <p className="mt-0.5 truncate text-xs text-slate-500">{sub}</p>
    </Link>
  );
}

function Panel({ title, subtitle, to, legend = false, children }: { title: string; subtitle: string; to?: string; legend?: boolean; children: ReactNode }) {
  return (
    <Card>
      <div className="mb-4 flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold">{title}</h2>
          <p className="text-xs text-slate-500">{subtitle}</p>
        </div>
        {legend && (
          <div className="flex items-center gap-3 text-xs text-slate-600">
            <Swatch color={DONE} label="Done" />
            <Swatch color={MISSED} label="Missed" />
          </div>
        )}
        {to && (
          <Link to={to} className="text-xs font-semibold text-indigo-600 hover:underline">
            Details →
          </Link>
        )}
      </div>
      {children}
    </Card>
  );
}

function Swatch({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="h-2.5 w-2.5 rounded-sm" style={{ background: color }} />
      {label}
    </span>
  );
}

/** A small hover label for a mark; also shown while the mark is focused or tapped. */
function Tip({ show, children }: { show: boolean; children: ReactNode }) {
  if (!show) return null;
  return (
    <span className="pointer-events-none absolute -top-8 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded-lg bg-slate-900 px-2 py-1 text-xs font-medium text-white shadow-lg">
      {children}
    </span>
  );
}

/** One bar per person (single series: no legend), with the fair share marked. */
function PersonBars({ rows, fairShare }: { rows: { name: string; done: number }[]; fairShare: number }) {
  const [hover, setHover] = useState<string | null>(null);
  if (!rows.length) return <Empty />;
  const max = Math.max(1, fairShare, ...rows.map((r) => r.done));
  const fairAt = (fairShare / max) * 100;
  const sorted = [...rows].sort((a, b) => b.done - a.done);
  return (
    <div className="space-y-2.5" role="list">
      {sorted.map((r) => (
        <div key={r.name} role="listitem" className="grid grid-cols-[5.5rem_1fr_2rem] items-center gap-3 text-sm">
          <span className="truncate text-slate-700">{r.name}</span>
          <div
            className="relative h-5 cursor-default"
            onMouseEnter={() => setHover(r.name)}
            onMouseLeave={() => setHover(null)}
            onClick={() => setHover((h) => (h === r.name ? null : r.name))}
          >
            <div className="absolute inset-y-1 left-0 right-0 rounded bg-slate-100" />
            <div className="absolute inset-y-1 left-0 rounded" style={{ width: `${(r.done / max) * 100}%`, background: DONE, minWidth: r.done ? 4 : 0 }} />
            <div className="absolute -inset-y-0.5 w-0.5 rounded bg-slate-500" style={{ left: `${fairAt}%` }} title="Fair share" />
            <Tip show={hover === r.name}>
              {r.name}: {r.done} done · fair share {share(fairShare)}
            </Tip>
          </div>
          <span className="text-right tabular-nums text-slate-700">{r.done}</span>
        </div>
      ))}
      <p className="pt-1 text-xs text-slate-500">
        <span className="mr-1 inline-block h-3 w-0.5 translate-y-0.5 bg-slate-500" /> fair share
      </p>
    </div>
  );
}

/** Done + missed per chore, stacked with a 2px gap; missed is always labelled with its number. */
function ChoreBars({ rows }: { rows: { name: string; done: number; missed: number }[] }) {
  const [hover, setHover] = useState<string | null>(null);
  if (!rows.length) return <Empty />;
  const max = Math.max(1, ...rows.map((r) => r.done + r.missed));
  return (
    <div className="space-y-2.5">
      {rows.map((r) => (
        <div key={r.name} className="grid grid-cols-[5.5rem_1fr_3.5rem] items-center gap-3 text-sm">
          <span className="truncate text-slate-700">{r.name}</span>
          <div
            className="relative flex h-5 cursor-default items-center gap-0.5"
            onMouseEnter={() => setHover(r.name)}
            onMouseLeave={() => setHover(null)}
            onClick={() => setHover((h) => (h === r.name ? null : r.name))}
          >
            {r.done > 0 && <div className="h-3 rounded" style={{ width: `${(r.done / max) * 100}%`, background: DONE }} />}
            {r.missed > 0 && <div className="h-3 rounded" style={{ width: `${(r.missed / max) * 100}%`, background: MISSED, minWidth: 4 }} />}
            {r.done + r.missed === 0 && <div className="h-3 w-full rounded bg-slate-100" />}
            <Tip show={hover === r.name}>
              {r.name}: {r.done} done · {r.missed} missed
            </Tip>
          </div>
          <span className="text-right tabular-nums text-slate-700">
            {r.done}
            {r.missed > 0 && <span className="text-amber-700"> +{r.missed}</span>}
          </span>
        </div>
      ))}
    </div>
  );
}

/** Chores done per month for up to the last six months: one line, with a dot per month. */
function Trend({ householdId }: { householdId: string }) {
  const months = useReportMonths(householdId, true);
  const last = (months.data?.months ?? []).slice().sort().slice(-6);
  const reports = useQueries({
    queries: last.map((m) => ({ queryKey: choreKeys.report(householdId, m), queryFn: () => reportsApi.report(householdId, m) })),
  });
  const [hover, setHover] = useState<number | null>(null);

  if (months.isLoading || reports.some((q) => q.isLoading)) return <Loading />;
  const points = last.map((m, i) => ({
    month: m,
    done: (reports[i].data?.leaderboard ?? []).reduce((n, row) => n + row.done, 0),
  }));
  if (points.length < 2) return <p className="py-8 text-center text-sm text-slate-500">Come back next month to see a trend.</p>;

  const W = 320;
  const H = 120;
  const pad = { l: 8, r: 8, t: 16, b: 22 };
  const max = Math.max(1, ...points.map((p) => p.done));
  const x = (i: number) => pad.l + (i * (W - pad.l - pad.r)) / (points.length - 1);
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.done)}`).join(" ");
  const label = (m: string) => new Date(`${m}-01T00:00:00`).toLocaleDateString(undefined, { month: "short" });

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={points.map((p) => `${label(p.month)}: ${p.done}`).join(", ")}>
        <line x1={pad.l} x2={W - pad.r} y1={H - pad.b} y2={H - pad.b} stroke="#e2e8f0" />
        <path d={path} fill="none" stroke={DONE} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {points.map((p, i) => (
          <g key={p.month} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onClick={() => setHover(i)}>
            <rect x={x(i) - 20} y={0} width={40} height={H} fill="transparent" />
            {hover === i && <line x1={x(i)} x2={x(i)} y1={pad.t - 6} y2={H - pad.b} stroke="#cbd5e1" strokeDasharray="3 3" />}
            <circle cx={x(i)} cy={y(p.done)} r={hover === i ? 5 : 4} fill={DONE} stroke="#fff" strokeWidth={2} />
            <text x={x(i)} y={H - 6} textAnchor="middle" className="fill-slate-500 text-[10px]">
              {label(p.month)}
            </text>
          </g>
        ))}
        {/* Label the latest month directly. */}
        <text x={x(points.length - 1)} y={y(points[points.length - 1].done) - 9} textAnchor="end" className="fill-slate-700 text-[11px] font-semibold">
          {points[points.length - 1].done}
        </text>
      </svg>
      {hover !== null && (
        <span
          className="pointer-events-none absolute top-0 -translate-x-1/2 whitespace-nowrap rounded-lg bg-slate-900 px-2 py-1 text-xs font-medium text-white shadow-lg"
          style={{ left: `${(x(hover) / W) * 100}%` }}
        >
          {label(points[hover].month)}: {points[hover].done} done
        </span>
      )}
    </div>
  );
}

const BILL_STATUS: Record<BillStatus, { label: string; icon: string; tone: string }> = {
  paid: { label: "Paid", icon: "✓", tone: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  due: { label: "Due", icon: "•", tone: "bg-amber-50 text-amber-800 ring-amber-200" },
  overdue: { label: "Overdue", icon: "!", tone: "bg-red-50 text-red-700 ring-red-200" },
  upcoming: { label: "Upcoming", icon: "…", tone: "bg-slate-100 text-slate-600 ring-slate-200" },
};

function BillList({ bills }: { bills: Bill[] }) {
  if (!bills.length) return <Empty text="No bills set up yet." />;
  return (
    <ul className="divide-y divide-slate-100">
      {bills.map((b) => {
        const s = BILL_STATUS[b.current.status];
        const amount = b.current.amount_cents ?? b.amount_cents;
        return (
          <li key={b.id} className="flex items-center gap-3 py-2 text-sm">
            <span className="text-lg">{b.icon}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-slate-800">{b.name}</span>
              <span className="block text-xs text-slate-500">
                {b.current.label} · due {formatDay(b.current.due_date)}
                {b.payer_mode === "everyone" && ` · ${b.current.paid_count}/${b.current.expected_count} paid`}
              </span>
            </span>
            {amount != null && <span className="tabular-nums text-slate-700">{formatMoney(amount, b.currency)}</span>}
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${s.tone}`}>
              {s.icon} {s.label}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function Empty({ text = "Nothing yet this month." }: { text?: string }) {
  return <p className="py-8 text-center text-sm text-slate-500">{text}</p>;
}
