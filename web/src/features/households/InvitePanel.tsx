import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../api/client";
import { householdsApi } from "../../api/households";
import { Badge, Button, Card, ErrorText, Input } from "../../components/ui";
import type { EmailInviteResults, HouseholdDetail } from "../../types/api";

/** The link that joins a house. Opening it asks to log in or sign up first. */
export function inviteLink(code: string): string {
  return `${window.location.origin}/join/${code}`;
}

function inviteMessage(house: HouseholdDetail): string {
  return (
    `Hi! Join our home “${house.name}” on Roommates to share chores, groceries and bills: ` +
    `${inviteLink(house.invite_code)}\n\n(Or sign up and enter invite code ${house.invite_code}.)`
  );
}

/** WhatsApp's own share link: opens WhatsApp with the message ready; you pick the chat. Free. */
const whatsappUrl = (text: string) => `https://wa.me/?text=${encodeURIComponent(text)}`;

/** Opens your own email app with the invite filled in (no email service needed). */
const emailUrl = (house: HouseholdDetail, text: string, to = "") =>
  `mailto:${to}?subject=${encodeURIComponent(`Join ${house.name} on Roommates`)}&body=${encodeURIComponent(text)}`;

/** Styled like the secondary Button, for links. */
const linkButton =
  "inline-flex items-center justify-center gap-1.5 rounded-xl px-3.5 py-2 text-sm font-medium bg-white/90 text-slate-700 ring-1 ring-slate-200 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:bg-white hover:text-indigo-700 hover:shadow-md hover:ring-indigo-300";

function ShareButtons({ house }: { house: HouseholdDetail }) {
  const [copied, setCopied] = useState(false);
  const text = inviteMessage(house);
  const copy = async () => {
    await navigator.clipboard?.writeText(inviteLink(house.invite_code));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="flex flex-wrap gap-2">
      <a href={whatsappUrl(text)} target="_blank" rel="noreferrer" className={linkButton}>
        💬 WhatsApp
      </a>
      <a href={emailUrl(house, text)} className={linkButton}>
        ✉️ Email app
      </a>
      <Button variant="secondary" onClick={copy}>
        {copied ? "✓ Copied" : "🔗 Copy link"}
      </Button>
    </div>
  );
}

/**
 * Invite roommates: their email gets the invite, and they log in or sign up from it and join (with
 * their own name). Or share the house link on WhatsApp. Anyone in the house can invite.
 */
export function InvitePanel({ house, onClose }: { house: HouseholdDetail; onClose?: () => void }) {
  return (
    <Card className="space-y-5">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="font-semibold">Invite roommates</h2>
          <p className="text-sm text-slate-500">They get an invite, log in or sign up from it, and join {house.name} — at the end of every chore rotation.</p>
        </div>
        {onClose && (
          <Button variant="ghost" onClick={onClose} aria-label="Close">
            ✕
          </Button>
        )}
      </div>

      <EmailInvites house={house} />

      <div className="border-t border-slate-100 pt-4">
        <p className="mb-2 text-sm font-medium text-slate-700">Or share the link</p>
        <ShareButtons house={house} />
        <p className="mt-2 text-xs text-slate-500">
          Anyone with the link can join. The code <Badge tone="indigo">{house.invite_code}</Badge> works too.
        </p>
        {house.my_role === "admin" && <ResetLink house={house} />}
      </div>
    </Card>
  );
}

/** Admins: a new shared link when the old one reached the wrong people. Emailed invites keep working. */
function ResetLink({ house }: { house: HouseholdDetail }) {
  const queryClient = useQueryClient();
  const reset = useMutation({
    mutationFn: () => householdsApi.resetInviteCode(house.id),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  const ask = () =>
    confirm("Make a new link? The current link and code stop working right away — share the new one with anyone who still needs it.") &&
    reset.mutate();
  return (
    <div className="mt-2">
      <button className="text-xs font-semibold text-indigo-600 hover:underline disabled:opacity-50" disabled={reset.isPending} onClick={ask}>
        {reset.isPending ? "Making a new link…" : reset.isSuccess ? "✓ New link made — old links no longer work" : "↻ Make a new link (stops the old one)"}
      </button>
      <ErrorText error={reset.error} />
    </div>
  );
}

/** Addresses from "a@x.com, b@y.com" or one per line. */
function parseEmails(text: string): string[] {
  return [...new Set(text.split(/[\s,;]+/).map((e) => e.trim()).filter(Boolean))];
}

/** Invite by email: saved as pending (listed with the roommates until they join) and emailed. */
function EmailInvites({ house }: { house: HouseholdDetail }) {
  const queryClient = useQueryClient();
  const key = ["email-invites", house.id];
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
  const unsent = result?.results.filter((r) => r.status === "saved" || r.status === "failed").map((r) => r.email) ?? [];

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (emails.length && !invalid.length) send.mutate();
  };

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
        <div className="min-w-56 flex-1">
          <Input
            label="Their email"
            placeholder="bea@example.com, cy@example.com"
            value={text}
            onChange={(e) => (setText(e.target.value), setResult(null))}
          />
        </div>
        <Button type="submit" disabled={!emails.length || invalid.length > 0 || send.isPending}>
          {send.isPending ? "Inviting…" : emails.length > 1 ? `Invite ${emails.length}` : "Invite"}
        </Button>
      </form>
      {invalid.length > 0 && <ErrorText error={`Check ${invalid.join(", ")}: that isn't an email address.`} />}
      <ErrorText
        error={
          send.error instanceof ApiError && (send.error.status >= 500 || send.error.status === 0)
            ? "We couldn't reach the server, so nothing was sent. Check your connection and try again in a minute."
            : send.error
        }
      />

      {result && (
        <div className="space-y-1 text-sm">
          {result.results.map((r) => (
            <InviteResultLine key={r.email} result={r} />
          ))}
          {unsent.length > 0 && (
            <p className="text-slate-600">
              You can also{" "}
              <a className="font-semibold text-indigo-600 underline" href={emailUrl(house, inviteMessage(house), unsent.join(","))}>
                send it from your own email app
              </a>{" "}
              or share the link below.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** One address's outcome, in words the sender can act on. */
function InviteResultLine({ result: r }: { result: EmailInviteResults["results"][number] }) {
  if (r.status === "sent") return <p className="text-emerald-700">✓ Invite emailed to {r.email}</p>;
  if (r.status === "member") return <p className="text-slate-500">{r.email} is already in the house.</p>;
  const why =
    r.status === "saved"
      ? "Sending email isn't set up on this server yet."
      : r.reason === "bad_address"
        ? "That address doesn't look right — check for typos and invite again."
        : r.reason === "unavailable"
          ? "Our email service isn't responding right now. Try “Invite” again in a few minutes."
          : "Our email service didn't accept it. Try again later; if it keeps happening, the app's email setup needs a look.";
  return (
    <p className="rounded-xl bg-amber-50 px-3 py-2 text-amber-900 ring-1 ring-amber-100">
      <b>Couldn't email {r.email}.</b> {why}
    </p>
  );
}
