import { useState } from "react";
import { Empty, ErrorText, Loading } from "../../components/ui";
import { ReportView } from "../../features/chores/ReportView";
import { useReport, useReportMonths } from "../../features/chores/hooks";
import { formatMonth } from "../../lib/format";
import { useCurrentHousehold } from "./HouseholdLayout";

/** This month's dashboard — visible to everyone. */
export function ReportTab() {
  const household = useCurrentHousehold();
  const report = useReport(household.id);
  if (report.isLoading) return <Loading />;
  if (!report.data) return <ErrorText error={report.error} />;
  return <ReportView report={report.data} myMemberId={household.my_member_id} />;
}

/** Past months — admins only. */
export function HistoryTab() {
  const household = useCurrentHousehold();
  const isAdmin = household.my_role === "admin";
  const months = useReportMonths(household.id, isAdmin);
  const past = (months.data?.months ?? []).slice(1); // first entry is the current month
  const [selected, setSelected] = useState<string | undefined>();
  const month = selected ?? past[0];
  const report = useReport(household.id, month);

  if (!isAdmin) return <Empty>Only admins can see past months.</Empty>;
  if (months.isLoading) return <Loading />;
  if (past.length === 0) return <Empty>No past months yet. This month's numbers are in the Report tab.</Empty>;

  return (
    <div className="space-y-4">
      <label className="flex items-center gap-2 text-sm">
        <span className="font-medium text-slate-700">Month</span>
        <select
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5"
          value={month}
          onChange={(e) => setSelected(e.target.value)}
        >
          {past.map((m) => (
            <option key={m} value={m}>
              {formatMonth(m)}
            </option>
          ))}
        </select>
      </label>
      {report.isLoading ? <Loading /> : report.data ? (
        <ReportView report={report.data} myMemberId={household.my_member_id} />
      ) : (
        <ErrorText error={report.error} />
      )}
    </div>
  );
}
