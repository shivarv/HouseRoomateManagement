import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { chatApi } from "../../api/chat";
import { ErrorText, Loading } from "../../components/ui";
import { avatarColor } from "../../lib/avatar";
import { formatDay, formatTime, localIsoDate, relativeDay } from "../../lib/format";
import type { ChatMessage } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

const POLL_MS = 4000;
/** Compare times as times: as text, "…:00Z" would sort after "…:00.5Z". */
const time = (iso: string) => Date.parse(iso);
/** Phones and tablets: Enter makes a new line and the send button sends. */
const touchScreen = () => typeof window !== "undefined" && window.matchMedia("(pointer: coarse)").matches;

/**
 * Height that fills the screen from where `ref` starts down to the bottom (minus `gap`), so the
 * typing box is always in view without scrolling. Follows resizes and the phone keyboard.
 */
function useFillScreen(ref: React.RefObject<HTMLElement | null>, gap = 16) {
  const [height, setHeight] = useState<number | null>(null);
  useLayoutEffect(() => {
    const fit = () => {
      const el = ref.current;
      if (!el) return;
      const top = el.getBoundingClientRect().top + window.scrollY;
      const screen = window.visualViewport?.height ?? window.innerHeight;
      setHeight(Math.max(320, Math.floor(screen - top - gap)));
    };
    window.scrollTo({ top: 0 });
    fit();
    window.addEventListener("resize", fit);
    window.visualViewport?.addEventListener("resize", fit);
    return () => {
      window.removeEventListener("resize", fit);
      window.visualViewport?.removeEventListener("resize", fit);
    };
  }, [ref, gap]);
  return height;
}

function dayLabel(iso: string): string {
  const day = localIsoDate(new Date(iso));
  const relative = relativeDay(day, localIsoDate());
  return relative === formatDay(day) ? formatDay(day, { weekday: "long", month: "short", day: "numeric" }) : relative;
}

/** 💬 Chat: the house's group chat. New messages arrive every few seconds while it's open. */
export function ChatTab() {
  const house = useCurrentHousehold();
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [selected, setSelected] = useState<string | null>(null); // the message whose actions are open (tap on phones)
  const [unseen, setUnseen] = useState(0); // new messages while I'm scrolled up
  const since = useRef<string | null>(null); // the latest change we've seen
  const list = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true); // follow new messages unless I've scrolled up to read
  const frame = useRef<HTMLDivElement>(null);
  const height = useFillScreen(frame, 40); // the page keeps 2rem padding below

  const markRead = useCallback(() => {
    chatApi.markRead(house.id).then(() => queryClient.invalidateQueries({ queryKey: ["chat-unread", house.id] }), () => {});
  }, [house.id, queryClient]);

  /** Add new messages and replace edited or deleted ones, keeping oldest first. */
  const merge = useCallback((incoming: ChatMessage[]) => {
    if (!incoming.length) return;
    setMessages((current) => {
      const byId = new Map((current ?? []).map((m) => [m.id, m]));
      const fresh = incoming.filter((m) => !byId.has(m.id)).length;
      if (fresh && !stickToBottom.current) setUnseen((n) => n + fresh);
      for (const m of incoming) byId.set(m.id, m);
      return [...byId.values()].sort((a, b) => time(a.created_at) - time(b.created_at));
    });
    // Poll for anything newer than the latest change seen (new, edited or deleted).
    for (const m of incoming) if (!since.current || time(m.changed_at) > time(since.current)) since.current = m.changed_at;
  }, []);

  // First page, then poll for what's new while the page is visible.
  useEffect(() => {
    let stopped = false;
    setMessages(null);
    since.current = null;
    stickToBottom.current = true;
    chatApi.page(house.id).then(
      (page) => {
        if (stopped) return;
        setMessages([]);
        merge(page.messages);
        setHasMore(page.has_more);
        markRead();
      },
      (e) => setError(e),
    );
    const timer = setInterval(async () => {
      if (stopped || document.hidden) return;
      try {
        const page = await chatApi.page(house.id, since.current ? { after: since.current } : {});
        if (page.messages.length) {
          merge(page.messages);
          markRead();
        }
        setError(null);
      } catch (e) {
        setError(e);
      }
    }, POLL_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
  }, [house.id, merge, markRead]);

  // Keep the newest message in view when it arrives (unless I scrolled up).
  useLayoutEffect(() => {
    const el = list.current;
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const toBottom = () => {
    const el = list.current;
    stickToBottom.current = true;
    setUnseen(0);
    el?.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  };

  const loadOlder = async () => {
    if (!messages?.length) return;
    const el = list.current;
    const fromBottom = el ? el.scrollHeight - el.scrollTop : 0;
    setLoadingOlder(true);
    try {
      const page = await chatApi.page(house.id, { before: messages[0].created_at });
      stickToBottom.current = false;
      setMessages((current) => [...page.messages, ...(current ?? [])]);
      setHasMore(page.has_more);
      // Stay where I was reading.
      requestAnimationFrame(() => el && (el.scrollTop = el.scrollHeight - fromBottom));
    } catch (e) {
      setError(e);
    } finally {
      setLoadingOlder(false);
    }
  };

  const onScroll = () => {
    const el = list.current;
    if (!el) return;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    if (stickToBottom.current) setUnseen(0);
  };

  return (
    // Exactly fills the screen below the header, so the typing box is always visible.
    <div
      ref={frame}
      style={{ height: height ?? undefined }}
      className="relative flex h-[calc(100dvh-9rem)] flex-col overflow-hidden rounded-2xl border border-white/70 bg-white/85 shadow-sm ring-1 ring-slate-900/5 backdrop-blur"
    >
      {/* The house at a glance: who's in this chat. */}
      <div className="relative overflow-hidden bg-linear-to-r from-indigo-600 via-violet-600 to-fuchsia-600 px-4 py-3.5 text-white sm:px-5">
        <div className="pointer-events-none absolute -right-8 -top-10 h-28 w-28 rounded-full bg-white/20 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-12 left-1/3 h-24 w-24 rounded-full bg-sky-300/30 blur-2xl" />
        <div className="relative flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white/20 text-xl ring-1 ring-white/30 backdrop-blur">💬</span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-base font-extrabold tracking-tight sm:text-lg">{house.name} chat</p>
            <p className="flex items-center gap-1.5 truncate text-xs text-white/80">
              👥 {house.members.length} {house.members.length === 1 ? "roommate" : "roommates"} · messages stay in your house
            </p>
          </div>
          <div className="hidden -space-x-2 sm:flex">
            {house.members.slice(0, 5).map((m) => (
              <span
                key={m.id}
                title={m.display_name}
                className={`flex h-8 w-8 items-center justify-center rounded-full bg-linear-to-br text-xs font-bold text-white shadow-sm ring-2 ring-white/70 ${avatarColor(m.display_name)}`}
              >
                {m.display_name.slice(0, 1).toUpperCase()}
              </span>
            ))}
            {house.members.length > 5 && (
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/25 text-[11px] font-bold ring-2 ring-white/70 backdrop-blur">
                +{house.members.length - 5}
              </span>
            )}
          </div>
        </div>
      </div>

      <div ref={list} onScroll={onScroll} onClick={() => setSelected(null)} className="flex-1 overflow-y-auto overscroll-contain px-3 py-4 sm:px-5">
        {messages === null ? (
          error ? <ErrorText error={error} /> : <Loading />
        ) : (
          <>
            {hasMore && (
              <div className="pb-3 text-center">
                <button
                  className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-200 disabled:opacity-50"
                  disabled={loadingOlder}
                  onClick={(e) => (e.stopPropagation(), loadOlder())}
                >
                  {loadingOlder ? "Loading…" : "Load earlier messages"}
                </button>
              </div>
            )}
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                <span className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-linear-to-br from-indigo-500 to-fuchsia-500 text-2xl text-white shadow-lg shadow-indigo-500/30">
                  💬
                </span>
                <p className="font-semibold">Say hi to your house</p>
                <p className="mt-1 text-sm text-slate-500">Everyone in {house.name} sees these messages.</p>
              </div>
            )}
            {messages.map((m, i) => {
              const prev = messages[i - 1];
              const next = messages[i + 1];
              const day = localIsoDate(new Date(m.created_at));
              const newDay = !prev || localIsoDate(new Date(prev.created_at)) !== day;
              const firstOfGroup = newDay || prev.author?.id !== m.author?.id;
              const lastOfGroup = !next || next.author?.id !== m.author?.id || localIsoDate(new Date(next.created_at)) !== day;
              return (
                <div key={m.id}>
                  {newDay && (
                    <div className="my-4 flex justify-center">
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold text-slate-500">{dayLabel(m.created_at)}</span>
                    </div>
                  )}
                  <Bubble
                    message={m}
                    firstOfGroup={firstOfGroup}
                    lastOfGroup={lastOfGroup}
                    selected={selected === m.id}
                    onSelect={() => setSelected((s) => (s === m.id ? null : m.id))}
                    onChanged={(updated) => (merge([updated]), setSelected(null))}
                  />
                </div>
              );
            })}
          </>
        )}
      </div>

      {unseen > 0 && (
        <button
          onClick={toBottom}
          className="absolute bottom-20 left-1/2 -translate-x-1/2 rounded-full bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:bg-indigo-700"
        >
          ↓ {unseen} new {unseen === 1 ? "message" : "messages"}
        </button>
      )}
      {messages !== null && error ? (
        <div className="px-3">
          <ErrorText error={error} />
        </div>
      ) : null}
      <Composer householdId={house.id} onSent={(m) => ((stickToBottom.current = true), setUnseen(0), merge([m]))} />
    </div>
  );
}

function Avatar({ name, small = false }: { name: string; small?: boolean }) {
  return (
    <span
      className={`flex shrink-0 items-center justify-center rounded-full bg-linear-to-br ${avatarColor(name)} font-semibold text-white shadow-sm ring-2 ring-white ${
        small ? "h-7 w-7 text-[11px]" : "h-8 w-8 text-xs"
      }`}
    >
      {name.slice(0, 1).toUpperCase()}
    </span>
  );
}

/**
 * One message. Others' show their avatar and name at the start of a run. Tap (or hover on a
 * computer) to see what I can do with it: copy, and edit or delete my own (admins can delete any).
 */
function Bubble({
  message: m,
  firstOfGroup,
  lastOfGroup,
  selected,
  onSelect,
  onChanged,
}: {
  message: ChatMessage;
  firstOfGroup: boolean;
  lastOfGroup: boolean;
  selected: boolean;
  onSelect: () => void;
  onChanged: (m: ChatMessage) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(m.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);

  const run = async (action: () => Promise<ChatMessage>) => {
    setBusy(true);
    try {
      onChanged(await action());
      setEditing(false);
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };
  const copy = async () => {
    await navigator.clipboard?.writeText(m.body);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };
  const actions = !m.deleted && !editing;
  const author = m.author?.display_name ?? "Someone who left";

  return (
    <div className={`group flex items-end gap-2 ${m.is_mine ? "flex-row-reverse" : ""} ${firstOfGroup ? "mt-3" : "mt-0.5"}`}>
      {!m.is_mine && <div className="w-8 shrink-0">{lastOfGroup && <Avatar name={author} />}</div>}
      <div className={`flex min-w-0 max-w-[85%] flex-col sm:max-w-[70%] ${m.is_mine ? "items-end" : "items-start"}`}>
        {firstOfGroup && !m.is_mine && <span className="mb-0.5 px-1 text-xs font-semibold text-slate-500">{author}</span>}
        <div
          role={actions ? "button" : undefined}
          tabIndex={actions ? 0 : undefined}
          onClick={(e) => {
            e.stopPropagation();
            if (actions) onSelect();
          }}
          className={`whitespace-pre-wrap break-words px-3.5 py-2 text-[15px] leading-snug shadow-sm transition sm:text-sm ${
            m.deleted
              ? "rounded-2xl bg-slate-100 italic text-slate-400"
              : m.is_mine
                ? `rounded-2xl bg-linear-to-br from-indigo-500 to-fuchsia-500 text-white ${lastOfGroup ? "rounded-br-md" : ""}`
                : `rounded-2xl bg-white text-slate-800 ring-1 ring-slate-200 ${lastOfGroup ? "rounded-bl-md" : ""}`
          } ${selected ? "ring-2 ring-indigo-300" : ""} ${actions ? "cursor-pointer" : ""}`}
        >
          {editing ? (
            <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
              <textarea
                className="block w-[min(18rem,70vw)] rounded-lg bg-white/95 p-2 text-sm text-slate-800 outline-none"
                rows={3}
                maxLength={2000}
                value={text}
                onChange={(e) => setText(e.target.value)}
                autoFocus
              />
              <div className="flex justify-end gap-2">
                <button className="rounded px-2 py-0.5 text-xs text-white/85 hover:text-white" onClick={() => setEditing(false)}>
                  Cancel
                </button>
                <button
                  className="rounded bg-white/95 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 disabled:opacity-50"
                  disabled={busy || !text.trim()}
                  onClick={() => run(() => chatApi.edit(m.id, text))}
                >
                  Save
                </button>
              </div>
            </div>
          ) : m.deleted ? (
            "Message deleted"
          ) : (
            m.body
          )}
        </div>
        {(lastOfGroup || selected) && (
          <span className="mt-0.5 px-1 text-[10px] text-slate-400">
            {formatTime(m.created_at)}
            {m.edited_at && !m.deleted && " · edited"}
          </span>
        )}
        {/* Actions: shown when tapped (phones) or hovered (computers). */}
        {actions && (
          <div className={`mt-1 gap-1 ${selected ? "flex" : "hidden sm:group-hover:flex"}`} onClick={(e) => e.stopPropagation()}>
            <ActionButton onClick={copy}>{copied ? "✓ Copied" : "Copy"}</ActionButton>
            {m.can_edit && <ActionButton onClick={() => (setText(m.body), setEditing(true))}>Edit</ActionButton>}
            {m.can_delete && (
              <ActionButton
                danger
                disabled={busy}
                onClick={() => confirm(m.is_mine ? "Delete this message for everyone?" : "Delete this message? (admin)") && run(() => chatApi.remove(m.id))}
              >
                Delete
              </ActionButton>
            )}
          </div>
        )}
        <ErrorText error={error} />
      </div>
    </div>
  );
}

function ActionButton({ children, danger = false, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { danger?: boolean }) {
  return (
    <button
      className={`rounded-full bg-white px-2.5 py-1 text-xs font-medium shadow-sm ring-1 transition disabled:opacity-50 ${
        danger ? "text-red-600 ring-red-200 hover:bg-red-50" : "text-slate-600 ring-slate-200 hover:bg-slate-50"
      }`}
      {...props}
    >
      {children}
    </button>
  );
}

/** Enter sends on a computer (Shift+Enter: new line); on phones Enter is a new line and the button sends. */
function Composer({ householdId, onSent }: { householdId: string; onSent: (m: ChatMessage) => void }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  // Grow with the message, up to about five lines.
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
  }, [text]);

  const send = async () => {
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    try {
      onSent(await chatApi.send(householdId, body));
      setText("");
      setError(null);
      box.current?.focus();
    } catch (e) {
      setError(e);
    } finally {
      setSending(false);
    }
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && !touchScreen()) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="border-t border-slate-100 bg-white/90 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3">
      <ErrorText error={error} />
      <div className="flex items-end gap-2">
        <textarea
          ref={box}
          className="max-h-32 min-h-11 flex-1 resize-none rounded-2xl border border-slate-200 bg-white px-4 py-2.5 text-[16px] leading-snug outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15 sm:text-sm"
          rows={1}
          placeholder="Message your house…"
          maxLength={2000}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          aria-label="Message"
        />
        <button
          onClick={send}
          disabled={!text.trim() || sending}
          aria-label="Send"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-linear-to-br from-indigo-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30 transition hover:brightness-110 active:scale-95 disabled:opacity-40"
        >
          {sending ? (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          ) : (
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
              <path d="M3.4 20.4 21 12 3.4 3.6 3.4 10l12 2-12 2z" />
            </svg>
          )}
        </button>
      </div>
      <p className="mt-1 hidden px-1 text-[11px] text-slate-400 sm:block">Enter to send · Shift+Enter for a new line</p>
    </div>
  );
}
