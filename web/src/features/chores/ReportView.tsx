import { Badge, Card, Empty } from "../../components/ui";
import { formatDay, formatMonth, percent } from "../../lib/format";
import type { ChoreReport, Report } from "../../types/api";
import { choreIcon } from "./TaskCard";

/** Below half of a fair share is called out; it's a nudge, not an accusation. */
const isLow = (share: number, fair: number) => share < fair / 2;

export function ReportView({ report, myMemberId }: { report: Report; myMemberId: string }) {
  const totalDone = report.leaderboard.reduce((sum, r) => sum + r.done, 0);

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-500">
        {formatMonth(report.month)} · {formatDay(report.start)} – {formatDay(report.end)}
        {report.is_current && " · so far"} · fair share {percent(report.fair_share)} each
      </p>

      <Card>
        <h2 className="mb-3 font-semibold">Leaderboard</h2>
        {totalDone === 0 && report.leaderboard.every((r) => r.missed === 0) ? (
          <Empty>Nothing recorded this month yet.</Empty>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-slate-500">
              <tr>
                <th className="w-8 py-1.5 font-medium">#</th>
                <th className="py-1.5 font-medium">Person</th>
                <th className="py-1.5 text-right font-medium">Done</th>
                <th className="py-1.5 text-right font-medium">Missed</th>
                <th className="hidden py-1.5 text-right font-medium sm:table-cell">Covered for others</th>
              </tr>
            </thead>
            <tbody>
              {report.leaderboard.map((r, i) => (
                <tr key={r.member.id} className={`border-t border-slate-100 ${r.member.id === myMemberId ? "font-semibold" : ""}`}>
                  <td className="py-2 text-slate-400">{i + 1}</td>
                  <td className="py-2">
                    {r.member.display_name} {!r.is_active && <Badge>Left</Badge>}
                    {totalDone > 0 && r.is_active && isLow(r.done / totalDone, report.fair_share) && (
                      <Badge tone="amber">Below fair share</Badge>
                    )}
                  </td>
                  <td className="py-2 text-right tabular-nums">{r.done}</td>
                  <td className={`py-2 text-right tabular-nums ${r.missed ? "text-amber-700" : "text-slate-400"}`}>{r.missed}</td>
                  <td className="hidden py-2 text-right tabular-nums text-slate-500 sm:table-cell">{r.covered_for_others}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {report.chores.map((c) => (
          <ChoreReportCard key={c.chore.id} report={c} fair={report.fair_share} myMemberId={myMemberId} />
        ))}
      </div>
    </div>
  );
}

function ChoreReportCard({ report, fair, myMemberId }: { report: ChoreReport; fair: number; myMemberId: string }) {
  const isOpen = report.chore.assignment_mode === "open";
  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">
          {choreIcon(report.chore.name)} {report.chore.name}
        </h3>
        <Badge>{report.chore.frequency === "weekly" ? "Weekly" : "Daily"}</Badge>
        {isOpen && <Badge tone="green">Anyone</Badge>}
        {!report.is_active && <Badge tone="amber">Paused</Badge>}
        <span className="ml-auto text-xs text-slate-500">
          {report.total_done} done{report.total_missed ? ` · ${report.total_missed} missed` : ""}
        </span>
      </div>
      <ul className="space-y-2.5">
        {report.rows.map((r) => {
          const low = r.is_active && report.total_done > 0 && isLow(r.share, fair);
          const notes = isOpen
            ? [r.last_done ? `last ${formatDay(r.last_done)}` : "not this month"]
            : [
                `${r.turns} turn${r.turns === 1 ? "" : "s"}`,
                r.missed ? `${r.missed} missed` : null,
                r.covered_by_others ? `${r.covered_by_others} covered by others` : null,
                r.covered_for_others ? `covered ${r.covered_for_others}` : null,
              ];
          return (
            <li key={r.member.id}>
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className={r.member.id === myMemberId ? "font-semibold" : ""}>
                  {r.member.display_name}
                  {r.done === 0 && r.is_active && <span className="ml-2 text-xs text-amber-700">not yet</span>}
                </span>
                <span className="tabular-nums text-slate-600">
                  {r.done} · {percent(r.share)}
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={`h-full rounded-full ${low ? "bg-amber-400" : "bg-indigo-500"}`}
                  style={{ width: `${Math.max(r.share * 100, r.done ? 3 : 0)}%` }}
                />
              </div>
              <p className="mt-0.5 text-xs text-slate-400">{notes.filter(Boolean).join(" · ")}</p>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
