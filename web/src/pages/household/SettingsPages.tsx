import { useState, type FormEvent } from "react";
import { Navigate, NavLink, Outlet } from "react-router";
import { Button, Card, ErrorText, Input } from "../../components/ui";
import { useUpdateHousehold } from "../../features/households/hooks";
import { useCurrentHousehold } from "./HouseholdLayout";

const section = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-xl px-3.5 py-1.5 text-sm font-medium transition-all duration-200 ${
    isActive
      ? "bg-linear-to-r from-indigo-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30"
      : "text-slate-600 hover:bg-white/70 hover:text-slate-900"
  }`;

/** Household settings: everything only an admin can change, kept out of the everyday tabs. */
export function SettingsLayout() {
  const household = useCurrentHousehold();
  if (household.my_role !== "admin") return <Navigate to={`/households/${household.id}`} replace />;

  return (
    <div className="space-y-6">
      <nav className="flex flex-wrap items-center gap-1">
        <span className="mr-2 text-xs font-semibold uppercase tracking-widest text-slate-400">Admin only</span>
        <NavLink to="" end className={section}>House details</NavLink>
        <NavLink to="people" className={section}>Roommates</NavLink>
        <NavLink to="chores" className={section}>Chores</NavLink>
        <NavLink to="history" className={section}>Past months</NavLink>
      </nav>
      <Outlet context={household} />
    </div>
  );
}

export function HouseDetailsSettings() {
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
