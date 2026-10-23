import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { householdsApi } from "../api/households";
import { Badge, Button, Card, ErrorText, Input, Loading, PageTitle } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";
import { DueDayField } from "../features/bills/DueDayField";
import { browserTimezone } from "../lib/format";
import { lastHousehold } from "../lib/lastHousehold";
import { useUnsavedChangesGuard } from "../lib/unsavedChanges";
import type { HouseholdSetup, SetupBill, SetupChore, SetupGrocery, SetupTemplate } from "../types/api";

const fieldClass =
  "rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-sm shadow-sm outline-none transition placeholder:text-slate-400 hover:border-indigo-300 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15";

const STEPS = ["Your home", "Roommates", "Chores", "Groceries", "Bills", "Review"] as const;
type StepName = (typeof STEPS)[number];
const LEAVE_PROMPT =
  "Your new home isn't created yet. Finish the setup and tap “Create home” to save it, or you'll lose what you've filled in.\n\nLeave anyway?";

/** A chore as the wizard edits it: who's left out of its turns, by position in `people` (0 = me). */
type WizardChore = SetupChore & { excluded: number[] };

/** "Everyone" · "Everyone except Bea" · "Ann, Cy" · "Nobody yet" */
function rotationLabel(people: string[], excluded: number[]): string {
  const left = excluded.filter((i) => i < people.length);
  if (left.length === 0) return "Everyone";
  const included = people.filter((_, i) => !left.includes(i));
  if (included.length === 0) return "Nobody yet";
  if (left.length <= 2 && included.length > left.length) return `Everyone except ${left.map((i) => people[i]).join(" & ")}`;
  return included.join(", ");
}

/** How many of each to start with. Roommates and groceries can be 0; chores and bills start at 1. */
interface Counts {
  roommates: number; // besides me
  chores: number;
  groceries: number;
  bills: number;
}

/** Prefill a list to `count`: keep what's been edited, add template defaults for the rest. */
function resize<T extends { name: string }>(list: T[], count: number, defaults: T[], blank: () => T): T[] {
  if (count <= list.length) return list.slice(0, count);
  const taken = new Set(list.map((x) => x.name.toLowerCase()));
  const extra = defaults.filter((d) => !taken.has(d.name.toLowerCase()));
  const out = [...list];
  while (out.length < count) out.push(extra.length ? { ...extra.shift()! } : blank());
  return out;
}

function duplicate(names: string[]): string | null {
  const seen = new Set<string>();
  for (const n of names.map((x) => x.trim().toLowerCase())) {
    if (seen.has(n)) return n;
    seen.add(n);
  }
  return null;
}

/**
 * Guided set-up of a new home: details, then how many roommates / chores / groceries / bills,
 * each prefilled from a template and editable. Nothing is created until "Create home".
 */
export function SetupWizardPage() {
  const template = useQuery({ queryKey: ["setup-template"], queryFn: householdsApi.setupTemplate });
  if (template.isLoading) return <Loading />;
  if (!template.data) return <ErrorText error={template.error ?? "Couldn't load the template"} />;
  return <Wizard template={template.data} />;
}

function Wizard({ template }: { template: SetupTemplate }) {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const max = template.max_items;

  const [step, setStep] = useState(0);
  const [details, setDetails] = useState({ name: "", address: "", timezone: browserTimezone() });
  const [counts, setCounts] = useState<Counts>({ roommates: 2, chores: 2, groceries: 0, bills: 2 });
  // No roommates skips their step. Groceries always shows, so items can still be added there.
  const steps: StepName[] = STEPS.filter((s) => s !== "Roommates" || counts.roommates > 0);
  /** Groceries added or removed on their step keep the count in step, so going back keeps them. */
  const setGroceryList = (list: SetupGrocery[]) => {
    setGroceries(list);
    setCounts((c) => ({ ...c, groceries: list.length }));
  };
  const current = steps[step];
  const [roommates, setRoommates] = useState<string[]>([]);
  const [chores, setChores] = useState<WizardChore[]>([]);
  const [groceries, setGroceries] = useState<SetupGrocery[]>([]);
  const [bills, setBills] = useState<SetupBill[]>([]);
  const [currency, setCurrency] = useState("USD");
  const [error, setError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () => householdsApi.setup(payload()),
    onSuccess: async (house) => {
      lastHousehold.set(house.id);
      await queryClient.invalidateQueries();
      navigate(`/households/${house.id}/reminders`);
    },
  });
  const touched = step > 0 || details.name.trim() !== "" || details.address.trim() !== "";
  useUnsavedChangesGuard(touched && !create.isSuccess, LEAVE_PROMPT);

  const me = user?.name ?? "You";
  const people = [me, ...roommates.map((r) => r.trim())];

  function payload(): HouseholdSetup {
    return {
      name: details.name.trim(),
      address: details.address.trim(),
      timezone: details.timezone.trim(),
      roommates: roommates.map((r) => r.trim()),
      chores: chores.map(({ excluded, ...c }) => {
        const left = excluded.filter((i) => i < people.length);
        // Everyone (people left out) unless someone was taken off the rotation.
        const turns = c.assignment_mode === "rotation" && left.length ? people.filter((_, i) => !left.includes(i)) : undefined;
        return { ...c, name: c.name.trim(), ...(turns ? { people: turns } : {}) };
      }),
      groceries: groceries.map((g) => ({ ...g, name: g.name.trim() })),
      bills: bills.map((b) => ({
        ...b,
        name: b.name.trim(),
        payer_name: b.payer_mode === "one" ? b.payer_name : null,
        due_day: b.frequency === "daily" ? 1 : b.due_day,
        amount_cents: b.amount_type === "fixed" ? b.amount_cents : null,
      })),
      currency: currency.trim().toUpperCase(),
    };
  }

  /** What's wrong with the current step, or null to go on. */
  function problem(): string | null {
    switch (current) {
      case "Your home": {
        if (!details.name.trim()) return "Give your home a name";
        if (!details.address.trim()) return "Add the home's address";
        if (!details.timezone.trim()) return "Add a timezone, e.g. America/New_York";
        const bad = (n: number, lo: number, hi: number) => !Number.isInteger(n) || n < lo || n > hi;
        if (bad(counts.roommates, 0, max - 1)) return `Roommates: pick 0–${max - 1}`;
        if (bad(counts.chores, 1, max)) return `Chores: pick 1–${max} (at least one to begin with)`;
        if (bad(counts.groceries, 0, max)) return `Grocery items: pick 0–${max}`;
        if (bad(counts.bills, 1, max)) return `Bills: pick 1–${max} (at least one to begin with)`;
        return null;
      }
      case "Roommates":
        if (roommates.some((r) => !r.trim())) return "Every roommate needs a name";
        if (duplicate(people)) return `Two people are called “${duplicate(people)}”: names must be different`;
        return null;
      case "Chores":
        if (chores.some((c) => !c.name.trim())) return "Every chore needs a name";
        if (duplicate(chores.map((c) => c.name))) return `Two chores are called “${duplicate(chores.map((c) => c.name))}”`;
        if (chores.some((c) => c.assignment_mode === "rotation" && people.every((_, i) => c.excluded.includes(i))))
          return "Every “take turns” chore needs at least one person";
        return null;
      case "Groceries":
        if (groceries.some((g) => !g.name.trim())) return "Every grocery item needs a name";
        if (duplicate(groceries.map((g) => g.name))) return `Two items are called “${duplicate(groceries.map((g) => g.name))}”`;
        return null;
      case "Bills":
        if (bills.some((b) => !b.name.trim())) return "Every bill needs a name";
        if (duplicate(bills.map((b) => b.name))) return `Two bills are called “${duplicate(bills.map((b) => b.name))}”`;
        if (bills.some((b) => b.payer_mode === "one" && !people.some((p) => p.toLowerCase() === b.payer_name?.toLowerCase())))
          return "Pick who pays each “one person pays” bill";
        if (bills.some((b) => b.amount_type === "fixed" && b.amount_cents !== null && (!Number.isFinite(b.amount_cents) || b.amount_cents < 0)))
          return "Amounts must be numbers, like 60 or 1250.50";
        if (!/^[A-Za-z]{3}$/.test(currency.trim())) return "Currency is a 3-letter code, like USD or INR";
        return null;
      default:
        return null;
    }
  }

  const next = () => {
    const p = problem();
    setError(p);
    if (p) return;
    if (current === "Your home") {
      // Prefill each list to its count, keeping anything already edited.
      setRoommates((r) => {
        const out = r.slice(0, counts.roommates);
        while (out.length < counts.roommates) out.push(`Roommate ${out.length + 2}`);
        return out;
      });
      setChores((c) =>
        resize(
          c.map((x) => ({ ...x, excluded: x.excluded.filter((i) => i <= counts.roommates) })),
          counts.chores,
          template.chores.map((t) => ({ ...t, excluded: [] })),
          () => ({ name: "", frequency: "daily", assignment_mode: "rotation", excluded: [] }),
        ),
      );
      setGroceries((g) => resize(g, counts.groceries, template.groceries, () => ({ name: "", category_key: "other" })));
      setBills((b) =>
        resize(b, counts.bills, template.bills, () => ({
          name: "", icon: "🧾", payer_mode: "anyone", payer_name: null, frequency: "monthly", due_day: 1, amount_type: "fixed", amount_cents: null,
        })),
      );
    }
    setStep((s) => s + 1);
  };
  const back = () => {
    setError(null);
    setStep((s) => s - 1);
  };

  return (
    <div className="space-y-6">
      <PageTitle title="Set up a new home" subtitle="A few quick steps. Everything is prefilled; change what you like. You can edit it all later in ⚙ Settings." />

      <ol className="flex flex-wrap gap-1.5">
        {steps.map((name, i) => (
          <li
            key={name}
            className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
              i === step ? "bg-linear-to-r from-indigo-500 to-fuchsia-500 text-white shadow-md" : i < step ? "bg-emerald-100 text-emerald-700" : "bg-white/80 text-slate-500 ring-1 ring-slate-200"
            }`}
          >
            <span>{i < step ? "✓" : i + 1}</span>
            {name}
          </li>
        ))}
      </ol>

      <Card>
        {current === "Your home" && (
          <Step title="🏠 Your new home" hint="You'll be its admin. Tell us how many of each to start with, and we'll prefill the next steps.">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Name" placeholder="e.g. Maple Street House" maxLength={100} value={details.name} onChange={(e) => setDetails({ ...details, name: e.target.value })} />
              <Input label="Timezone" value={details.timezone} onChange={(e) => setDetails({ ...details, timezone: e.target.value })} />
              <div className="sm:col-span-2">
                <Input label="Address" placeholder="e.g. 12 Maple Street, Boston, MA" maxLength={300} value={details.address} onChange={(e) => setDetails({ ...details, address: e.target.value })} />
              </div>
            </div>
            <h3 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-widest text-slate-500">How many to start with</h3>
            <div className="space-y-3">
              <Question
                icon="👥"
                question="How many roommates live with you?"
                hint={counts.roommates === 0 ? "Just you for now — invite people later with the house's invite code." : "Not counting you. They can claim their name later with the invite code."}
                value={counts.roommates}
                min={0}
                max={max - 1}
                onChange={(roommates) => setCounts({ ...counts, roommates })}
              />
              <Question
                icon="🧹"
                question="How many chores should we start with?"
                hint="At least one. Cooking, cleaning and the trash are a good start."
                value={counts.chores}
                min={1}
                max={max}
                onChange={(chores) => setCounts({ ...counts, chores })}
              />
              <Question
                icon="🛒"
                question="How many grocery quick-add items?"
                hint={counts.groceries === 0 ? "None for now — anyone can still add anything to the list." : "One-tap buttons for things you buy often."}
                value={counts.groceries}
                min={0}
                max={max}
                onChange={(groceries) => setCounts({ ...counts, groceries })}
              />
              <Question
                icon="🧾"
                question="How many bills should we remind you about?"
                hint="At least one, like rent or WiFi."
                value={counts.bills}
                min={1}
                max={max}
                onChange={(bills) => setCounts({ ...counts, bills })}
              />
            </div>
          </Step>
        )}

        {current === "Roommates" && (
          <Step title="👥 Roommates" hint="They can claim their name later with the invite code, or stay name-only.">
            <ul className="space-y-2">
              <li className="flex items-center gap-2">
                <input className={`${fieldClass} flex-1 bg-slate-50`} value={me} disabled />
                <Badge tone="indigo">You · admin</Badge>
              </li>
              {roommates.map((r, i) => (
                <li key={i}>
                  <input
                    className={`${fieldClass} w-full`}
                    value={r}
                    maxLength={100}
                    onChange={(e) => setRoommates(roommates.map((x, j) => (j === i ? e.target.value : x)))}
                    aria-label={`Roommate ${i + 2}`}
                  />
                </li>
              ))}
            </ul>
          </Step>
        )}

        {current === "Chores" && (
          <Step title="🧹 Chores" hint="Take turns: the people in it rotate (tap “👥” to leave someone out). Anyone: whoever does it logs it.">
            {chores.length === 0 ? (
              <Nothing what="chores" />
            ) : (
              <ul className="space-y-2">
                {chores.map((c, i) => (
                  <li key={i} className="space-y-2 rounded-xl border border-slate-100 bg-white/70 p-2">
                    <div className="flex flex-wrap gap-2">
                      <input className={`${fieldClass} min-w-40 flex-1`} value={c.name} maxLength={100} placeholder="e.g. Clean bathroom" onChange={(e) => setChores(chores.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} aria-label="Chore" />
                      <select className={`${fieldClass} w-32`} value={c.frequency} onChange={(e) => setChores(chores.map((x, j) => (j === i ? { ...x, frequency: e.target.value as SetupChore["frequency"] } : x)))} aria-label="How often">
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                      </select>
                      <select className={`${fieldClass} w-40`} value={c.assignment_mode} onChange={(e) => setChores(chores.map((x, j) => (j === i ? { ...x, assignment_mode: e.target.value as SetupChore["assignment_mode"] } : x)))} aria-label="Who does it">
                        <option value="rotation">Take turns</option>
                        <option value="open">Anyone</option>
                      </select>
                    </div>
                    {c.assignment_mode === "rotation" && (
                      <RotationPicker people={people} excluded={c.excluded} onChange={(excluded) => setChores(chores.map((x, j) => (j === i ? { ...x, excluded } : x)))} />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Step>
        )}

        {current === "Groceries" && (
          <Step title="🛒 Grocery quick-add items" hint="One-tap buttons on the Groceries tab. Pick from our list or add your own; anyone can still add anything to the list.">
            <GroceryPicker
              picked={groceries}
              options={template.groceries}
              categories={template.categories}
              max={max}
              onChange={setGroceryList}
            />
          </Step>
        )}

        {current === "Bills" && (
          <Step title="🧾 Bills" hint="They show up on Reminders at the start of each month, week or day. Amounts that change (gas, electricity) are entered when the bill arrives.">
            {bills.length === 0 ? (
              <Nothing what="bills" />
            ) : (
              <ul className="space-y-3">
                {bills.map((b, i) => (
                  <BillRow key={i} bill={b} people={people} onChange={(bill) => setBills(bills.map((x, j) => (j === i ? bill : x)))} />
                ))}
              </ul>
            )}
            <label className="mt-3 flex items-center gap-2 text-sm text-slate-600">
              Currency
              <input className={`${fieldClass} w-20 uppercase`} maxLength={3} value={currency} onChange={(e) => setCurrency(e.target.value)} />
            </label>
          </Step>
        )}

        {current === "Review" && (
          <Step title="✅ Review" hint="Looks right? Create it — you can change everything later in ⚙ Settings.">
            <dl className="grid gap-3 text-sm sm:grid-cols-2">
              <Summary label="🏠 Home" value={`${details.name} · ${details.address}`} />
              <Summary
                label="👥 People"
                value={roommates.length ? people.join(", ") : `Just you (${me}) for now. Invite people later with the invite code on the home's banner.`}
              />
              <Summary
                label="🧹 Chores"
                value={
                  chores
                    .map((c) => (c.assignment_mode === "open" ? `${c.name} (anyone)` : `${c.name} (${rotationLabel(people, c.excluded).toLowerCase()})`))
                    .join(", ") || "None"
                }
              />
              <Summary label="🛒 Quick-add" value={groceries.map((g) => g.name).join(", ") || "None"} />
              <Summary label="🧾 Bills" value={bills.map((b) => `${b.icon} ${b.name}`).join(", ") || "None"} />
            </dl>
          </Step>
        )}

        {error && <p className="mt-4 text-sm font-medium text-red-600">{error}</p>}
        <ErrorText error={create.error} />

        <div className="mt-6 flex flex-wrap gap-2">
          {step > 0 && (
            <Button variant="ghost" disabled={create.isPending} onClick={back}>
              ← Back
            </Button>
          )}
          {current === "Review" ? (
            <Button disabled={create.isPending} onClick={() => create.mutate()}>
              {create.isPending ? "Creating…" : "Create home"}
            </Button>
          ) : (
            <Button onClick={next}>Next →</Button>
          )}
        </div>
      </Card>
    </div>
  );
}

/** Who takes turns: "Everyone" until someone is tapped off. */
function RotationPicker({ people, excluded, onChange }: { people: string[]; excluded: number[]; onChange: (excluded: number[]) => void }) {
  const [open, setOpen] = useState(false);
  const label = rotationLabel(people, excluded);
  const everyone = label === "Everyone";
  return (
    <div className="text-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={`rounded-full px-3 py-1 text-xs font-semibold ring-1 transition ${
          everyone ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : "bg-amber-50 text-amber-800 ring-amber-200"
        }`}
        title="Choose who takes turns"
      >
        👥 {label} {open ? "▴" : "▾"}
      </button>
      {open && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {people.map((p, i) => {
            const out = excluded.includes(i);
            return (
              <button
                key={i}
                type="button"
                onClick={() => onChange(out ? excluded.filter((x) => x !== i) : [...excluded, i])}
                className={`rounded-full border px-3 py-1 text-xs font-medium transition ${
                  out ? "border-slate-200 bg-white text-slate-400 line-through" : "border-indigo-200 bg-indigo-50 text-indigo-700"
                }`}
                title={out ? `Add ${p} back` : `Leave ${p} out`}
              >
                {out ? "" : "✓ "}
                {p}
              </button>
            );
          })}
          {excluded.length > 0 && (
            <button type="button" className="text-xs text-slate-500 hover:underline" onClick={() => onChange([])}>
              Everyone again
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** Your list (names only) + every option to pick from + add your own. */
function GroceryPicker({
  picked,
  options,
  categories,
  max,
  onChange,
}: {
  picked: SetupGrocery[];
  options: SetupGrocery[];
  categories: SetupTemplate["categories"];
  max: number;
  onChange: (list: SetupGrocery[]) => void;
}) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("groceries");
  const [error, setError] = useState<string | null>(null);
  const icon = (key: string) => categories.find((c) => c.key === key)?.icon ?? "🛍️";
  const has = (n: string) => picked.some((g) => g.name.trim().toLowerCase() === n.trim().toLowerCase());
  const full = picked.length >= max;

  const toggle = (option: SetupGrocery) =>
    onChange(has(option.name) ? picked.filter((g) => g.name.toLowerCase() !== option.name.toLowerCase()) : full ? picked : [...picked, { ...option }]);
  const addOwn = () => {
    const n = name.trim();
    if (!n) return;
    if (has(n)) return setError(`${n} is already on your list`);
    if (full) return setError(`Up to ${max} items`);
    onChange([...picked, { name: n, category_key: category }]);
    setName("");
    setError(null);
  };

  return (
    <div className="space-y-5">
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">
          Your list · {picked.length} of {max}
        </p>
        {picked.length === 0 ? (
          <p className="text-sm text-slate-500">Nothing yet — that's fine. Pick some below, or add them later in ⚙ Settings → Groceries.</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {picked.map((g) => (
              <span key={g.name} className="inline-flex items-center gap-1 rounded-full bg-indigo-50 py-1 pl-3 pr-1 text-sm font-medium text-indigo-800 ring-1 ring-indigo-200">
                {icon(g.category_key)} {g.name}
                <button
                  type="button"
                  className="ml-0.5 rounded-full px-1.5 text-indigo-400 transition hover:bg-indigo-100 hover:text-indigo-700"
                  onClick={() => onChange(picked.filter((x) => x !== g))}
                  aria-label={`Remove ${g.name}`}
                >
                  ✕
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Pick from our list</p>
        <div className="flex flex-wrap gap-1.5">
          {options.map((o) => {
            const on = has(o.name);
            return (
              <button
                key={o.name}
                type="button"
                onClick={() => toggle(o)}
                disabled={!on && full}
                className={`rounded-full border px-3 py-1 text-sm transition disabled:opacity-40 ${
                  on ? "border-indigo-300 bg-indigo-600 text-white shadow-sm" : "border-slate-200 bg-white text-slate-700 hover:border-indigo-300 hover:text-indigo-700"
                }`}
                aria-pressed={on}
              >
                {on ? "✓ " : "+ "}
                {icon(o.category_key)} {o.name}
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Add your own</p>
        <div className="flex flex-wrap gap-2">
          <input
            className={`${fieldClass} min-w-40 flex-1`}
            placeholder="e.g. Paneer"
            maxLength={80}
            value={name}
            onChange={(e) => (setName(e.target.value), setError(null))}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addOwn())}
          />
          <select className={`${fieldClass} w-44`} value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Type">
            {categories.map((c) => (
              <option key={c.key} value={c.key}>
                {c.icon} {c.label}
              </option>
            ))}
          </select>
          <Button variant="secondary" disabled={!name.trim() || full} onClick={addOwn}>
            ＋ Add
          </Button>
        </div>
        {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
      </div>
    </div>
  );
}

function Step({ title, hint, children }: { title: string; hint: string; children: ReactNode }) {
  return (
    <div>
      <h2 className="font-semibold">{title}</h2>
      <p className="mb-4 text-sm text-slate-500">{hint}</p>
      {children}
    </div>
  );
}

function Nothing({ what }: { what: string }) {
  return <p className="text-sm text-slate-500">No {what} for now. Go back to “Your home” to add some, or add them later in Settings.</p>;
}

function Summary({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-50 px-3 py-2">
      <dt className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</dt>
      <dd className="mt-0.5">{value}</dd>
    </div>
  );
}

/** One question with a number answer from a fixed range (a select, so it can't be out of range). */
function Question({
  icon,
  question,
  hint,
  value,
  min,
  max,
  onChange,
}: {
  icon: string;
  question: string;
  hint: string;
  value: number;
  min: number;
  max: number;
  onChange: (n: number) => void;
}) {
  return (
    <label className="flex items-center gap-3 rounded-2xl bg-slate-50 px-4 py-3 ring-1 ring-slate-100 transition hover:ring-indigo-200">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-xl shadow-sm">{icon}</span>
      <span className="min-w-0 flex-1">
        <span className="block font-medium text-slate-800">{question}</span>
        <span className="block text-xs text-slate-500">{hint}</span>
      </span>
      <select className={`${fieldClass} w-20 text-base font-semibold`} value={value} onChange={(e) => onChange(Number(e.target.value))} aria-label={question}>
        {Array.from({ length: max - min + 1 }, (_, i) => min + i).map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
    </label>
  );
}

function BillRow({ bill, people, onChange }: { bill: SetupBill; people: string[]; onChange: (b: SetupBill) => void }) {
  const [amount, setAmount] = useState(bill.amount_cents != null ? (bill.amount_cents / 100).toFixed(2) : "");
  const set = (patch: Partial<SetupBill>) => onChange({ ...bill, ...patch });

  return (
    <li className="space-y-2 rounded-xl border border-slate-100 bg-white/70 p-3">
      <div className="flex flex-wrap gap-2">
        <input className={`${fieldClass} w-16 text-center`} value={bill.icon} maxLength={16} onChange={(e) => set({ icon: e.target.value })} aria-label="Icon" />
        <input className={`${fieldClass} min-w-40 flex-1`} value={bill.name} maxLength={80} placeholder="e.g. WiFi" onChange={(e) => set({ name: e.target.value })} aria-label="Bill" />
        <select className={`${fieldClass} w-48`} value={bill.payer_mode} onChange={(e) => set({ payer_mode: e.target.value as SetupBill["payer_mode"], payer_name: e.target.value === "one" ? (bill.payer_name ?? people[0]) : null })} aria-label="Who pays">
          <option value="anyone">Anyone can pay</option>
          <option value="everyone">Everyone pays a share</option>
          <option value="one">One person pays</option>
        </select>
        {bill.payer_mode === "one" && (
          <select className={`${fieldClass} w-40`} value={bill.payer_name ?? ""} onChange={(e) => set({ payer_name: e.target.value })} aria-label="Who pays it">
            {people.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <select
          className={`${fieldClass} w-36`}
          value={bill.frequency}
          onChange={(e) => {
            const frequency = e.target.value as SetupBill["frequency"];
            set({ frequency, due_day: frequency === "weekly" && bill.due_day > 7 ? 1 : bill.due_day });
          }}
          aria-label="Repeats"
        >
          <option value="monthly">Every month</option>
          <option value="weekly">Every week</option>
          <option value="daily">Every day</option>
        </select>
        <DueDayField frequency={bill.frequency} value={bill.due_day} onChange={(due_day) => set({ due_day })} />
        <select className={`${fieldClass} w-52`} value={bill.amount_type} onChange={(e) => set({ amount_type: e.target.value as SetupBill["amount_type"] })} aria-label="Amount">
          <option value="fixed">Same amount every time</option>
          <option value="variable">Amount changes each time</option>
        </select>
        {bill.amount_type === "fixed" && (
          <input
            className={`${fieldClass} w-32`}
            inputMode="decimal"
            placeholder="Amount (optional)"
            value={amount}
            onChange={(e) => {
              setAmount(e.target.value);
              const cleaned = e.target.value.replace(/[,\s]/g, "");
              set({ amount_cents: cleaned === "" ? null : Math.round(Number(cleaned) * 100) });
            }}
            aria-label="Amount"
          />
        )}
      </div>
    </li>
  );
}
