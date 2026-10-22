import { useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { Badge, Button, Empty, ErrorText, Loading } from "../../components/ui";
import {
  useAddShopping,
  useBought,
  useBoughtMany,
  useRemoveShopping,
  useShoppingList,
  useUndoBought,
  useUpdateShopping,
} from "../../features/shopping/hooks";
import { CATEGORIES, SHOPPING_PRESETS } from "../../features/shopping/presets";
import { formatTime, localIsoDate, relativeDay } from "../../lib/format";
import type { ShoppingItem } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

const fieldClass =
  "rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-sm shadow-sm outline-none transition placeholder:text-slate-400 hover:border-indigo-300 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15";

type Notice = { message: string; lost: boolean }; // lost: someone else bought it first (409)

function when(iso: string): string {
  return `${relativeDay(localIsoDate(new Date(iso)), localIsoDate())}, ${formatTime(iso)}`;
}

/** The house's shared shopping list: what's running out, and what was bought recently. */
export function GroceriesTab() {
  const household = useCurrentHousehold();
  const list = useShoppingList(household.id);
  const boughtMany = useBoughtMany(household.id);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Kept here, not in each row: a row moves to "Recently bought" when its status changes.
  const [notices, setNotices] = useState<Record<string, Notice>>({});
  const setNotice = (id: string, notice: Notice | null) =>
    setNotices(({ [id]: _, ...rest }) => (notice ? { ...rest, [id]: notice } : rest));

  if (list.isLoading) return <Loading />;
  const needed = list.data?.needed ?? [];
  const bought = list.data?.recently_bought ?? [];
  const picked = needed.filter((i) => selected.has(i.id));

  const toggle = (id: string) =>
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const buyPicked = () =>
    boughtMany.mutate(
      picked.map((i) => i.id),
      {
        onSuccess: (items) => {
          setSelected(new Set());
          // Anything someone else got to first keeps their name: say so.
          for (const i of items) {
            if (i.bought_by && i.bought_by.id !== household.my_member_id) {
              setNotice(i.id, { message: `${i.bought_by.display_name} already bought it`, lost: true });
            }
          }
        },
      },
    );

  return (
    <div className="space-y-8">
      <ErrorText error={list.error} />
      <AddItem householdId={household.id} onList={needed.map((i) => i.name)} suggestions={list.data?.suggestions ?? []} />

      <section className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="section-title">Needed · {needed.length}</h2>
          {picked.length > 0 && (
            <div className="ml-auto flex items-center gap-2">
              <Button variant="ghost" onClick={() => setSelected(new Set())}>
                Clear
              </Button>
              <Button disabled={boughtMany.isPending} onClick={buyPicked}>
                {boughtMany.isPending ? "Saving…" : `Mark ${picked.length} bought ✓`}
              </Button>
            </div>
          )}
        </div>
        <ErrorText error={boughtMany.error} />
        {needed.length === 0 ? (
          <Empty>Nothing on the list. Add what's running out above.</Empty>
        ) : (
          CATEGORIES.map((c) => {
            const items = needed.filter((i) => i.category === c.key);
            if (items.length === 0) return null;
            return (
              <div key={c.key} className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                  {c.icon} {c.label}
                </p>
                <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-white/70 bg-white/90 shadow-sm ring-1 ring-slate-900/5">
                  {items.map((item) => (
                    <NeededRow
                      key={item.id}
                      item={item}
                      checked={selected.has(item.id)}
                      onToggle={() => toggle(item.id)}
                      notice={notices[item.id]}
                      setNotice={(n) => setNotice(item.id, n)}
                    />
                  ))}
                </ul>
              </div>
            );
          })
        )}
      </section>

      {bought.length > 0 && (
        <section className="space-y-2">
          <h2 className="section-title">Recently bought</h2>
          <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-white/70 bg-white/80 shadow-sm ring-1 ring-slate-900/5">
            {bought.map((item) => (
              <BoughtRow key={item.id} item={item} notice={notices[item.id]} setNotice={(n) => setNotice(item.id, n)} />
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function AddItem({ householdId, onList, suggestions }: { householdId: string; onList: string[]; suggestions: string[] }) {
  const add = useAddShopping(householdId);
  const [name, setName] = useState("");
  const [quantity, setQuantity] = useState("");
  const listed = new Set(onList.map((n) => n.toLowerCase()));
  const chips = [...new Map([...suggestions, ...SHOPPING_PRESETS].map((n) => [n.toLowerCase(), n])).values()].filter(
    (n) => !listed.has(n.toLowerCase()),
  );

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    add.mutate({ name: name.trim(), quantity: quantity.trim() || undefined }, {
      onSuccess: () => {
        setName("");
        setQuantity("");
      },
    });
  };

  return (
    <div className="rounded-2xl border border-indigo-100 bg-white/90 p-4 shadow-sm ring-1 ring-indigo-50">
      <form onSubmit={submit} className="flex flex-wrap gap-2">
        <input
          className={`${fieldClass} min-w-40 flex-1`}
          placeholder="What's running out? e.g. Eggs"
          maxLength={80}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          className={`${fieldClass} w-36`}
          placeholder="How much? (optional)"
          maxLength={40}
          value={quantity}
          onChange={(e) => setQuantity(e.target.value)}
        />
        <Button type="submit" disabled={!name.trim() || add.isPending}>
          + Add
        </Button>
      </form>
      <div className="mt-2">
        <ErrorText error={add.error} />
      </div>
      {chips.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-xs text-slate-500">Quick add:</span>
          {chips.map((n) => (
            <button
              key={n}
              type="button"
              disabled={add.isPending}
              onClick={() => add.mutate({ name: n })}
              className={`rounded-full border px-2.5 py-1 text-xs transition hover:border-indigo-300 hover:text-indigo-700 ${
                suggestions.includes(n) ? "border-indigo-200 bg-indigo-50 text-indigo-700" : "border-slate-200 bg-white text-slate-600"
              }`}
              title={suggestions.includes(n) ? "Bought before" : undefined}
            >
              + {n}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function NeededRow({
  item,
  checked,
  onToggle,
  notice,
  setNotice,
}: {
  item: ShoppingItem;
  checked: boolean;
  onToggle: () => void;
  notice?: Notice;
  setNotice: (n: Notice | null) => void;
}) {
  const bought = useBought();
  const remove = useRemoveShopping();
  const update = useUpdateShopping();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(item.name);
  const [quantity, setQuantity] = useState(item.quantity ?? "");
  const [note, setNote] = useState(item.note ?? "");
  const busy = bought.isPending || remove.isPending || update.isPending;
  const handlers = {
    onSuccess: () => setNotice(null),
    onError: (error: Error) => setNotice({ message: error.message, lost: error instanceof ApiError && error.status === 409 }),
  };

  if (editing) {
    return (
      <li className="px-4 py-3">
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            update.mutate(
              { id: item.id, name: name.trim(), quantity: quantity.trim(), note: note.trim() },
              { onSuccess: () => (setEditing(false), setNotice(null)), onError: handlers.onError },
            );
          }}
        >
          <input className={`${fieldClass} min-w-32 flex-1`} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} />
          <input className={`${fieldClass} w-32`} placeholder="How much?" value={quantity} maxLength={40} onChange={(e) => setQuantity(e.target.value)} />
          <input className={`${fieldClass} min-w-40 flex-1`} placeholder="Note, e.g. the brown one" value={note} maxLength={200} onChange={(e) => setNote(e.target.value)} />
          <Button type="submit" disabled={!name.trim() || busy}>
            Save
          </Button>
          <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </form>
        {notice && <NoticeLine notice={notice} onDismiss={() => setNotice(null)} />}
      </li>
    );
  }

  return (
    <li className={`px-4 py-3 transition ${checked ? "bg-indigo-50/60" : "hover:bg-indigo-50/30"}`}>
      <div className="flex items-center gap-3">
        <input
          type="checkbox"
          className="h-4 w-4 accent-indigo-600"
          checked={checked}
          onChange={onToggle}
          aria-label={`Select ${item.name}`}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{item.name}</span>
            {item.quantity && <Badge>{item.quantity}</Badge>}
          </div>
          {item.note && <p className="text-sm text-slate-600">{item.note}</p>}
          <p className="text-xs text-slate-400">
            Added by {item.added_by?.display_name ?? "someone"} · {when(item.created_at)}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button variant="ghost" disabled={busy} onClick={() => setEditing(true)} aria-label={`Edit ${item.name}`}>
            ✏️
          </Button>
          <Button variant="ghost" disabled={busy} onClick={() => remove.mutate(item.id, handlers)} aria-label={`Remove ${item.name}`} title="Take it off the list">
            ✕
          </Button>
          <Button disabled={busy} onClick={() => bought.mutate(item.id, handlers)}>
            {bought.isPending ? "Saving…" : "Bought ✓"}
          </Button>
        </div>
      </div>
      {notice && <NoticeLine notice={notice} onDismiss={() => setNotice(null)} />}
    </li>
  );
}

function BoughtRow({ item, notice, setNotice }: { item: ShoppingItem; notice?: Notice; setNotice: (n: Notice | null) => void }) {
  const undo = useUndoBought();
  return (
    <li className="px-4 py-2.5">
      <div className="flex items-center gap-3">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-xs text-emerald-700">✓</span>
        <div className="min-w-0 flex-1 text-sm">
          <span className="text-slate-500 line-through">{item.name}</span>
          {item.quantity && <span className="text-slate-400"> · {item.quantity}</span>}
          <span className="ml-2 text-xs font-medium text-emerald-700">
            {item.bought_by?.display_name ?? "Someone"} bought it · {item.bought_at && when(item.bought_at)}
          </span>
        </div>
        {item.can_undo && (
          <Button
            variant="ghost"
            disabled={undo.isPending}
            onClick={() =>
              undo.mutate(item.id, {
                onSuccess: () => setNotice(null),
                onError: (e) => setNotice({ message: e.message, lost: e instanceof ApiError && e.status === 409 }),
              })
            }
          >
            Undo
          </Button>
        )}
      </div>
      {notice && <NoticeLine notice={notice} onDismiss={() => setNotice(null)} />}
    </li>
  );
}

function NoticeLine({ notice, onDismiss }: { notice: Notice; onDismiss: () => void }) {
  return (
    <div
      className={`mt-2 flex items-center gap-2 rounded-xl px-3 py-1.5 text-sm ring-1 ${
        notice.lost ? "bg-slate-50 text-slate-600 ring-slate-200" : "bg-red-50 text-red-700 ring-red-100"
      }`}
    >
      <span className="flex-1">{notice.message}</span>
      <button className="opacity-60 hover:opacity-100" aria-label="Dismiss" onClick={onDismiss}>
        ×
      </button>
    </div>
  );
}
