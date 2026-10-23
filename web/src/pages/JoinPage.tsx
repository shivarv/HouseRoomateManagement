import { useMutation, useQuery } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router";
import { householdsApi } from "../api/households";
import { Button, Card, ErrorText, Loading } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";
import { useAcceptInvite, useHouseholds } from "../features/households/hooks";
import { lastHousehold } from "../lib/lastHousehold";

/**
 * /join/CODE — where an invite link lands. Signed out: who invited you where, then sign up or
 * log in and come straight back. Signed in: say which roommate you are, and you're in.
 * `?as=MEMBER` (a personal link) picks that name for you.
 */
export function JoinPage() {
  const { code = "" } = useParams();
  const { user, loading } = useAuth();
  if (loading) return <Loading />;
  return <Frame>{user ? <SignedIn code={code} /> : <SignedOut code={code} />}</Frame>;
}

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute -left-24 top-10 h-80 w-80 rounded-full bg-indigo-400/30 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-fuchsia-400/30 blur-3xl" />
      <Card className="relative w-full max-w-md p-7 shadow-xl shadow-indigo-500/10">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-linear-to-br from-indigo-500 to-fuchsia-500 text-2xl shadow-lg shadow-indigo-500/30">
          🏠
        </div>
        {children}
      </Card>
    </div>
  );
}

function SignedOut({ code }: { code: string }) {
  const location = useLocation();
  const invite = useQuery({ queryKey: ["invite-public", code], queryFn: () => householdsApi.invitePublic(code), retry: false });
  // Signing up or in comes back here to finish joining.
  const state = { from: `${location.pathname}${location.search}`, invite: invite.data?.household_name };

  if (invite.isLoading) return <Loading />;
  if (!invite.data) return <BadLink error={invite.error} />;
  return (
    <>
      <p className="text-sm font-semibold uppercase tracking-widest text-indigo-600">You're invited</p>
      <h1 className="mt-1 text-2xl font-extrabold tracking-tight">Join {invite.data.household_name}</h1>
      <p className="mt-2 text-sm text-slate-600">
        {invite.data.people} {invite.data.people === 1 ? "person lives" : "people live"} here. Share chores, groceries and bills — the app
        keeps track of whose turn it is.
      </p>
      <div className="mt-6 space-y-2">
        <Link to="/register" state={state} className="block">
          <Button className="w-full">Create an account to join</Button>
        </Link>
        <Link to="/login" state={state} className="block">
          <Button variant="secondary" className="w-full">
            I already have an account — log in
          </Button>
        </Link>
      </div>
      <p className="mt-4 text-xs text-slate-500">New here? Signing up takes a minute: your name, email and a password, then confirm your email from the link we send — it brings you back here to join.</p>
    </>
  );
}

function SignedIn({ code }: { code: string }) {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const households = useHouseholds();
  const preview = useQuery({ queryKey: ["invite", code], queryFn: () => householdsApi.previewInvite(code), retry: false });
  const accept = useAcceptInvite();
  const open = (id: string) => {
    lastHousehold.set(id);
    navigate(`/households/${id}/reminders`, { replace: true });
  };
  const join = useMutation({
    mutationFn: (memberId: string | null) => accept.mutateAsync({ code, memberId }),
    onSuccess: (house) => open(house.id),
  });

  if (preview.isLoading || households.isLoading) return <Loading />;
  if (!preview.data) return <BadLink error={preview.error} />;
  const p = preview.data;

  if (households.data?.some((h) => h.id === p.household_id)) {
    return (
      <>
        <h1 className="text-2xl font-extrabold tracking-tight">You're already in {p.household_name} 🎉</h1>
        <Button className="mt-6 w-full" onClick={() => open(p.household_id)}>
          Open {p.household_name}
        </Button>
      </>
    );
  }

  const mine = p.unclaimed_members.find((m) => m.id === params.get("as"));
  return (
    <>
      <p className="text-sm font-semibold uppercase tracking-widest text-indigo-600">You're invited</p>
      <h1 className="mt-1 text-2xl font-extrabold tracking-tight">Join {p.household_name}</h1>
      {mine ? (
        <>
          <p className="mt-2 text-sm text-slate-600">
            This invite is for <b>{mine.display_name}</b>. Is that you?
          </p>
          <div className="mt-6 space-y-2">
            <Button className="w-full" disabled={join.isPending} onClick={() => join.mutate(mine.id)}>
              {join.isPending ? "Joining…" : `Yes, I'm ${mine.display_name} — join`}
            </Button>
            <Button variant="ghost" className="w-full" disabled={join.isPending} onClick={() => join.mutate(null)}>
              No, add me as someone new
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="mt-2 text-sm text-slate-600">
            {p.unclaimed_members.length > 0 ? "Which one is you? Your roommates added these names already." : "You'll be added to the house."}
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            {p.unclaimed_members.map((m) => (
              <Button key={m.id} variant="secondary" disabled={join.isPending} onClick={() => join.mutate(m.id)}>
                I'm {m.display_name}
              </Button>
            ))}
            <Button disabled={join.isPending} onClick={() => join.mutate(null)}>
              {p.unclaimed_members.length > 0 ? "I'm not listed — add me" : "Join"}
            </Button>
          </div>
        </>
      )}
      <ErrorText error={join.error} />
    </>
  );
}

function BadLink({ error }: { error: unknown }) {
  return (
    <>
      <h1 className="text-2xl font-extrabold tracking-tight">This invite doesn't work</h1>
      <p className="mt-2 text-sm text-slate-600">The link may be mistyped or the home was deleted. Ask for a new link, or enter the code yourself.</p>
      <ErrorText error={error} />
      <Link to="/" className="mt-6 block">
        <Button variant="secondary" className="w-full">
          Go to the app
        </Button>
      </Link>
    </>
  );
}
