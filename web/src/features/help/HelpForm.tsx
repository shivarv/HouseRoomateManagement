import { useState, type FormEvent } from "react";
import { Button, ErrorText } from "../../components/ui";
import type { Household, HelpRequest } from "../../types/api";
import { useCreateHelp, useUpdateHelp } from "./hooks";
import { HELP_PRESETS } from "./presets";

const CUSTOM = "custom";

const fieldClass =
  "w-full rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-sm shadow-sm outline-none transition placeholder:text-slate-400 hover:border-indigo-300 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15";

/** Ask a favour (new), or edit my own open one (`editing`). */
export function HelpForm({
  households,
  editing,
  onDone,
}: {
  households: Household[];
  editing?: HelpRequest;
  onDone: () => void;
}) {
  const create = useCreateHelp();
  const update = useUpdateHelp();
  const preset = editing && HELP_PRESETS.some((p) => p.title === editing.title) ? editing.title : editing ? CUSTOM : "";
  const [choice, setChoice] = useState<string>(preset);
  const [custom, setCustom] = useState(preset === CUSTOM ? (editing?.title ?? "") : "");
  const [details, setDetails] = useState(editing?.details ?? "");
  const [householdId, setHouseholdId] = useState(editing?.household_id ?? households[0]?.id ?? "");

  const title = choice === CUSTOM ? custom.trim() : choice;
  const pending = create.isPending || update.isPending;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!title) return;
    if (editing) {
      update.mutate({ id: editing.id, title, details: details.trim() }, { onSuccess: onDone });
    } else {
      create.mutate({ householdId, title, details: details.trim() }, { onSuccess: onDone });
    }
  };

  const chip = (value: string, label: string) => (
    <button
      key={value}
      type="button"
      onClick={() => setChoice(value)}
      className={`rounded-xl border px-3 py-1.5 text-sm transition ${
        choice === value
          ? "border-transparent bg-linear-to-r from-indigo-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30"
          : "border-slate-200 bg-white hover:border-indigo-300 hover:text-indigo-700"
      }`}
    >
      {label}
    </button>
  );

  return (
    <form onSubmit={onSubmit} className="space-y-4 rounded-2xl border border-indigo-100 bg-white/90 p-5 shadow-sm ring-1 ring-indigo-50">
      <h2 className="font-semibold">{editing ? "Edit your favour" : "Ask a favour"}</h2>

      {!editing && households.length > 1 && (
        <label className="block space-y-1 text-sm">
          <span className="font-medium text-slate-700">Which house?</span>
          <select className={fieldClass} value={householdId} onChange={(e) => setHouseholdId(e.target.value)}>
            {households.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name}
              </option>
            ))}
          </select>
        </label>
      )}

      <div className="space-y-2">
        <p className="text-sm font-medium text-slate-700">What do you need?</p>
        <div className="flex flex-wrap gap-2">
          {HELP_PRESETS.map((p) => chip(p.title, `${p.icon} ${p.title}`))}
          {chip(CUSTOM, "✏️ Something else…")}
        </div>
        {choice === CUSTOM && (
          <input
            className={fieldClass}
            placeholder="Say what you need help with"
            maxLength={120}
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            autoFocus
          />
        )}
      </div>

      <label className="block space-y-1 text-sm">
        <span className="font-medium text-slate-700">Details (optional)</span>
        <textarea
          className={`${fieldClass} min-h-20`}
          placeholder="e.g. milk, eggs and bread · it's at the front desk"
          maxLength={500}
          value={details}
          onChange={(e) => setDetails(e.target.value)}
        />
      </label>

      <ErrorText error={create.error ?? update.error} />
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={!title || !householdId || pending}>
          {pending ? "Saving…" : editing ? "Save changes" : "Post to the house"}
        </Button>
      </div>
    </form>
  );
}
