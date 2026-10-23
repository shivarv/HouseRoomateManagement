import { useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { grocerySettingsApi } from "../../api/shopping";
import { Badge, Button, Card, Empty, ErrorText, Loading } from "../../components/ui";
import { useGrocerySettings, useGrocerySettingsChange } from "../../features/shopping/hooks";
import { useUnsavedChangesGuard } from "../../lib/unsavedChanges";
import type { GroceryCategory, GroceryPreset, GrocerySettings, GrocerySuggestion } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

const fieldClass =
  "rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-sm shadow-sm outline-none transition placeholder:text-slate-400 hover:border-indigo-300 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15";

const LEAVE_PROMPT = "You have unsaved grocery changes. Leave and discard them?";
const AUTO = ""; // category picked from the name when the item is saved

type PresetEdit = { name?: string; category_key?: string };
type CategoryEdit = { label?: string; icon?: string };
type NewPreset = { tempId: string; name: string; category_key: string };
type NewCategory = { tempId: string; label: string; icon: string };

/**
 * Every change on this page, unsaved: nothing reaches the server until "Save changes".
 * Saved rows are changed by id, so a refetch doesn't throw the draft away. New categories get a
 * temporary key ("new:<tempId>") that new or edited items can already use; saving swaps in the real one.
 */
interface Draft {
  newPresets: NewPreset[];
  presetEdits: Record<string, PresetEdit>;
  presetRemoved: string[];
  newCategories: NewCategory[];
  categoryEdits: Record<string, CategoryEdit>;
  categoryRemoved: string[];
  categoryOrder: string[] | null;
  dismissed: string[]; // suggestion names
}

const EMPTY: Draft = {
  newPresets: [],
  presetEdits: {},
  presetRemoved: [],
  newCategories: [],
  categoryEdits: {},
  categoryRemoved: [],
  categoryOrder: null,
  dismissed: [],
};

type SetDraft = (update: (d: Draft) => Draft) => void;
type CategoryView = GroceryCategory & { isNew?: boolean };
type PresetView = GroceryPreset & { isNew?: boolean };

let seq = 0;
const tempId = () => `t${++seq}`;
const tempKey = (id: string) => `new:${id}`;
const same = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

/** Rows in the draft's order; rows the draft doesn't know keep their place after the others. */
function ordered<T extends { id: string }>(rows: T[], order: string[] | null): T[] {
  if (!order) return rows;
  const rank = new Map(order.map((id, i) => [id, i]));
  return [...rows].sort((a, b) => (rank.get(a.id) ?? Infinity) - (rank.get(b.id) ?? Infinity));
}

/** Only the fields that differ from the saved row, so changing something back clears the edit. */
function diff<T extends object>(saved: T, edit: Partial<T>): Partial<T> {
  return Object.fromEntries(Object.entries(edit).filter(([k, v]) => saved[k as keyof T] !== v)) as Partial<T>;
}

function sameOrder(saved: { id: string }[], order: string[] | null, removed: string[]): boolean {
  if (!order) return true;
  const kept = saved.filter((r) => !removed.includes(r.id));
  const draft = ordered(kept, order);
  return kept.every((r, i) => r.id === draft[i].id);
}

function countChanges(data: GrocerySettings, d: Draft): number {
  const edits = (rows: { id: string }[], all: Record<string, object>, removed: string[]) =>
    Object.entries(all).filter(([id, edit]) => {
      const saved = rows.find((r) => r.id === id);
      return saved && !removed.includes(id) && Object.keys(diff(saved, edit)).length > 0;
    }).length;
  return (
    d.newPresets.length +
    d.newCategories.length +
    d.dismissed.length +
    edits(data.presets, d.presetEdits, d.presetRemoved) +
    edits(data.categories, d.categoryEdits, d.categoryRemoved) +
    d.presetRemoved.length +
    d.categoryRemoved.length +
    (sameOrder(data.categories, d.categoryOrder, d.categoryRemoved) ? 0 : 1)
  );
}

/** Settings → Groceries: the house's list sections, its quick-add items, and new things people added. */
export function GrocerySettingsPage() {
  const household = useCurrentHousehold();
  const settings = useGrocerySettings(household.id);
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  const data = settings.data;
  const changes = data ? countChanges(data, draft) : 0;
  useUnsavedChangesGuard(changes > 0, LEAVE_PROMPT);

  if (settings.isLoading) return <Loading />;
  if (!data) return <ErrorText error={settings.error ?? "Couldn't load the grocery settings"} />;

  // What the admin sees: saved data with the draft applied. Removed rows stay, crossed out.
  const categories: CategoryView[] = [
    ...ordered(
      data.categories.map((c) => ({ ...c, ...draft.categoryEdits[c.id] })),
      draft.categoryOrder,
    ),
    ...draft.newCategories.map((n, i) => ({
      id: n.tempId,
      key: tempKey(n.tempId),
      label: n.label,
      icon: n.icon || "🛍️",
      position: data.categories.length + i,
      can_delete: true,
      isNew: true,
    })),
  ];
  const liveCategories = categories.filter((c) => !draft.categoryRemoved.includes(c.id));
  // Alphabetical from the server; new ones at the end of their type until saved.
  const presets: PresetView[] = [
    ...data.presets.map((p) => ({ ...p, ...draft.presetEdits[p.id] })),
    ...draft.newPresets.map((n, i) => ({
      id: n.tempId,
      name: n.name,
      category_key: n.category_key,
      position: data.presets.length + i,
      isNew: true,
    })),
  ];
  const livePresets = presets.filter((p) => !draft.presetRemoved.includes(p.id));

  const blank =
    livePresets.some((p) => !p.name.trim()) || liveCategories.some((c) => !c.label.trim() || !c.icon.trim());

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    // Step by step. Each step leaves the draft once it's saved, so a failure keeps only what's left.
    const keys = new Map<string, string>(); // temporary category key → real key
    const real = (key: string) => keys.get(key) ?? key;
    const createdCategories: string[] = [];
    try {
      for (const n of draft.newCategories) {
        const created = await grocerySettingsApi.addCategory(household.id, {
          label: n.label.trim(),
          icon: n.icon.trim() || undefined,
        });
        keys.set(tempKey(n.tempId), created.key);
        createdCategories.push(created.id);
        const swap = (key: string) => (key === tempKey(n.tempId) ? created.key : key);
        setDraft((d) => ({
          ...d,
          newCategories: d.newCategories.filter((x) => x.tempId !== n.tempId),
          newPresets: d.newPresets.map((p) => ({ ...p, category_key: swap(p.category_key) })),
          presetEdits: Object.fromEntries(
            Object.entries(d.presetEdits).map(([id, e]) => [
              id,
              e.category_key ? { ...e, category_key: swap(e.category_key) } : e,
            ]),
          ),
        }));
      }
      for (const [id, edit] of Object.entries(draft.categoryEdits)) {
        const saved = data.categories.find((c) => c.id === id);
        if (saved && !draft.categoryRemoved.includes(id)) {
          const body = diff(saved, edit);
          if (Object.keys(body).length)
            await grocerySettingsApi.updateCategory(id, { label: body.label?.trim(), icon: body.icon?.trim() });
        }
        setDraft(({ categoryEdits: { [id]: _, ...rest }, ...d }) => ({ ...d, categoryEdits: rest }));
      }
      for (const n of draft.newPresets) {
        await grocerySettingsApi.addPreset(household.id, {
          name: n.name.trim(),
          category_key: n.category_key ? real(n.category_key) : undefined,
        });
        setDraft((d) => ({ ...d, newPresets: d.newPresets.filter((x) => x.tempId !== n.tempId) }));
      }
      for (const [id, edit] of Object.entries(draft.presetEdits)) {
        const saved = data.presets.find((p) => p.id === id);
        if (saved && !draft.presetRemoved.includes(id)) {
          const body = diff(saved, edit);
          if (Object.keys(body).length)
            await grocerySettingsApi.updatePreset(id, {
              name: body.name?.trim(),
              category_key: body.category_key ? real(body.category_key) : undefined,
            });
        }
        setDraft(({ presetEdits: { [id]: _, ...rest }, ...d }) => ({ ...d, presetEdits: rest }));
      }
      for (const name of draft.dismissed) {
        await grocerySettingsApi.dismissSuggestion(household.id, name);
        setDraft((d) => ({ ...d, dismissed: d.dismissed.filter((x) => x !== name) }));
      }
      for (const id of draft.presetRemoved) {
        await grocerySettingsApi.removePreset(id);
        setDraft((d) => ({ ...d, presetRemoved: d.presetRemoved.filter((x) => x !== id) }));
      }
      for (const id of draft.categoryRemoved) {
        await grocerySettingsApi.deleteCategory(id);
        setDraft((d) => ({ ...d, categoryRemoved: d.categoryRemoved.filter((x) => x !== id) }));
      }
      // New rows were created at the end, which is also where the draft shows them.
      if (!sameOrder(data.categories, draft.categoryOrder, draft.categoryRemoved)) {
        const kept = data.categories.filter((c) => !draft.categoryRemoved.includes(c.id));
        await grocerySettingsApi.orderCategories(household.id, [
          ...ordered(kept, draft.categoryOrder).map((c) => c.id),
          ...createdCategories,
        ]);
      }
      setDraft((d) => ({ ...d, categoryOrder: null }));
    } catch (error) {
      setSaveError(error);
    } finally {
      setSaving(false);
      await Promise.all(
        ["grocery-settings", "shopping"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
      );
    }
  };

  return (
    <div className="space-y-6 pb-20">
      {data.suggestions.length > 0 && (
        <Suggestions
          suggestions={data.suggestions}
          categories={liveCategories}
          presets={livePresets}
          draft={draft}
          setDraft={setDraft}
          disabled={saving}
        />
      )}
      <QuickAdd
        householdId={household.id}
        saved={data.presets}
        presets={presets}
        livePresets={livePresets}
        categories={liveCategories}
        draft={draft}
        setDraft={setDraft}
        disabled={saving}
      />
      <Categories saved={data.categories} categories={categories} draft={draft} setDraft={setDraft} disabled={saving} />

      {(changes > 0 || saveError != null) && (
        <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-3 rounded-2xl border border-indigo-200 bg-white/95 px-4 py-3 shadow-lg shadow-indigo-500/10 backdrop-blur">
          <span className="text-sm font-medium text-slate-700">
            {changes > 0 ? `${changes} unsaved change${changes === 1 ? "" : "s"}` : "Some changes couldn't be saved"}
          </span>
          <div className="min-w-0 flex-1">
            {blank ? <p className="text-sm text-red-600">Names can't be empty.</p> : <ErrorText error={saveError} />}
          </div>
          <Button
            variant="ghost"
            disabled={saving}
            onClick={() => {
              setDraft(EMPTY);
              setSaveError(null);
            }}
          >
            Discard
          </Button>
          <Button disabled={saving || changes === 0 || blank} onClick={save}>
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      )}
    </div>
  );
}

function CategorySelect({
  categories,
  value,
  onChange,
  auto = false,
  disabled,
}: {
  categories: CategoryView[];
  value: string;
  onChange: (key: string) => void;
  auto?: boolean;
  disabled?: boolean;
}) {
  return (
    <select
      className={`${fieldClass} w-40`}
      aria-label="Category"
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
    >
      {auto && <option value={AUTO}>Category: auto</option>}
      {categories.map((c) => (
        <option key={c.key} value={c.key}>
          {c.icon} {c.label || "(unnamed)"}
          {c.isNew ? " · new" : ""}
        </option>
      ))}
    </select>
  );
}

/** "New" / "Edited" / "Will be removed", with Undo. */
function RowState({ state, onUndo }: { state: "new" | "edited" | "removed" | null; onUndo: () => void }) {
  if (!state) return null;
  const text = { new: "New", edited: "Edited", removed: "Will be removed" }[state];
  return (
    <>
      <Badge tone={state === "new" ? "green" : "amber"}>{text}</Badge>
      <Button type="button" variant="ghost" onClick={onUndo}>
        Undo
      </Button>
    </>
  );
}

const rowTint = (state: "new" | "edited" | "removed" | null) =>
  state === "removed" ? "bg-red-50/50" : state === "edited" ? "bg-amber-50/50" : state === "new" ? "bg-emerald-50/50" : "";

// --- New things people added ---------------------------------------------------------------------

function Suggestions({
  suggestions,
  categories,
  presets,
  draft,
  setDraft,
  disabled,
}: {
  suggestions: GrocerySuggestion[];
  categories: CategoryView[];
  presets: PresetView[];
  draft: Draft;
  setDraft: SetDraft;
  disabled: boolean;
}) {
  // Accepted ones show up under Quick-add items instead.
  const open = suggestions.filter((s) => !presets.some((p) => same(p.name, s.name)));
  if (open.length === 0) return null;
  return (
    <Card className="border-indigo-200 ring-1 ring-indigo-100">
      <h2 className="mb-1 font-semibold">✨ New items your house added</h2>
      <p className="mb-4 text-sm text-slate-500">
        Not quick-add items yet. Add the ones you buy often so everyone gets a one-tap button.
      </p>
      <ul className="divide-y divide-slate-100">
        {open.map((s) => (
          <SuggestionRow
            key={s.name.toLowerCase()}
            suggestion={s}
            categories={categories}
            dismissed={draft.dismissed.includes(s.name)}
            setDraft={setDraft}
            disabled={disabled}
          />
        ))}
      </ul>
    </Card>
  );
}

function SuggestionRow({
  suggestion,
  categories,
  dismissed,
  setDraft,
  disabled,
}: {
  suggestion: GrocerySuggestion;
  categories: CategoryView[];
  dismissed: boolean;
  setDraft: SetDraft;
  disabled: boolean;
}) {
  const known = categories.some((c) => c.key === suggestion.category_key);
  const [category, setCategory] = useState(known ? suggestion.category_key : "other");
  const accept = () =>
    setDraft((d) => ({
      ...d,
      newPresets: [...d.newPresets, { tempId: tempId(), name: suggestion.name, category_key: category }],
    }));
  const toggleDismiss = () =>
    setDraft((d) => ({
      ...d,
      dismissed: dismissed ? d.dismissed.filter((n) => n !== suggestion.name) : [...d.dismissed, suggestion.name],
    }));

  return (
    <li className={`flex flex-wrap items-center gap-2 py-2.5 ${dismissed ? "opacity-70" : ""}`}>
      <span className={`font-medium ${dismissed ? "text-slate-400 line-through" : ""}`}>{suggestion.name}</span>
      <Badge tone="indigo">added {suggestion.times_added}×</Badge>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        {dismissed ? (
          <RowState state="removed" onUndo={toggleDismiss} />
        ) : (
          <>
            <CategorySelect categories={categories} value={category} onChange={setCategory} disabled={disabled} />
            <Button disabled={disabled} onClick={accept}>
              + Add to quick add
            </Button>
            <Button variant="ghost" disabled={disabled} onClick={toggleDismiss} title="Stop suggesting it">
              Dismiss
            </Button>
          </>
        )}
      </div>
    </li>
  );
}

// --- Quick-add items ------------------------------------------------------------------------------

function QuickAdd({
  householdId,
  saved,
  presets,
  livePresets,
  categories,
  draft,
  setDraft,
  disabled,
}: {
  householdId: string;
  saved: GroceryPreset[];
  presets: PresetView[];
  livePresets: PresetView[];
  categories: CategoryView[];
  draft: Draft;
  setDraft: SetDraft;
  disabled: boolean;
}) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState(AUTO);
  const [error, setError] = useState<string | null>(null);
  // Restoring adds the standard items straight away, so it's only offered with nothing unsaved.
  const restore = useGrocerySettingsChange(() => grocerySettingsApi.restore(householdId));
  const known = new Set(categories.map((c) => c.key));
  const groupOf = (p: PresetView) =>
    p.isNew && p.category_key === AUTO ? AUTO : known.has(p.category_key) ? p.category_key : "other";
  const untouched =
    draft.newPresets.length + draft.presetRemoved.length + Object.keys(draft.presetEdits).length === 0 &&
    draft.newCategories.length + draft.categoryRemoved.length + Object.keys(draft.categoryEdits).length === 0 &&
    !draft.categoryOrder &&
    draft.dismissed.length === 0;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    if (livePresets.some((p) => same(p.name, name))) {
      setError(`${name.trim()} is already a quick-add item`);
      return;
    }
    setDraft((d) => ({ ...d, newPresets: [...d.newPresets, { tempId: tempId(), name: name.trim(), category_key: category }] }));
    setName("");
    setCategory(AUTO);
    setError(null);
  };

  const edit = (p: PresetView, patch: PresetEdit) =>
    setDraft((d) => {
      if (p.isNew) {
        return { ...d, newPresets: d.newPresets.map((n) => (n.tempId === p.id ? { ...n, ...patch } : n)) };
      }
      const merged = diff(saved.find((s) => s.id === p.id)!, { ...d.presetEdits[p.id], ...patch });
      const { [p.id]: _, ...rest } = d.presetEdits;
      return { ...d, presetEdits: Object.keys(merged).length ? { ...rest, [p.id]: merged } : rest };
    });
  const remove = (p: PresetView) =>
    setDraft((d) =>
      p.isNew
        ? { ...d, newPresets: d.newPresets.filter((n) => n.tempId !== p.id) }
        : { ...d, presetRemoved: [...d.presetRemoved, p.id] },
    );
  const undo = (p: PresetView) =>
    setDraft(({ presetEdits: { [p.id]: _, ...rest }, ...d }) =>
      p.isNew
        ? { ...d, presetEdits: rest, newPresets: d.newPresets.filter((n) => n.tempId !== p.id) }
        : { ...d, presetEdits: rest, presetRemoved: d.presetRemoved.filter((x) => x !== p.id) },
    );

  const groups = [
    ...(presets.some((p) => groupOf(p) === AUTO)
      ? [{ key: AUTO, title: "✨ New · category picked from the name when saved" }]
      : []),
    ...categories.map((c) => ({ key: c.key, title: `${c.icon} ${c.label}` })),
  ];

  return (
    <Card>
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <h2 className="font-semibold">Quick-add items</h2>
        <Button
          variant="ghost"
          className="ml-auto"
          disabled={restore.isPending || disabled || !untouched}
          title={untouched ? undefined : "Save or discard your changes first"}
          onClick={() => confirm("Bring back any standard items or categories you removed? Your own ones stay.") && restore.mutate(undefined)}
        >
          Restore standard items
        </Button>
      </div>
      <p className="mb-4 text-sm text-slate-500">
        The one-tap buttons on the Groceries tab: just a name and a type (the type sets the icon). Nothing changes for the
        house until you press “Save changes”.
      </p>
      <form onSubmit={submit} className="mb-4 flex flex-wrap gap-2">
        <input
          className={`${fieldClass} min-w-40 flex-1`}
          placeholder="e.g. Paneer"
          maxLength={80}
          value={name}
          onChange={(e) => (setName(e.target.value), setError(null))}
        />
        <CategorySelect categories={categories} value={category} onChange={setCategory} auto />
        <Button type="submit" disabled={!name.trim() || disabled}>
          + Add
        </Button>
      </form>
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      <ErrorText error={restore.error} />

      {presets.length === 0 ? (
        <Empty>No quick-add items. Add some above, or restore the standard ones.</Empty>
      ) : (
        <div className="space-y-4">
          {groups.map((g) => {
            const group = presets.filter((p) => groupOf(p) === g.key);
            if (group.length === 0) return null;
            return (
              <div key={g.key || "auto"}>
                <p className="mb-1 text-xs font-semibold uppercase tracking-widest text-slate-400">{g.title}</p>
                <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-100">
                  {group.map((p) => {
                    const state = p.isNew
                      ? "new"
                      : draft.presetRemoved.includes(p.id)
                        ? "removed"
                        : draft.presetEdits[p.id]
                          ? "edited"
                          : null;
                    return (
                      <PresetRow
                        key={p.id}
                        preset={p}
                        categories={categories}
                        state={state}
                        disabled={disabled}
                        onEdit={(patch) => edit(p, patch)}
                        onRemove={() => remove(p)}
                        onUndo={() => undo(p)}
                      />
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function PresetRow({
  preset,
  categories,
  state,
  disabled,
  onEdit,
  onRemove,
  onUndo,
}: {
  preset: PresetView;
  categories: CategoryView[];
  state: "new" | "edited" | "removed" | null;
  disabled: boolean;
  onEdit: (patch: PresetEdit) => void;
  onRemove: () => void;
  onUndo: () => void;
}) {
  const removed = state === "removed";
  const known = categories.some((c) => c.key === preset.category_key);
  const value = preset.isNew && preset.category_key === AUTO ? AUTO : known ? preset.category_key : "other";

  return (
    <li className={`flex flex-wrap items-center gap-2 px-3 py-2 ${rowTint(state)}`}>
      <input
        className={`${fieldClass} min-w-32 flex-1 ${removed ? "text-slate-400 line-through" : ""}`}
        value={preset.name}
        maxLength={80}
        disabled={removed || disabled}
        onChange={(e) => onEdit({ name: e.target.value })}
        aria-label="Name"
      />
      <CategorySelect
        categories={categories}
        value={value}
        auto={preset.isNew}
        disabled={removed || disabled}
        onChange={(key) => onEdit({ category_key: key })}
      />
      <RowState state={state} onUndo={onUndo} />
      {!removed && state !== "new" && (
        <Button variant="ghost" disabled={disabled} onClick={onRemove} aria-label={`Remove ${preset.name}`} title="Remove from quick add">
          ✕
        </Button>
      )}
    </li>
  );
}

// --- Categories -----------------------------------------------------------------------------------

function Categories({
  saved,
  categories,
  draft,
  setDraft,
  disabled,
}: {
  saved: GroceryCategory[];
  categories: CategoryView[];
  draft: Draft;
  setDraft: SetDraft;
  disabled: boolean;
}) {
  const [label, setLabel] = useState("");
  const [icon, setIcon] = useState("");
  const [error, setError] = useState<string | null>(null);
  const live = categories.filter((c) => !draft.categoryRemoved.includes(c.id));
  const savedRows = categories.filter((c) => !c.isNew);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!label.trim()) return;
    if (live.some((c) => same(c.label, label))) {
      setError(`There's already a category called “${label.trim()}”`);
      return;
    }
    setDraft((d) => ({
      ...d,
      newCategories: [...d.newCategories, { tempId: tempId(), label: label.trim(), icon: icon.trim() }],
    }));
    setLabel("");
    setIcon("");
    setError(null);
  };

  const edit = (c: CategoryView, patch: CategoryEdit) =>
    setDraft((d) => {
      if (c.isNew) {
        return { ...d, newCategories: d.newCategories.map((n) => (n.tempId === c.id ? { ...n, ...patch } : n)) };
      }
      const merged = diff(saved.find((s) => s.id === c.id)!, { ...d.categoryEdits[c.id], ...patch });
      const { [c.id]: _, ...rest } = d.categoryEdits;
      return { ...d, categoryEdits: Object.keys(merged).length ? { ...rest, [c.id]: merged } : rest };
    });
  // Dropping a new category puts anything already filed under it back to "auto".
  const dropNew = (d: Draft, c: CategoryView): Draft => ({
    ...d,
    newCategories: d.newCategories.filter((n) => n.tempId !== c.id),
    newPresets: d.newPresets.map((p) => (p.category_key === c.key ? { ...p, category_key: AUTO } : p)),
    presetEdits: Object.fromEntries(
      Object.entries(d.presetEdits)
        .map(([id, e]): [string, PresetEdit] => {
          if (e.category_key !== c.key) return [id, e];
          const { category_key: _, ...rest } = e;
          return [id, rest];
        })
        .filter(([, e]) => Object.keys(e).length > 0),
    ),
  });
  const remove = (c: CategoryView) =>
    setDraft((d) => (c.isNew ? dropNew(d, c) : { ...d, categoryRemoved: [...d.categoryRemoved, c.id] }));
  const undo = (c: CategoryView) =>
    setDraft(({ categoryEdits: { [c.id]: _, ...rest }, ...d }) =>
      c.isNew
        ? dropNew({ ...d, categoryEdits: rest }, c)
        : { ...d, categoryEdits: rest, categoryRemoved: d.categoryRemoved.filter((x) => x !== c.id) },
    );
  const move = (index: number, step: -1 | 1) => {
    const ids = savedRows.map((c) => c.id);
    [ids[index], ids[index + step]] = [ids[index + step], ids[index]];
    setDraft((d) => ({ ...d, categoryOrder: ids }));
  };

  return (
    <Card>
      <h2 className="mb-1 font-semibold">Categories</h2>
      <p className="mb-4 text-sm text-slate-500">
        The sections of the shopping list, in this order. Deleting one moves its items to “Other”.
      </p>
      <form onSubmit={submit} className="mb-4 flex flex-wrap gap-2">
        <input className={`${fieldClass} w-20 text-center`} placeholder="🍿" maxLength={16} value={icon} onChange={(e) => setIcon(e.target.value)} aria-label="Icon" />
        <input
          className={`${fieldClass} min-w-40 flex-1`}
          placeholder="e.g. Snacks"
          maxLength={40}
          value={label}
          onChange={(e) => (setLabel(e.target.value), setError(null))}
        />
        <Button type="submit" disabled={!label.trim() || disabled}>
          + Add category
        </Button>
      </form>
      {error && <p className="mb-3 text-sm text-red-600">{error}</p>}
      <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-100">
        {categories.map((c) => {
          const state = c.isNew
            ? "new"
            : draft.categoryRemoved.includes(c.id)
              ? "removed"
              : draft.categoryEdits[c.id]
                ? "edited"
                : null;
          const removed = state === "removed";
          const index = savedRows.indexOf(c);
          return (
            <li key={c.id} className={`flex flex-wrap items-center gap-2 px-3 py-2 ${rowTint(state)}`}>
              <input
                className={`${fieldClass} w-16 text-center`}
                value={c.icon}
                maxLength={16}
                disabled={removed || disabled}
                onChange={(e) => edit(c, { icon: e.target.value })}
                aria-label="Icon"
              />
              <input
                className={`${fieldClass} min-w-32 flex-1 ${removed ? "text-slate-400 line-through" : ""}`}
                value={c.label}
                maxLength={40}
                disabled={removed || disabled}
                onChange={(e) => edit(c, { label: e.target.value })}
                aria-label="Name"
              />
              {!c.can_delete && <Badge>Fallback</Badge>}
              <RowState state={state} onUndo={() => undo(c)} />
              <Button variant="ghost" disabled={removed || disabled || c.isNew || index <= 0} onClick={() => move(index, -1)} aria-label={`Move ${c.label} up`}>
                ↑
              </Button>
              <Button
                variant="ghost"
                disabled={removed || disabled || c.isNew || index >= savedRows.length - 1}
                onClick={() => move(index, 1)}
                aria-label={`Move ${c.label} down`}
              >
                ↓
              </Button>
              {c.can_delete && !removed && state !== "new" && (
                <Button variant="ghost" disabled={disabled} onClick={() => remove(c)} aria-label={`Delete ${c.label}`} title="Delete (its items move to Other)">
                  ✕
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
