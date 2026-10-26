import { useState, type FormEvent, type ReactNode } from "react";
import { billsApi } from "../../api/bills";
import { Badge, Button, Empty, ErrorText, Loading } from "../../components/ui";
import { useBillChange, useBillHistory, useBills } from "../../features/bills/hooks";
import { OpenChoreCard } from "../../features/chores/OpenChoreCard";
import { TaskCard } from "../../features/chores/TaskCard";
import { useHouseholdToday } from "../../features/chores/hooks";
import { formatDay, formatMoney, formatTime, localIsoDate } from "../../lib/format";
import type { Bill, BillPeriod, BillStatus, Member } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

// Bills come first and the most urgent ones lead.
const URGENCY: Record<BillStatus, number> = { overdue: 0, due: 1, upcoming: 2, paid: 3 };
const PERIOD_NAME = { monthly: "This month", weekly: "This week", daily: "Today" } as const;

const STATUS: Record<BillStatus, { label: string; chip: string }> = {
  overdue: { label: "Overdue", chip: "bg-red-600 text-white" },
  due: { label: "Due soon", chip: "bg-amber-500 text-white" },
  upcoming: { label: "Upcoming", chip: "bg-slate-100 text-slate-600" },
  paid: { label: "Paid", chip: "bg-emerald-100 text-emerald-700" },
};

/**
 * 🧾 Reminders: what needs doing now, most important first —
 * 1. bills (loud when due or overdue), 2. today's turns for a specific person, 3. chores anyone can do.
 * Everything is for the current day / week / month, so yesterday's reminders give way to today's.
 */
export function RemindersTab() {
  const household = useCurrentHousehold();
  const bills = useBills(household.id);
  const today = useHouseholdToday(household.id);

  if (bills.isLoading || today.isLoading) return <Loading />;
  const billList = [...(bills.data?.bills ?? [])].sort(
    (a, b) => URGENCY[a.current.status] - URGENCY[b.current.status] || a.position - b.position,
  );
  const urgent = billList.filter((b) => b.current.status === "overdue" || b.current.status === "due").length;
  // Mine first, then by whether it's still to do.
  const tasks = [...(today.data?.tasks ?? [])].sort(
    (a, b) => Number(a.status === "done") - Number(b.status === "done") || Number(b.is_mine) - Number(a.is_mine),
  );
  const pendingTasks = tasks.filter((t) => t.status === "pending").length;
  const open = today.data?.open ?? [];
  const isAdmin = household.my_role === "admin";

  return (
    <div className="space-y-8">
      <ErrorText error={bills.error ?? today.error} />

      <Group
        icon="💸"
        title="Bills"
        accent="from-rose-500 to-orange-500"
        count={urgent > 0 ? `${urgent} need${urgent === 1 ? "s" : ""} paying` : `${billList.length}`}
        loud={urgent > 0}
      >
        {billList.length === 0 ? (
          <Empty>No bills yet. {isAdmin ? "Add them in ⚙ Settings → Reminders." : "An admin can add them in Settings."}</Empty>
        ) : (
          billList.map((bill) => (
            <BillCard key={bill.id} bill={bill} members={household.members} myMemberId={household.my_member_id} isAdmin={isAdmin} />
          ))
        )}
      </Group>

      <Group icon="👤" title="Turns today" accent="from-indigo-500 to-violet-500" count={`${pendingTasks} to do`}>
        {tasks.length === 0 ? <Empty>Nobody has a turn today.</Empty> : tasks.map((t) => <TaskCard key={t.id} task={t} />)}
      </Group>

      <Group icon="🙌" title="Anyone can do" accent="from-emerald-500 to-teal-500" count={`${open.length}`}>
        {open.length === 0 ? (
          <Empty>No open chores.</Empty>
        ) : (
          open.map((o) => (
            <OpenChoreCard key={o.chore.id} item={o} today={today.data?.date ?? localIsoDate()} myMemberId={household.my_member_id} />
          ))
        )}
      </Group>
    </div>
  );
}

function Group({
  icon,
  title,
  accent,
  count,
  loud = false,
  children,
}: {
  icon: string;
  title: string;
  accent: string;
  count: string;
  loud?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center gap-2">
        <span className={`flex h-7 w-7 items-center justify-center rounded-lg bg-linear-to-br ${accent} text-sm text-white shadow-md`}>
          {icon}
        </span>
        <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">{title}</h2>
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${loud ? "animate-pulse bg-red-600 text-white" : "bg-slate-100 text-slate-500"}`}>
          {count}
        </span>
      </div>
      <div className={`space-y-3 border-l-4 pl-3 ${loud ? "border-red-400" : "border-slate-200"}`}>{children}</div>
    </section>
  );
}

function amountText(bill: Bill, period: BillPeriod): string | null {
  if (period.amount_cents == null) return null;
  const total = formatMoney(period.amount_cents, bill.currency);
  return period.share_cents != null && bill.payer_mode === "everyone"
    ? `${total} · ${formatMoney(period.share_cents, bill.currency)} each`
    : total;
}

function BillCard({ bill, members, myMemberId, isAdmin }: { bill: Bill; members: Member[]; myMemberId: string; isAdmin: boolean }) {
  const [showHistory, setShowHistory] = useState(false);
  const period = bill.current;
  const urgent = period.status === "overdue" || period.status === "due";
  const amount = amountText(bill, period);
  // A variable bill anyone pays: the amount and "paid" are one step for the admin.
  const payWithAmount =
    isAdmin && bill.amount_type === "variable" && bill.payer_mode !== "everyone" && period.is_current && period.payments.length === 0;

  return (
    <div
      className={`rounded-2xl border p-4 shadow-sm transition ${
        period.status === "overdue"
          ? "border-red-300 bg-linear-to-r from-red-50 to-white ring-2 ring-red-200"
          : period.status === "due"
            ? "border-amber-300 bg-linear-to-r from-amber-50 to-white ring-2 ring-amber-200"
            : period.status === "paid"
              ? "border-white/70 bg-white/70 opacity-80 ring-1 ring-slate-900/5"
              : "border-white/70 bg-white/90 ring-1 ring-slate-900/5"
      }`}
    >
      <div className="flex flex-wrap items-start gap-4">
        <div
          className={`relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-2xl shadow-sm ${
            urgent ? "bg-linear-to-br from-rose-200 to-orange-300" : "bg-linear-to-br from-sky-100 to-indigo-200"
          }`}
        >
          {bill.icon}
          {urgent && <span className="absolute -right-1 -top-1 h-3 w-3 animate-ping rounded-full bg-red-500" />}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-base font-semibold">{bill.name}</span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${STATUS[period.status].chip}`}>
              {STATUS[period.status].label}
            </span>
            {amount ? (
              <Badge>{amount}</Badge>
            ) : bill.amount_type === "variable" ? (
              <Badge tone="amber">Amount not set yet</Badge>
            ) : null}
          </div>
          <p className="mt-0.5 text-sm text-slate-600">
            {PERIOD_NAME[bill.frequency]} ({period.label}) · due {formatDay(period.due_date)} ·{" "}
            {bill.payer_mode === "anyone" ? "anyone can pay" : `split · ${period.paid_count} of ${period.expected_count} paid`}
          </p>
          {bill.note && <p className="text-xs text-slate-500">{bill.note}</p>}
        </div>
        {bill.payer_mode !== "everyone" && !payWithAmount && (
          <SinglePayer bill={bill} period={period} myMemberId={myMemberId} />
        )}
      </div>

      {bill.payer_mode === "everyone" && <EveryonePays bill={bill} period={period} members={members} myMemberId={myMemberId} />}
      {payWithAmount ? (
        <PayWithAmount bill={bill} period={period} />
      ) : (
        isAdmin && bill.amount_type === "variable" && <SetAmount bill={bill} />
      )}

      <button className="mt-3 text-xs font-medium text-slate-500 hover:text-indigo-700" onClick={() => setShowHistory((s) => !s)}>
        {showHistory ? "Hide history ▴" : "History ▾"}
      </button>
      {showHistory && <History bill={bill} members={members} myMemberId={myMemberId} />}
    </div>
  );
}

/** Anyone pays: a single payment settles the period for the house. */
function SinglePayer({ bill, period, myMemberId }: { bill: Bill; period: BillPeriod; myMemberId: string }) {
  const pay = useBillChange((memberId: string | undefined) => billsApi.pay(bill.id, { member_id: memberId, period: period.period }));
  const undo = useBillChange((paymentId: string) => billsApi.undo(paymentId));
  const busy = pay.isPending || undo.isPending;
  const first = period.payments[0];

  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      <div className="flex flex-wrap items-center justify-end gap-2">
        {first ? (
          <>
            <span className="text-sm font-medium text-emerald-700">
              ✓ Paid by {first.member.id === myMemberId ? "you" : first.member.display_name} ·{" "}
              {formatDay(localIsoDate(new Date(first.paid_at)))}, {formatTime(first.paid_at)}
            </span>
            {first.can_undo && (
              <Button variant="ghost" disabled={busy} onClick={() => undo.mutate(first.id)}>
                Undo
              </Button>
            )}
          </>
        ) : (
          <Button disabled={busy || !period.is_current} onClick={() => pay.mutate(undefined)}>
            {pay.isPending ? "Saving…" : "I paid it ✓"}
          </Button>
        )}
      </div>
      <ErrorText error={pay.error ?? undo.error} />
    </div>
  );
}

/** Everyone pays their share: one button per person; tapping adds them to the count. */
function EveryonePays({ bill, period, members, myMemberId }: { bill: Bill; period: BillPeriod; members: Member[]; myMemberId: string }) {
  const pay = useBillChange((memberId: string | undefined) => billsApi.pay(bill.id, { member_id: memberId, period: period.period }));
  const undo = useBillChange((paymentId: string) => billsApi.undo(paymentId));
  const busy = pay.isPending || undo.isPending;

  return (
    <div className="mt-3 space-y-2">
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-linear-to-r from-emerald-400 to-green-500 transition-all"
          style={{ width: `${Math.min(100, (period.paid_count / Math.max(1, period.expected_count)) * 100)}%` }}
        />
      </div>
      <div className="flex flex-wrap gap-1.5">
        {[...members]
          .sort((a, b) => Number(b.id === myMemberId) - Number(a.id === myMemberId))
          .map((m) => {
            const payment = period.payments.find((p) => p.member.id === m.id);
            const mine = m.id === myMemberId;
            return (
              <button
                key={m.id}
                type="button"
                disabled={busy || !period.is_current || (payment && !payment.can_undo)}
                onClick={() => (payment ? undo.mutate(payment.id) : pay.mutate(mine ? undefined : m.id))}
                title={payment ? (payment.can_undo ? "Paid · tap to undo" : "Paid") : mine ? "Tap once you've paid your share" : `Tap if ${m.display_name} has paid`}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition disabled:cursor-default ${
                  payment
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : mine
                      ? "border-indigo-300 bg-white text-indigo-700 hover:bg-indigo-50"
                      : "border-slate-200 bg-white text-slate-600 hover:border-indigo-300 hover:text-indigo-700"
                }`}
              >
                {payment ? "✓ " : ""}
                {mine ? "You" : m.display_name}
              </button>
            );
          })}
      </div>
      <ErrorText error={pay.error ?? undo.error} />
    </div>
  );
}

/** "84.50" → 8450; empty → null; not a number → NaN. */
function toCents(value: string): number | null {
  return value.trim() === "" ? null : Math.round(Number(value.replace(/[,\s]/g, "")) * 100);
}

function currencySymbol(currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).formatToParts(0).find((p) => p.type === "currency")?.value ?? currency;
  } catch {
    return currency;
  }
}

/**
 * Admins, for a variable bill anyone pays: type the amount, then one click saves it and marks it
 * paid by me. "Save amount only" is for a bill that arrived but isn't paid yet.
 */
function PayWithAmount({ bill, period }: { bill: Bill; period: BillPeriod }) {
  const [value, setValue] = useState(period.amount_cents != null ? (period.amount_cents / 100).toFixed(2) : "");
  const pay = useBillChange(async (cents: number) => {
    if (cents !== period.amount_cents) await billsApi.setAmount(bill.id, cents, period.period);
    return billsApi.pay(bill.id, { period: period.period });
  });
  const save = useBillChange((cents: number) => billsApi.setAmount(bill.id, cents, period.period));
  const cents = toCents(value);
  const valid = cents !== null && Number.isFinite(cents) && cents >= 0;
  const busy = pay.isPending || save.isPending;
  const amount = valid ? ` ${formatMoney(cents, bill.currency)}` : "";

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (valid) pay.mutate(cents);
  };

  return (
    <form onSubmit={submit} className="mt-3 space-y-2 rounded-2xl bg-indigo-50/60 p-3 ring-1 ring-indigo-100">
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex min-w-40 flex-1 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm transition focus-within:border-indigo-500 focus-within:ring-4 focus-within:ring-indigo-500/15">
          <span className="text-lg font-semibold text-slate-400">{currencySymbol(bill.currency)}</span>
          <input
            className="w-full bg-transparent text-lg font-semibold tabular-nums outline-none placeholder:font-normal placeholder:text-slate-400"
            inputMode="decimal"
            placeholder={`${period.label} amount`}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            aria-label={`${bill.name} amount for ${period.label}`}
          />
        </label>
        <Button type="submit" disabled={!valid || busy}>
          {pay.isPending ? "Saving…" : `✓ Paid${amount}`}
        </Button>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs">
        {bill.last_amount_cents != null && (
          <span className="text-slate-500">Last time {formatMoney(bill.last_amount_cents, bill.currency)}</span>
        )}
        <button
          type="button"
          className="font-medium text-indigo-700 hover:underline disabled:cursor-default disabled:opacity-50 disabled:no-underline"
          disabled={!valid || cents === period.amount_cents || busy}
          onClick={() => valid && save.mutate(cents)}
        >
          {save.isPending ? "Saving…" : "Save amount only"}
        </button>
        {value.trim() !== "" && !valid && <span className="text-red-600">Enter a number, like 84.50</span>}
      </div>
      <ErrorText error={pay.error ?? save.error} />
    </form>
  );
}

/** Admins: enter this period's amount when a variable bill (gas, electricity) arrives. */
function SetAmount({ bill, period }: { bill: Bill; period?: BillPeriod }) {
  const target = period ?? bill.current;
  const [value, setValue] = useState(target.amount_cents != null ? (target.amount_cents / 100).toFixed(2) : "");
  const save = useBillChange((cents: number | null) => billsApi.setAmount(bill.id, cents, target.period));
  const cents = value.trim() === "" ? null : Math.round(Number(value.replace(/[,\s]/g, "")) * 100);
  const invalid = cents !== null && (!Number.isFinite(cents) || cents < 0);
  const changed = cents !== target.amount_cents;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!invalid && changed) save.mutate(cents);
  };

  return (
    <form onSubmit={submit} className="mt-3 flex flex-wrap items-center gap-2 rounded-xl bg-amber-50/60 px-3 py-2 ring-1 ring-amber-100">
      <span className="text-xs font-medium text-amber-800">
        {target.label} amount
        {!period && bill.last_amount_cents != null && ` · last time ${formatMoney(bill.last_amount_cents, bill.currency)}`}
      </span>
      <input
        className="w-28 rounded-lg border border-amber-200 bg-white px-2 py-1 text-sm outline-none focus:border-amber-400"
        inputMode="decimal"
        placeholder={`e.g. 84.50 ${bill.currency}`}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        aria-label={`${bill.name} amount for ${target.label}`}
      />
      <Button type="submit" variant="secondary" disabled={invalid || !changed || save.isPending}>
        {save.isPending ? "Saving…" : "Save amount"}
      </Button>
      {invalid && <span className="text-xs text-red-600">Enter a number, like 84.50</span>}
      <ErrorText error={save.error} />
    </form>
  );
}

function History({ bill, members, myMemberId }: { bill: Bill; members: Member[]; myMemberId: string }) {
  const history = useBillHistory(bill.id, true);
  const household = useCurrentHousehold();
  if (history.isLoading) return <p className="mt-2 text-xs text-slate-500">Loading…</p>;
  const periods = history.data ?? [];

  return (
    <ul className="mt-2 divide-y divide-slate-100 rounded-xl border border-slate-100 bg-white/70">
      <ErrorText error={history.error} />
      {periods.map((p) => (
        <li key={p.period} className="space-y-1 px-3 py-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="w-28 font-medium">{p.label}</span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS[p.status].chip}`}>{STATUS[p.status].label}</span>
            {amountText(bill, p) && <span className="text-xs text-slate-500">{amountText(bill, p)}</span>}
            <span className="text-xs text-slate-500">
              {p.payments.length > 0 &&
                (bill.payer_mode === "everyone"
                  ? `${p.paid_count} of ${p.expected_count} paid`
                  : `${p.payments[0].member.display_name} paid`)}
            </span>
          </div>
          {p.status !== "paid" &&
            (bill.payer_mode === "everyone" ? (
              <EveryonePays bill={bill} period={p} members={members} myMemberId={myMemberId} />
            ) : (
              <SinglePayer bill={bill} period={p} myMemberId={myMemberId} />
            ))}
          {household.my_role === "admin" && bill.amount_type === "variable" && p.amount_cents == null && (
            <SetAmount bill={bill} period={p} />
          )}
        </li>
      ))}
    </ul>
  );
}
