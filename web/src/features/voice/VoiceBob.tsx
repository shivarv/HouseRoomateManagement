import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { voiceApi } from "../../api/voice";
import { Button, ErrorText } from "../../components/ui";
import type { VoiceAction, VoiceInterpretation, VoiceProposal, VoiceResult } from "../../types/api";

// The browser's own speech recognition (Chrome, Edge, Safari). Firefox has none: typing instead.
interface Recognition {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
}
declare global {
  interface Window {
    SpeechRecognition?: new () => Recognition;
    webkitSpeechRecognition?: new () => Recognition;
  }
}
const Speech = typeof window !== "undefined" ? (window.SpeechRecognition ?? window.webkitSpeechRecognition) : undefined;

const AREA_ICON: Record<VoiceProposal["area"], string> = {
  chores: "✅",
  bills: "🧾",
  groceries: "🛒",
  chat: "💬",
  favours: "🙋",
};

type Step = "listening" | "typing" | "thinking" | "review";

/**
 * The mic button on every tab (not admin settings): say what happened ("Raj took out the trash,
 * I bought milk"), check the cards, Confirm. Nothing changes before Confirm; Undo after.
 * Mirrors iOS VoiceBob.
 */
export function VoiceBob({ householdId, tab }: { householdId: string; tab: string }) {
  const config = useQuery({ queryKey: ["voice-config"], queryFn: voiceApi.config, staleTime: 60 * 60_000 });
  const [open, setOpen] = useState(false);
  const [toast, setToast] = useState<{ text: string; undo: VoiceAction[] } | null>(null);
  if (!config.data?.enabled) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Voice command: say what you did"
        title="Say what you did"
        className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-linear-to-br from-indigo-600 via-violet-600 to-fuchsia-600 text-2xl text-white shadow-lg shadow-fuchsia-500/30 transition hover:-translate-y-0.5 hover:brightness-110"
      >
        🎤
      </button>
      {open && (
        <VoiceSheet
          householdId={householdId}
          tab={tab}
          onClose={() => setOpen(false)}
          onDone={(text, undo) => {
            setOpen(false);
            setToast({ text, undo });
          }}
        />
      )}
      {toast && <UndoToast householdId={householdId} {...toast} onClose={() => setToast(null)} />}
    </>
  );
}

function VoiceSheet({
  householdId,
  tab,
  onClose,
  onDone,
}: {
  householdId: string;
  tab: string;
  onClose: () => void;
  onDone: (text: string, undo: VoiceAction[]) => void;
}) {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<Step>(Speech ? "listening" : "typing");
  const [text, setText] = useState("");
  const [micError, setMicError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<VoiceInterpretation | null>(null);
  const [picked, setPicked] = useState<boolean[]>([]);
  // After a Confirm where something couldn't be done: what was sent, and each one's result.
  const [checked, setChecked] = useState<{ sent: VoiceProposal[]; results: VoiceResult[] } | null>(null);
  const recognition = useRef<Recognition | null>(null);

  const interpret = useMutation({
    mutationFn: (args: { said: string; followUp?: { question: string; answer: string } }) =>
      voiceApi.interpret(householdId, args.said, tab, args.followUp),
    onMutate: () => setStep("thinking"),
    onSuccess: (res) => {
      setAnswer(res);
      setPicked(res.proposals.map(() => true));
      setChecked(null);
      setStep("review");
    },
    onError: () => setStep("review"),
  });

  const run = useMutation({
    mutationFn: (sent: VoiceProposal[]) => voiceApi.execute(householdId, sent.map((p) => p.action)),
    onSuccess: (res, sent) => {
      if (res.some((r) => r.error)) {
        // Nothing ran: show which one can't be done, and offer the rest.
        setChecked({ sent, results: res });
        return;
      }
      queryClient.invalidateQueries();
      const failed = res.filter((r) => !r.ok);
      const done = res.filter((r) => r.ok);
      onDone(
        failed.length ? `Done ${done.length} of ${sent.length}. ${failed[0].error ?? ""}` : done.length === 1 ? `Done: ${done[0].summary}` : `Done: ${done.length} things`,
        done.flatMap((r) => r.undo),
      );
    },
  });

  // Listen while the sheet is on "listening"; stop after a pause, then work out what was said.
  useEffect(() => {
    if (step !== "listening" || !Speech) return;
    const rec = new Speech();
    rec.lang = navigator.language || "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    let heard = "";
    let cancelled = false;
    rec.onresult = (e) => {
      heard = Array.from(e.results, (r) => r[0].transcript).join(" ");
      setText(heard);
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") {
        setMicError("Microphone access is off. Allow it in the browser, or type instead.");
        setStep("typing");
      } else if (e.error === "no-speech") {
        setMicError("Didn't hear anything. Tap the mic to try again, or type.");
      }
    };
    rec.onend = () => {
      recognition.current = null;
      if (cancelled) return;
      if (heard.trim()) interpret.mutate({ said: heard.trim() });
      else setStep((s) => (s === "listening" ? "typing" : s));
    };
    recognition.current = rec;
    setMicError(null);
    setText("");
    rec.start();
    return () => {
      cancelled = true;
      rec.abort();
    };
  }, [step]); // one recognition each time the sheet starts listening

  const close = () => {
    recognition.current?.abort();
    onClose();
  };

  const submitTyped = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim()) interpret.mutate({ said: text.trim() });
  };

  const chosen = answer?.proposals.filter((_, i) => picked[i]) ?? [];
  const errorFor = (p: VoiceProposal) => (checked ? checked.results[checked.sent.indexOf(p)]?.error : null);
  const ready = checked ? checked.sent.filter((_, i) => !checked.results[i].error) : [];

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/30 p-4 sm:items-center" onClick={close}>
      <div
        role="dialog"
        aria-label="Voice command"
        className="w-full max-w-md space-y-4 rounded-3xl bg-white p-5 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-slate-900">
            {step === "listening" ? "🎙 Listening…" : step === "thinking" ? "Working it out…" : "Say what you did"}
          </h2>
          <button type="button" onClick={close} className="text-slate-400 hover:text-slate-700" aria-label="Close">
            ✕
          </button>
        </div>

        {step === "listening" && (
          <>
            <p className="min-h-12 rounded-2xl bg-indigo-50 p-3 text-slate-800">
              {text || <span className="text-slate-400">e.g. “Raj took out the trash and I bought milk”</span>}
            </p>
            <div className="flex gap-2">
              <Button className="flex-1" onClick={() => recognition.current?.stop()}>
                Done
              </Button>
              <Button variant="ghost" onClick={() => setStep("typing")} title="Type instead">
                ⌨︎ Type
              </Button>
            </div>
          </>
        )}

        {step === "typing" && (
          <form onSubmit={submitTyped} className="space-y-2">
            <textarea
              autoFocus
              value={text}
              maxLength={500}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && submitTyped(e)}
              placeholder="e.g. I paid the gas bill, it was 42.50"
              className="h-20 w-full resize-none rounded-2xl border border-slate-200 p-3 text-sm focus:border-indigo-400 focus:outline-none"
            />
            {micError && <p className="text-xs text-amber-700">{micError}</p>}
            <div className="flex gap-2">
              <Button type="submit" className="flex-1" disabled={!text.trim()}>
                Go
              </Button>
              {Speech && (
                <Button type="button" variant="ghost" onClick={() => setStep("listening")}>
                  🎤 Speak
                </Button>
              )}
            </div>
          </form>
        )}

        {step === "thinking" && (
          <p className="flex items-center gap-2 text-sm text-slate-500">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-300 border-t-indigo-600" /> “{text}”
          </p>
        )}

        {step === "review" && (
          <div className="space-y-3">
            {text && <p className="text-sm text-slate-500">“{text}”</p>}
            <ErrorText error={interpret.error} />
            {answer?.notes.map((n) => (
              <p key={n} className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
                {n}
              </p>
            ))}
            {answer?.question && (
              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-800">{answer.question}</p>
                <div className="flex flex-wrap gap-2">
                  {answer.options.map((o) => (
                    <Button
                      key={o}
                      variant="secondary"
                      onClick={() => interpret.mutate({ said: text, followUp: { question: answer.question!, answer: o } })}
                    >
                      {o}
                    </Button>
                  ))}
                </div>
              </div>
            )}
            {!!answer?.proposals.length && (
              <ul className="space-y-2">
                {answer.proposals.map((p, i) => {
                  const error = errorFor(p);
                  return (
                    <li key={i}>
                      <label
                        className={`flex cursor-pointer items-start gap-3 rounded-2xl border p-3 ${error ? "border-red-200 bg-red-50" : "border-slate-200"}`}
                      >
                        <input
                          type="checkbox"
                          checked={picked[i] ?? false}
                          onChange={(e) => setPicked((all) => all.map((v, j) => (j === i ? e.target.checked : v)))}
                          className="mt-1 accent-indigo-600"
                        />
                        <span className="text-sm text-slate-800">
                          {AREA_ICON[p.area]} {p.summary}
                          {error && <span className="mt-1 block text-xs text-red-700">{error}</span>}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
            <ErrorText error={run.error} />
            <div className="flex gap-2">
              {!!answer?.proposals.length && (
                <Button
                  className="flex-1"
                  disabled={run.isPending || (checked ? ready.length === 0 : chosen.length === 0)}
                  onClick={() => run.mutate(checked ? ready : chosen)}
                >
                  {run.isPending ? "Doing it…" : checked ? `Do the other ${ready.length}` : chosen.length > 1 ? `Confirm all ${chosen.length}` : "Confirm"}
                </Button>
              )}
              <Button variant="ghost" onClick={() => setStep(Speech ? "listening" : "typing")}>
                {Speech ? "🎤 Again" : "Try again"}
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/** "Done · Undo" for a few seconds after voice did something. */
function UndoToast({ householdId, text, undo, onClose }: { householdId: string; text: string; undo: VoiceAction[]; onClose: () => void }) {
  const queryClient = useQueryClient();
  const revert = useMutation({
    mutationFn: () => voiceApi.execute(householdId, undo),
    onSuccess: () => {
      queryClient.invalidateQueries();
      onClose();
    },
  });
  useEffect(() => {
    if (revert.isPending) return;
    const timer = setTimeout(onClose, 8000);
    return () => clearTimeout(timer);
  }, [onClose, revert.isPending]);

  return (
    <div className="fixed bottom-24 right-6 z-40 flex max-w-sm items-center gap-3 rounded-2xl bg-slate-900 px-4 py-3 text-sm text-white shadow-xl">
      <span className="flex-1">{revert.error ? (revert.error as Error).message : text}</span>
      {undo.length > 0 && !revert.error && (
        <button type="button" onClick={() => revert.mutate()} disabled={revert.isPending} className="font-semibold text-fuchsia-300 hover:text-fuchsia-200">
          {revert.isPending ? "Undoing…" : "Undo"}
        </button>
      )}
    </div>
  );
}
