import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui";
import { useHousehold } from "../households/hooks";

/**
 * "I did it" button with a ▾ menu to record that someone else did it.
 * The member list is only fetched when the menu is opened.
 */
export function DoneMenu({
  householdId,
  label,
  disabled,
  onDone,
}: {
  householdId: string;
  label: string;
  disabled?: boolean;
  onDone: (memberId?: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  return (
    <div ref={ref} className="relative flex shrink-0">
      <Button className="rounded-r-none" disabled={disabled} onClick={() => onDone()}>
        {label}
      </Button>
      <Button
        className="rounded-l-none border-l border-indigo-500 px-2"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        aria-label="Someone else did it"
        title="Someone else did it"
      >
        ▾
      </Button>
      {open && (
        <MemberPicker
          householdId={householdId}
          onPick={(id) => {
            setOpen(false);
            onDone(id);
          }}
        />
      )}
    </div>
  );
}

function MemberPicker({ householdId, onPick }: { householdId: string; onPick: (memberId: string) => void }) {
  const household = useHousehold(householdId);
  const members = (household.data?.members ?? []).filter((m) => m.id !== household.data?.my_member_id);
  return (
    <div className="absolute right-0 top-full z-10 mt-1 w-52 rounded-lg border border-slate-200 bg-white py-1 shadow-lg">
      <p className="px-3 py-1.5 text-xs font-medium text-slate-500">Someone else did it:</p>
      {household.isLoading && <p className="px-3 py-1.5 text-sm text-slate-400">Loading…</p>}
      {members.map((m) => (
        <button key={m.id} className="block w-full px-3 py-1.5 text-left text-sm hover:bg-indigo-50" onClick={() => onPick(m.id)}>
          {m.display_name}
        </button>
      ))}
    </div>
  );
}
