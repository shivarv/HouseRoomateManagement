import { useCallback, useState, type FormEvent } from "react";
import { billsApi } from "../../api/bills";
import { Badge, Button, Card, Empty, ErrorText, Loading } from "../../components/ui";
import { useBillChange, useBills } from "../../features/bills/hooks";
import { formatMoney } from "../../lib/format";
import { useUnsavedChangesGuard } from "../../lib/unsavedChanges";
import type { AmountType, Bill, BillFields, BillFrequency, Member, PayerMode } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

const fieldClass =
  "rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-sm shadow-sm outline-none transition placeholder:text-slate-400 hover:border-indigo-300 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15";

/** One-tap starters for the add form (the four defaults every house starts with, plus a few more). */
const STARTERS: { name: string; icon: string; payer_mode: PayerMode; amount_type: AmountType }[] = [
  { name: "Rent", icon: "🏠", payer_mode: "everyone", amount_type: "fixed" },
  { name: "Electricity", icon: "⚡", payer_mode: "anyone", amount_type: "variable" },
  { name: "WiFi", icon: "📶", payer_mode: "anyone", amount_type: "fixed" },
  { name: "Gas", icon: "🔥", payer_mode: "anyone", amount_type: "variable" },
  { name: "Water", icon: "💧", payer_mode: "anyone", amount_type: "variable" },
  { name: "Cleaner", icon: "🧹", payer_mode: "everyone", amount_type: "fixed" },
];

const FREQUENCY_LABEL: Record<BillFrequency, string> = {
  monthly: "Every month",
  weekly: "Every week",
  daily: "Every day",
};
const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function dueText(bill: Bill): string {
  if (bill.frequency === "daily") return "Every day";
  if (bill.frequency === "weekly") return `Every ${WEEKDAYS[bill.due_day - 1] ?? "Monday"}`;
  return `Monthly on day ${bill.due_day}`;
}

const MODE_LABEL: Record<PayerMode, string> = {
  one: "One person pays",
  anyone: "Anyone can pay (first one closes it)",
  everyone: "Everyone pays their share",
};

const LEAVE_PROMPT = "You have unsaved bill changes. Leave and discard them?";

/** The form's fields as typed. Money is typed as text and stored as integer cents. */
interface FormValues {
  name: string;
  icon: string;
  payer_mode: PayerMode;
  payer_id: string;
  frequency: BillFrequency;
  due_day: string;
  amount_type: AmountType;
  amount: string;
  currency: string;
  note: string;
}

function valuesOf(bill?: Bill): FormValues {
  return {
    name: bill?.name ?? "",
    icon: bill?.icon ?? "🧾",
    payer_mode: bill?.payer_mode ?? "anyone",
    payer_id: bill?.payer?.id ?? "",
    frequency: bill?.frequency ?? "monthly",
    due_day: String(bill?.due_day ?? 1),
    amount_type: bill?.amount_type ?? "fixed",
    amount: bill?.amount_cents != null ? (bill.amount_cents / 100).toFixed(2) : "",
    currency: bill?.currency ?? "USD",
    note: bill?.note ?? "",
  };
}

/** "1,250.50" → 125050. Empty → null. Not a number → undefined (invalid). */
function cents(amount: string): number | null | undefined {
  const cleaned = amount.replace(/[,\s]/g, "");
  if (!cleaned) return null;
  const value = Number(cleaned);
  return Number.isFinite(value) && value >= 0 ? Math.round(value * 100) : undefined;
}

function problem(v: FormValues): string | null {
  if (!v.name.trim()) return "Give the bill a name";
  if (v.payer_mode === "one" && !v.payer_id) return "Pick who pays it";
  const day = Number(v.due_day);
  if (v.frequency === "monthly" && (!Number.isInteger(day) || day < 1 || day > 31)) return "Due day must be 1–31";
  if (v.amount_type === "fixed" && cents(v.amount) === undefined) return "Amount must be a number, like 60 or 1250.50";
  if (!/^[A-Za-z]{3}$/.test(v.currency.trim())) return "Currency is a 3-letter code, like USD or INR";
  return null;
}

function fieldsOf(v: FormValues): BillFields & { name: string } {
  return {
    name: v.name.trim(),
    icon: v.icon.trim() || "🧾",
    payer_mode: v.payer_mode,
    payer_id: v.payer_mode === "one" ? v.payer_id : null,
    frequency: v.frequency,
    due_day: v.frequency === "daily" ? 1 : Number(v.due_day),
    amount_type: v.amount_type,
    amount_cents: v.amount_type === "fixed" ? (cents(v.amount) ?? null) : null,
    currency: v.currency.trim().toUpperCase(),
    note: v.note.trim(),
  };
}

/** Settings → Reminders: the house's recurring bills. Every edit has its own Save. */
export function BillSettingsPage() {
  const household = useCurrentHousehold();
  const bills = useBills(household.id, true);
  const [editing, setEditing] = useState<string | null>(null); // bill id, or "new"
  const [starter, setStarter] = useState<FormValues | null>(null);
  const [dirty, setDirty] = useState(false);
  useUnsavedChangesGuard(dirty, LEAVE_PROMPT);

  // Switching forms with unsaved edits asks first, like leaving the page.
  const open = (id: string | null, values: FormValues | null = null) => {
    if (dirty && !confirm(LEAVE_PROMPT)) return;
    setDirty(false);
    setStarter(values);
    setEditing(id);
  };
  const onDirty = useCallback((d: boolean) => setDirty(d), []);

  if (bills.isLoading) return <Loading />;
  const list = bills.data?.bills ?? [];
  const names = new Set(list.map((b) => b.name.toLowerCase()));
  const starters = STARTERS.filter((s) => !names.has(s.name.toLowerCase()));

  return (
    <div className="space-y-6">
      <Card>
        <div className="mb-1 flex flex-wrap items-center gap-2">
          <h2 className="font-semibold">Bills</h2>
          {editing !== "new" && (
            <Button className="ml-auto" onClick={() => open("new")}>
              + Add a bill
            </Button>
          )}
        </div>
        <p className="mb-4 text-sm text-slate-500">
          Payments everyone sees on the 🧾 Reminders tab. Each one shows up at the start of its month, week or day.
          Fixed amounts repeat on their own; for amounts that change (gas, electricity), you enter each one on the
          Reminders tab when the bill arrives. Pause a bill to hide it and keep its history.
        </p>
        {starters.length > 0 && editing !== "new" && (
          <div className="mb-4 flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-xs text-slate-500">Quick add:</span>
            {starters.map((s) => (
              <button
                key={s.name}
                type="button"
                onClick={() => open("new", { ...valuesOf(), ...s })}
                className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 transition hover:border-indigo-300 hover:text-indigo-700"
              >
                + {s.icon} {s.name}
              </button>
            ))}
          </div>
        )}
        <ErrorText error={bills.error} />

        {editing === "new" && (
          <div className="mb-4 rounded-2xl border border-indigo-100 bg-indigo-50/40 p-4">
            <BillForm
              householdId={household.id}
              members={household.members}
              initial={starter ?? valuesOf()}
              onDirty={onDirty}
              onDone={() => (setDirty(false), setEditing(null))}
            />
          </div>
        )}

        {list.length === 0 && editing !== "new" ? (
          <Empty>No bills yet. Start with one of the quick adds above.</Empty>
        ) : (
          <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-100">
            {list.map((bill) =>
              editing === bill.id ? (
                <li key={bill.id} className="bg-indigo-50/40 p-4">
                  <BillForm
                    householdId={household.id}
                    members={household.members}
                    bill={bill}
                    initial={valuesOf(bill)}
                    onDirty={onDirty}
                    onDone={() => (setDirty(false), setEditing(null))}
                  />
                </li>
              ) : (
                <BillRow key={bill.id} bill={bill} onEdit={() => open(bill.id)} />
              ),
            )}
          </ul>
        )}
      </Card>
    </div>
  );
}

function BillRow({ bill, onEdit }: { bill: Bill; onEdit: () => void }) {
  const toggle = useBillChange(() => billsApi.update(bill.id, { is_active: !bill.is_active }));
  const remove = useBillChange(() => billsApi.remove(bill.id));

  return (
    <li className={`flex flex-wrap items-center gap-3 px-4 py-3 ${bill.is_active ? "" : "opacity-60"}`}>
      <span className="text-xl">{bill.icon}</span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{bill.name}</span>
          {bill.amount_type === "fixed" && bill.amount_cents != null && (
            <Badge>{formatMoney(bill.amount_cents, bill.currency)}</Badge>
          )}
          {bill.amount_type === "variable" && <Badge tone="indigo">Amount changes</Badge>}
          {!bill.is_active && <Badge tone="amber">Paused</Badge>}
        </div>
        <p className="text-xs text-slate-500">
          {dueText(bill)} ·{" "}
          {bill.payer_mode === "one" ? `${bill.payer?.display_name ?? "?"} pays` : MODE_LABEL[bill.payer_mode]}
        </p>
      </div>
      <Button variant="ghost" onClick={onEdit}>
        Edit
      </Button>
      <Button variant="ghost" disabled={toggle.isPending} onClick={() => toggle.mutate(undefined)}>
        {bill.is_active ? "Pause" : "Resume"}
      </Button>
      <Button
        variant="ghost"
        disabled={remove.isPending}
        onClick={() => confirm(`Delete “${bill.name}” and its payment history?`) && remove.mutate(undefined)}
        aria-label={`Delete ${bill.name}`}
      >
        ✕
      </Button>
      <div className="w-full">
        <ErrorText error={toggle.error ?? remove.error} />
      </div>
    </li>
  );
}

function BillForm({
  householdId,
  members,
  bill,
  initial,
  onDirty,
  onDone,
}: {
  householdId: string;
  members: Member[];
  bill?: Bill;
  initial: FormValues;
  onDirty: (dirty: boolean) => void;
  onDone: () => void;
}) {
  const [values, setValues] = useState(initial);
  const [touched, setTouched] = useState(false);
  const save = useBillChange(() =>
    bill ? billsApi.update(bill.id, fieldsOf(values)) : billsApi.create(householdId, fieldsOf(values)),
  );
  const changed = JSON.stringify(values) !== JSON.stringify(valuesOf(bill)) || !bill;
  const error = problem(values);

  const set = (patch: Partial<FormValues>) => {
    setValues((v) => ({ ...v, ...patch }));
    setTouched(true);
    onDirty(true);
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (error) return;
    save.mutate(undefined, { onSuccess: onDone });
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <input className={`${fieldClass} w-16 text-center`} value={values.icon} maxLength={16} onChange={(e) => set({ icon: e.target.value })} aria-label="Icon" />
        <input
          className={`${fieldClass} min-w-40 flex-1`}
          placeholder="e.g. WiFi"
          value={values.name}
          maxLength={80}
          onChange={(e) => set({ name: e.target.value })}
          aria-label="Name"
          autoFocus
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <select className={`${fieldClass} min-w-56`} value={values.payer_mode} onChange={(e) => set({ payer_mode: e.target.value as PayerMode })} aria-label="Who pays">
          {(Object.keys(MODE_LABEL) as PayerMode[]).map((m) => (
            <option key={m} value={m}>
              {MODE_LABEL[m]}
            </option>
          ))}
        </select>
        {values.payer_mode === "one" && (
          <select className={`${fieldClass} min-w-40`} value={values.payer_id} onChange={(e) => set({ payer_id: e.target.value })} aria-label="Who pays it">
            <option value="">Who pays it?</option>
            {members.map((m) => (
              <option key={m.id} value={m.id}>
                {m.display_name}
              </option>
            ))}
          </select>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <select
          className={`${fieldClass} min-w-40`}
          value={values.frequency}
          onChange={(e) => {
            const frequency = e.target.value as BillFrequency;
            // Weekdays are 1–7: "the 15th" becomes Monday.
            set({ frequency, due_day: frequency === "weekly" && Number(values.due_day) > 7 ? "1" : values.due_day });
          }}
          aria-label="Repeats"
        >
          {(Object.keys(FREQUENCY_LABEL) as BillFrequency[]).map((f) => (
            <option key={f} value={f}>
              {FREQUENCY_LABEL[f]}
            </option>
          ))}
        </select>
        {values.frequency === "monthly" && (
          <label className="flex items-center gap-2 text-sm text-slate-600">
            due on day
            <input className={`${fieldClass} w-20`} type="number" min={1} max={31} value={values.due_day} onChange={(e) => set({ due_day: e.target.value })} />
          </label>
        )}
        {values.frequency === "weekly" && (
          <label className="flex items-center gap-2 text-sm text-slate-600">
            due on
            <select className={`${fieldClass} min-w-36`} value={values.due_day} onChange={(e) => set({ due_day: e.target.value })}>
              {WEEKDAYS.map((d, i) => (
                <option key={d} value={String(i + 1)}>
                  {d}
                </option>
              ))}
            </select>
          </label>
        )}
        {values.frequency === "daily" && <span className="text-sm text-slate-500">due the same day</span>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <select
          className={`${fieldClass} min-w-56`}
          value={values.amount_type}
          onChange={(e) => set({ amount_type: e.target.value as AmountType })}
          aria-label="Amount"
        >
          <option value="fixed">Same amount every time</option>
          <option value="variable">Amount changes each time</option>
        </select>
        {values.amount_type === "fixed" ? (
          <input className={`${fieldClass} w-32`} inputMode="decimal" placeholder="Amount (optional)" value={values.amount} onChange={(e) => set({ amount: e.target.value })} aria-label="Amount" />
        ) : (
          <span className="text-sm text-slate-500">You'll enter it on the Reminders tab when the bill arrives</span>
        )}
        <input className={`${fieldClass} w-20 uppercase`} maxLength={3} value={values.currency} onChange={(e) => set({ currency: e.target.value })} aria-label="Currency" />
      </div>
      <input
        className={`${fieldClass} w-full`}
        placeholder="Note (optional), e.g. pay on the landlord's portal"
        value={values.note}
        maxLength={200}
        onChange={(e) => set({ note: e.target.value })}
        aria-label="Note"
      />
      <p className="text-xs text-slate-500">
        {values.frequency === "monthly" && "Due day 29–31 uses the last day of shorter months."}
        {values.payer_mode === "everyone" && " Each person taps their name once they've paid their share."}
      </p>
      {touched && error && <p className="text-sm text-red-600">{error}</p>}
      <ErrorText error={save.error} />
      <div className="flex gap-2">
        <Button type="submit" disabled={!!error || !changed || save.isPending}>
          {save.isPending ? "Saving…" : bill ? "Save changes" : "Add bill"}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
