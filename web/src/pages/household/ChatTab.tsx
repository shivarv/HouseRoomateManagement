import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { chatApi } from "../../api/chat";
import { Button, ErrorText, Loading } from "../../components/ui";
import { formatDay, formatTime, localIsoDate, relativeDay } from "../../lib/format";
import type { ChatMessage } from "../../types/api";
import { useCurrentHousehold } from "./HouseholdLayout";

const POLL_MS = 4000;
/** Compare times as times: as text, "…:00Z" would sort after "…:00.5Z". */
const time = (iso: string) => Date.parse(iso);


/** 💬 Chat: the house's group chat. New messages arrive every few seconds while it's open. */
export function ChatTab() {
  const house = useCurrentHousehold();
  const queryClient = useQueryClient();
  const [messages, setMessages] = useState<ChatMessage[] | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const since = useRef<string | null>(null); // the latest change we've seen
  const list = useRef<HTMLDivElement>(null);
  const stickToBottom = useRef(true); // follow new messages unless I've scrolled up to read

  const markRead = useCallback(() => {
    chatApi.markRead(house.id).then(() => queryClient.invalidateQueries({ queryKey: ["chat-unread", house.id] }), () => {});
  }, [house.id, queryClient]);

  /** Add new messages and replace edited or deleted ones, keeping oldest first. */
  const merge = useCallback((incoming: ChatMessage[]) => {
    if (!incoming.length) return;
    setMessages((current) => {
      const byId = new Map((current ?? []).map((m) => [m.id, m]));
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
    if (el) stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
  };

  if (messages === null) return error ? <ErrorText error={error} /> : <Loading />;

  return (
    <div className="flex h-[70vh] min-h-96 flex-col overflow-hidden rounded-2xl border border-white/70 bg-white/80 shadow-sm ring-1 ring-slate-900/5">
      <div ref={list} onScroll={onScroll} className="flex-1 space-y-1 overflow-y-auto px-4 py-4">
        {hasMore && (
          <div className="pb-2 text-center">
            <Button variant="ghost" disabled={loadingOlder} onClick={loadOlder}>
              {loadingOlder ? "Loading…" : "Load earlier messages"}
            </Button>
          </div>
        )}
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-sm text-slate-500">
            <span className="mb-2 text-4xl">💬</span>
            Say hi to your house! Everyone in {house.name} sees these messages.
          </div>
        )}
        {messages.map((m, i) => {
          const prev = messages[i - 1];
          const day = localIsoDate(new Date(m.created_at));
          const newDay = !prev || localIsoDate(new Date(prev.created_at)) !== day;
          const sameAuthor = !newDay && prev && prev.author?.id === m.author?.id;
          return (
            <div key={m.id}>
              {newDay && (
                <div className="my-3 text-center text-xs font-semibold text-slate-400">
                  {relativeDay(day, localIsoDate()) === formatDay(day) ? formatDay(day, { weekday: "long", month: "short", day: "numeric" }) : relativeDay(day, localIsoDate())}
                </div>
              )}
              <Bubble message={m} showAuthor={!sameAuthor && !m.is_mine} onChanged={(updated) => merge([updated])} />
            </div>
          );
        })}
      </div>
      <ErrorText error={error} />
      <Composer householdId={house.id} onSent={(m) => ((stickToBottom.current = true), merge([m]))} />
    </div>
  );
}

function Bubble({ message: m, showAuthor, onChanged }: { message: ChatMessage; showAuthor: boolean; onChanged: (m: ChatMessage) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(m.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

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

  return (
    <div className={`group flex flex-col ${m.is_mine ? "items-end" : "items-start"} ${showAuthor ? "mt-3" : ""}`}>
      {showAuthor && <span className="mb-0.5 px-1 text-xs font-semibold text-slate-500">{m.author?.display_name ?? "Someone who left"}</span>}
      <div className="flex max-w-[80%] items-end gap-1.5">
        {m.is_mine && !m.deleted && !editing && (
          <span className="hidden gap-0.5 group-hover:flex">
            {m.can_edit && (
              <button className="rounded px-1 text-xs text-slate-400 hover:text-indigo-600" onClick={() => (setText(m.body), setEditing(true))} aria-label="Edit">
                ✏️
              </button>
            )}
            {m.can_delete && (
              <button className="rounded px-1 text-xs text-slate-400 hover:text-red-600" disabled={busy} onClick={() => confirm("Delete this message?") && run(() => chatApi.remove(m.id))} aria-label="Delete">
                🗑
              </button>
            )}
          </span>
        )}
        <div
          className={`whitespace-pre-wrap break-words rounded-2xl px-3.5 py-2 text-sm shadow-sm ${
            m.deleted
              ? "bg-slate-100 italic text-slate-400"
              : m.is_mine
                ? "rounded-br-md bg-linear-to-br from-indigo-500 to-fuchsia-500 text-white"
                : "rounded-bl-md bg-white text-slate-800 ring-1 ring-slate-200"
          }`}
        >
          {editing ? (
            <div className="space-y-2">
              <textarea className="w-72 rounded-lg bg-white/90 p-2 text-sm text-slate-800 outline-none" rows={3} maxLength={2000} value={text} onChange={(e) => setText(e.target.value)} autoFocus />
              <div className="flex justify-end gap-2">
                <button className="text-xs text-white/80 hover:text-white" onClick={() => setEditing(false)}>
                  Cancel
                </button>
                <button className="rounded bg-white/90 px-2 py-0.5 text-xs font-semibold text-indigo-700" disabled={busy || !text.trim()} onClick={() => run(() => chatApi.edit(m.id, text))}>
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
        {!m.is_mine && m.can_delete && !m.deleted && (
          <button className="hidden rounded px-1 text-xs text-slate-400 hover:text-red-600 group-hover:block" disabled={busy} onClick={() => confirm("Delete this message? (admin)") && run(() => chatApi.remove(m.id))} aria-label="Delete">
            🗑
          </button>
        )}
      </div>
      <span className="px-1 text-[10px] text-slate-400">
        {formatTime(m.created_at)}
        {m.edited_at && !m.deleted && " · edited"}
      </span>
      <ErrorText error={error} />
    </div>
  );
}

/** Enter sends; Shift+Enter starts a new line. */
function Composer({ householdId, onSent }: { householdId: string; onSent: (m: ChatMessage) => void }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const send = async () => {
    const body = text.trim();
    if (!body || sending) return;
    setSending(true);
    try {
      onSent(await chatApi.send(householdId, body));
      setText("");
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setSending(false);
    }
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="border-t border-slate-100 bg-white/90 p-3">
      <ErrorText error={error} />
      <div className="flex items-end gap-2">
        <textarea
          className="max-h-40 min-h-10 flex-1 resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15"
          rows={Math.min(5, text.split("\n").length)}
          placeholder="Message your house… (Enter to send, Shift+Enter for a new line)"
          maxLength={2000}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          aria-label="Message"
        />
        <Button disabled={!text.trim() || sending} onClick={send}>
          {sending ? "…" : "Send"}
        </Button>
      </div>
    </div>
  );
}
