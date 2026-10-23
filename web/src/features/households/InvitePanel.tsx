import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { householdsApi } from "../../api/households";
import { Button, ErrorText } from "../../components/ui";
import type { EmailInviteResults, HouseholdDetail, Member } from "../../types/api";

/**
 * The link that joins a house: `/join/CODE`, or `/join/CODE?as=MEMBER` for someone already
 * added by name, so they're matched to that name. Opening it asks to sign up or log in first.
 */
export function inviteLink(code: string, member?: Member): string {
  const link = `${window.location.origin}/join/${code}`;
  return member ? `${link}?as=${member.id}` : link;
}

function inviteMessage(house: HouseholdDetail, member?: Member): string {
  const hi = member ? `Hi ${member.display_name}! ` : "Hi! ";
  return (
    `${hi}Join our home “${house.name}” on Roommates to share chores, groceries and bills: ` +
    `${inviteLink(house.invite_code, member)}\n\n(Or sign up and enter invite code ${house.invite_code}.)`
  );
}

/** WhatsApp's own share link: opens WhatsApp with the message ready; you pick the chat. Free. */
const whatsappUrl = (text: string) => `https://wa.me/?text=${encodeURIComponent(text)}`;

/** Opens your own email app with the invite filled in (no email service needed). */
const emailUrl = (house: HouseholdDetail, text: string) =>
  `mailto:?subject=${encodeURIComponent(`Join ${house.name} on Roommates`)}&body=${encodeURIComponent(text)}`;

function ShareButtons({ house, member, compact = false }: { house: HouseholdDetail; member?: Member; compact?: boolean }) {
  const [copied, setCopied] = useState(false);
  const text = inviteMessage(house, member);
  const copy = async () => {
    await navigator.clipboard?.writeText(inviteLink(house.invite_code, member));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  const size = compact ? "px-2.5 py-1 text-xs" : "px-3.5 py-2 text-sm";
  return (
    <div className="flex flex-wrap gap-2">
      <a
        href={whatsappUrl(text)}
        target="_blank"
        rel="noreferrer"
        className={`inline-flex items-center gap-1.5 rounded-xl bg-emerald-500 font-semibold text-white shadow-sm transition hover:bg-emerald-600 ${size}`}
      >
        💬 WhatsApp
      </a>
      <a
        href={emailUrl(house, text)}
        className={`inline-flex items-center gap-1.5 rounded-xl bg-white font-semibold text-indigo-700 shadow-sm ring-1 ring-indigo-200 transition hover:bg-indigo-50 ${size}`}
      >
        ✉️ Email
      </a>
      <button
        type="button"
        onClick={copy}
        className={`inline-flex items-center gap-1.5 rounded-xl bg-white font-semibold text-slate-700 shadow-sm ring-1 ring-slate-200 transition hover:bg-slate-50 ${size}`}
      >
        {copied ? "✓ Copied" : "🔗 Copy link"}
      </button>
    </div>
  );
}

/** Invite people to a house: one link for anyone, and a personal one for each roommate added by name. */
export function InvitePanel({ house, onClose }: { house: HouseholdDetail; onClose?: () => void }) {
  const waiting = house.members.filter((m) => !m.has_account);

  return (
    <div className="space-y-4 rounded-2xl border border-indigo-100 bg-white/95 p-5 shadow-sm ring-1 ring-indigo-50">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold">Invite people to {house.name}</h2>
          <p className="text-sm text-slate-500">
            They open the link, sign up (or log in if they have an account) and join. The code{" "}
            <span className="font-mono font-semibold text-slate-700">{house.invite_code}</span> works too.
          </p>
        </div>
        {onClose && (
          <Button variant="ghost" onClick={onClose} aria-label="Close">
            ✕
          </Button>
        )}
      </div>
      <ShareButtons house={house} />
      <EmailInvites house={house} />

      {waiting.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Haven't joined yet</p>
          <ul className="divide-y divide-slate-100 rounded-xl border border-slate-100">
            {waiting.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-3 px-3 py-2">
                <span className="flex-1 text-sm font-medium">{m.display_name}</span>
                <ShareButtons house={house} member={m} compact />
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-slate-500">A personal link matches them to their name when they join.</p>
        </div>
      )}
    </div>
  );
}

/** Addresses from "a@x.com, b@y.com" or one per line. */
function parseEmails(text: string): string[] {
  return [...new Set(text.split(/[\s,;]+/).map((e) => e.trim()).filter(Boolean))];
}

/** Invite by email: saved as pending (they see it once signed in) and emailed when email is set up. */
function EmailInvites({ house }: { house: HouseholdDetail }) {
  const queryClient = useQueryClient();
  const key = ["email-invites", house.id];
  const pending = useQuery({ queryKey: key, queryFn: () => householdsApi.pendingInvites(house.id) });
  const [text, setText] = useState("");
  const [result, setResult] = useState<EmailInviteResults | null>(null);
  const emails = parseEmails(text);
  const invalid = emails.filter((e) => !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e));
  const send = useMutation({
    mutationFn: () => householdsApi.emailInvites(house.id, emails),
    onSuccess: (res) => {
      setResult(res);
      setText("");
      queryClient.invalidateQueries({ queryKey: key });
    },
  });
  const cancel = useMutation({
    mutationFn: householdsApi.cancelInvite,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
  const unsent = result?.results.filter((r) => r.status === "saved").map((r) => r.email) ?? [];

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (emails.length && !invalid.length) send.mutate();
  };

  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-slate-500">Invite by email</p>
      <form onSubmit={submit} className="flex flex-wrap gap-2">
        <input
          className="min-w-56 flex-1 rounded-xl border border-slate-200 bg-white/90 px-3 py-2 text-sm shadow-sm outline-none transition placeholder:text-slate-400 hover:border-indigo-300 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15"
          placeholder="bea@example.com, cy@example.com"
          value={text}
          onChange={(e) => (setText(e.target.value), setResult(null))}
          aria-label="Email addresses"
        />
        <Button type="submit" disabled={!emails.length || invalid.length > 0 || send.isPending}>
          {send.isPending ? "Inviting…" : emails.length > 1 ? `Invite ${emails.length}` : "Invite"}
        </Button>
      </form>
      {invalid.length > 0 && <p className="mt-1 text-sm text-red-600">Check {invalid.join(", ")}: that isn't an email address.</p>}
      <ErrorText error={send.error ?? cancel.error} />
      {result && (
        <div className="mt-2 space-y-1 text-sm">
          {result.results.map((r) => (
            <p key={r.email} className={r.status === "member" ? "text-slate-500" : "text-emerald-700"}>
              {r.status === "sent" ? "✓ Emailed" : r.status === "saved" ? "✓ Invited" : "Already in the house:"} {r.email}
            </p>
          ))}
          {unsent.length > 0 && (
            <p className="rounded-xl bg-amber-50 px-3 py-2 text-amber-900 ring-1 ring-amber-100">
              Sending emails from the app isn't set up yet, so they weren't emailed — they'll see the invite when they sign up with that
              email.{" "}
              <a
                className="font-semibold underline"
                href={`mailto:${unsent.join(",")}?subject=${encodeURIComponent(`Join ${house.name} on Roommates`)}&body=${encodeURIComponent(inviteMessage(house))}`}
              >
                Send it from your email app
              </a>
            </p>
          )}
        </div>
      )}
      {(pending.data?.length ?? 0) > 0 && (
        <ul className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-100 text-sm">
          {pending.data!.map((p) => (
            <li key={p.id} className="flex flex-wrap items-center gap-2 px-3 py-2">
              <span className="flex-1">
                {p.email}
                <span className="ml-2 text-xs text-slate-500">
                  {p.last_sent_at ? "emailed" : "invited"}
                  {p.invited_by && ` by ${p.invited_by.display_name}`} · waiting to join
                </span>
              </span>
              {p.can_cancel && (
                <Button variant="ghost" disabled={cancel.isPending} onClick={() => cancel.mutate(p.id)}>
                  Cancel
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
