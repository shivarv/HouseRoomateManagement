import { useEffect, useRef, useState } from "react";
import { Button } from "../../components/ui";
import { useHousehold } from "../households/hooks";

export interface MenuAction {
  label: string;
  title?: string;
  onClick: () => void;
}

/**
 * "I did it" button with a ▾ menu to record that someone else did it, plus any extra
 * `actions` (e.g. "Ask for a swap"). The member list is only fetched when the menu is opened.
 */
export function DoneMenu({
  householdId,
  label,
  disabled,
  onDone,
  actions = [],
}: {
  householdId: string;
  label: string;
  disabled?: boolean;
  onDone: (memberId?: string) => void;
  actions?: MenuAction[];
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
    <div ref={ref} className="relative flex shrink-0" data-open={open || undefined}>
      <Button className="rounded-r-none" disabled={disabled} onClick={() => onDone()}>
        {label}
      </Button>
      <Button
        className="rounded-l-none border-l border-white/25 px-2"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        aria-label="More options"
        title="Someone else did it, or ask for a swap"
      >
        ▾
      </Button>
      {open && (
        <MemberPicker
          householdId={householdId}
          actions={actions}
          onPick={(id) => {
            setOpen(false);
            onDone(id);
          }}
          onAction={(action) => {
            setOpen(false);
            action.onClick();
          }}
        />
      )}
    </div>
  );
}

const itemClass =
  "block w-full px-3 py-2 text-left text-sm transition hover:bg-linear-to-r hover:from-indigo-50 hover:to-fuchsia-50 hover:text-indigo-700";

function MemberPicker({
  householdId,
  actions,
  onPick,
  onAction,
}: {
  householdId: string;
  actions: MenuAction[];
  onPick: (memberId: string) => void;
  onAction: (action: MenuAction) => void;
}) {
  const household = useHousehold(householdId);
  const members = (household.data?.members ?? []).filter((m) => m.id !== household.data?.my_member_id);
  return (
    <div className="absolute right-0 top-full z-30 mt-2 w-56 overflow-hidden rounded-2xl border border-white/70 bg-white/95 py-1.5 shadow-xl shadow-indigo-500/10 ring-1 ring-slate-900/5 backdrop-blur">
      <p className="px-3 py-1.5 text-xs font-medium text-slate-500">Someone else did it:</p>
      {household.isLoading && <p className="px-3 py-1.5 text-sm text-slate-400">Loading…</p>}
      {members.map((m) => (
        <button key={m.id} className={itemClass} onClick={() => onPick(m.id)}>
          {m.display_name}
        </button>
      ))}
      {actions.length > 0 && (
        <div className="mt-1.5 border-t border-slate-100 pt-1.5">
          {actions.map((a) => (
            <button key={a.label} className={`${itemClass} font-medium text-indigo-700`} title={a.title} onClick={() => onAction(a)}>
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
