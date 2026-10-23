import { useState, type FormEvent } from "react";
import { subTab, subTabTray } from "../../lib/tabStyles";
import { Link, Navigate, NavLink, Outlet, useNavigate } from "react-router";
import { Badge, Button, Card, ErrorText, Input } from "../../components/ui";
import { useDeleteHousehold, useHouseholds, useUpdateHousehold } from "../../features/households/hooks";
import type { Household } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

const section = subTab;

/** Household settings: everything only an admin can change, kept out of the everyday tabs. */
export function SettingsLayout() {
  const household = useCurrentHousehold();
  if (household.my_role !== "admin") return <Navigate to={`/households/${household.id}`} replace />;

  return (
    <div className="space-y-6">
      <nav className="flex flex-wrap items-center gap-2">
        <span className="mr-1 text-xs font-semibold uppercase tracking-widest text-slate-400">Admin only</span>
        <div className={subTabTray}>
        <NavLink to="" end className={section}>House details</NavLink>
        <NavLink to="people" className={section}>Roommates</NavLink>
        <NavLink to="chores" className={section}>Chores</NavLink>
        <NavLink to="groceries" className={section}>Groceries</NavLink>
        <NavLink to="reminders" className={section}>Reminders</NavLink>
        <NavLink to="history" className={section}>Past months</NavLink>
        </div>
        <Link
          to="/households/new/setup"
          className="ml-auto whitespace-nowrap rounded-xl bg-white px-3.5 py-1.5 text-sm font-semibold text-indigo-700 shadow-sm ring-1 ring-indigo-200 transition-all duration-200 hover:-translate-y-px hover:shadow-md hover:shadow-indigo-500/15 hover:ring-indigo-300 active:translate-y-0"
          title="Set up another home from a template"
        >
          ＋ New home from a template
        </Link>
      </nav>
      <Outlet context={household} />
    </div>
  );
}

export function HouseDetailsSettings() {
  return (
    <div className="space-y-6">
      <HouseDetailsForm />
      <YourHomes />
    </div>
  );
}

/** Homes I'm an admin of, to delete. The last one stays: everyone keeps a home they run. */
function YourHomes() {
  const current = useCurrentHousehold();
  const households = useHouseholds();
  const remove = useDeleteHousehold();
  const navigate = useNavigate();
  const [confirming, setConfirming] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const mine = (households.data ?? []).filter((h) => h.my_role === "admin");
  const last = mine.length <= 1;

  const onDelete = (h: Household) =>
    remove.mutate(h.id, {
      onSuccess: () => {
        setConfirming(null);
        setTyped("");
        // Deleted the one I'm looking at: go home; the header picks another house.
        if (h.id === current.id) navigate("/", { replace: true });
      },
    });

  return (
    <Card className="border-red-100 ring-1 ring-red-50">
      <h2 className="mb-1 font-semibold">Your homes</h2>
      <p className="mb-4 text-sm text-slate-500">
        Homes you're an admin of. Deleting one removes it for everyone in it, with its chores, groceries, bills and
        history. You always keep at least one, so the last one can't be deleted.
      </p>
      <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-100">
        {mine.map((h) => (
          <li key={h.id} className="space-y-2 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">🏠 {h.name}</span>
              {h.address && <span className="text-xs text-slate-500">{h.address}</span>}
              {h.id === current.id && <Badge tone="indigo">Open now</Badge>}
              {confirming !== h.id && (
                <Button
                  variant="ghost"
                  className="ml-auto text-red-600"
                  disabled={last || remove.isPending}
                  title={last ? "This is your last home as admin, so it can't be deleted" : undefined}
                  onClick={() => (setConfirming(h.id), setTyped(""))}
                >
                  Delete…
                </Button>
              )}
            </div>
            {confirming === h.id && (
              <div className="flex flex-wrap items-center gap-2 rounded-xl bg-red-50 p-3 ring-1 ring-red-100">
                <span className="text-sm text-red-800">
                  Type <b>{h.name}</b> to delete it for everyone:
                </span>
                <input
                  className="w-48 rounded-lg border border-red-200 bg-white px-2 py-1 text-sm outline-none focus:border-red-400"
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  autoFocus
                  aria-label={`Type ${h.name} to confirm`}
                />
                <Button
                  variant="danger"
                  disabled={typed.trim().toLowerCase() !== h.name.toLowerCase() || remove.isPending}
                  onClick={() => onDelete(h)}
                >
                  {remove.isPending ? "Deleting…" : "Delete home"}
                </Button>
                <Button variant="ghost" onClick={() => setConfirming(null)}>
                  Cancel
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
      {last && <p className="mt-3 text-xs text-slate-500">To delete this one, first set up another home you run.</p>}
      <ErrorText error={remove.error} />
    </Card>
  );
}

function HouseDetailsForm() {
  const household = useCurrentHousehold();
  const update = useUpdateHousehold(household.id);
  const [name, setName] = useState(household.name);
  const [address, setAddress] = useState(household.address ?? "");
  const [timezone, setTimezone] = useState(household.timezone);
  const changed =
    name.trim() !== household.name ||
    address.trim() !== (household.address ?? "") ||
    timezone.trim() !== household.timezone;

  const onSave = (e: FormEvent) => {
    e.preventDefault();
    update.mutate({ name: name.trim(), address: address.trim(), timezone: timezone.trim() });
  };

  return (
    <Card>
      <h2 className="mb-1 font-semibold">House details</h2>
      <p className="mb-4 text-sm text-slate-500">
        The timezone decides when "today" starts for everyone in the house.
      </p>
      <form onSubmit={onSave} className="space-y-3">
        <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} />
        <Input
          label="Address"
          placeholder="e.g. 12 Maple Street, Boston, MA"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          required
          maxLength={300}
        />
        <Input
          label="Timezone"
          placeholder="e.g. America/New_York"
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
          required
        />
        <ErrorText error={update.error} />
        <div className="flex items-center gap-3">
          <Button type="submit" disabled={!changed || update.isPending}>
            {update.isPending ? "Saving…" : "Save"}
          </Button>
          {update.isSuccess && !changed && <span className="text-sm text-emerald-600">Saved</span>}
        </div>
      </form>
    </Card>
  );
}
