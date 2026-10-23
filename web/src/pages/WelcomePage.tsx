import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { householdsApi } from "../api/households";
import { Link, useNavigate } from "react-router";
import { Button, Input } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";

/**
 * Signed in but not in any home yet: no tabs, just the two ways in — create a home, or join one
 * with the code or link a roommate sent — and a quick idea of how it works.
 */
export function WelcomePage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  // Homes that invited my email (someone typed it in their invite panel).
  const invites = useQuery({ queryKey: ["my-invites"], queryFn: householdsApi.myInvites });

  const join = (e: FormEvent) => {
    e.preventDefault();
    // Pasting the whole link works too: keep just the code at its end.
    const value = code.trim().split("/").pop()?.split("?")[0] ?? "";
    if (value) navigate(`/join/${value.toUpperCase()}`);
  };

  return (
    <div className="space-y-8">
      <div className="relative overflow-hidden rounded-3xl bg-linear-to-br from-indigo-600 via-violet-600 to-fuchsia-600 p-7 text-white shadow-xl shadow-indigo-500/20 sm:p-9">
        <div className="pointer-events-none absolute -right-12 -top-16 h-56 w-56 rounded-full bg-white/15 blur-2xl" />
        <p className="text-sm font-medium text-white/75">Welcome{user ? `, ${user.name}` : ""} 👋</p>
        <h1 className="mt-1 text-3xl font-extrabold tracking-tight sm:text-4xl">Let's get you into a home</h1>
        <p className="mt-2 max-w-xl text-white/85">
          Roommates keeps chores, groceries and bills fair and in one place. Start your own home, or join the one your roommates
          already set up.
        </p>
      </div>

      {(invites.data?.length ?? 0) > 0 && (
        <div className="space-y-2">
          <h2 className="section-title">📬 You're invited</h2>
          {invites.data!.map((i) => (
            <div key={i.invite_code} className="flex flex-wrap items-center gap-3 rounded-2xl border border-emerald-200 bg-emerald-50/70 p-4 ring-1 ring-emerald-100">
              <span className="text-2xl">🏠</span>
              <span className="min-w-0 flex-1">
                <span className="block font-semibold text-emerald-900">{i.household_name}</span>
                <span className="block text-sm text-emerald-800/80">{i.invited_by ? `${i.invited_by} invited you` : "You were invited"} to join.</span>
              </span>
              <Button onClick={() => navigate(`/join/${i.invite_code}`)}>Join {i.household_name} →</Button>
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          to="/households/new/setup"
          className="card-hover flex flex-col rounded-2xl border border-indigo-200 bg-linear-to-br from-indigo-50 to-fuchsia-50 p-6 shadow-sm ring-1 ring-indigo-100"
        >
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-linear-to-br from-indigo-500 to-fuchsia-500 text-2xl text-white shadow-md">✨</span>
          <span className="text-lg font-bold text-indigo-900">Create a new home</span>
          <span className="mt-1 text-sm text-slate-600">
            A few quick steps with sensible defaults: who lives there, chores, groceries and bills. You'll be its admin.
          </span>
          <span className="mt-5 inline-flex w-fit items-center gap-1 rounded-xl bg-linear-to-r from-indigo-500 to-fuchsia-500 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-indigo-500/30">
            Start setup →
          </span>
        </Link>

        <form onSubmit={join} className="flex flex-col rounded-2xl border border-white/70 bg-white/90 p-6 shadow-sm ring-1 ring-slate-900/5">
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-linear-to-br from-emerald-400 to-teal-500 text-2xl text-white shadow-md">🔑</span>
          <span className="text-lg font-bold">Join a home</span>
          <span className="mb-4 mt-1 text-sm text-slate-600">
            Got an invite on WhatsApp or email? Open the link — or paste it, or the 8-character code, here.
          </span>
          <Input label="Invite code or link" placeholder="e.g. ABCD2345" value={code} onChange={(e) => setCode(e.target.value)} />
          <Button type="submit" variant="secondary" className="mt-3 w-fit" disabled={!code.trim()}>
            Find my home →
          </Button>
        </form>
      </div>

      <div className="rounded-2xl bg-white/70 p-6 ring-1 ring-slate-900/5">
        <h2 className="section-title mb-4">How it works</h2>
        <ol className="grid gap-4 text-sm sm:grid-cols-3">
          <Tip n={1} title="Set up your home">Pick how many roommates, chores and bills. Everything is prefilled; change what you like.</Tip>
          <Tip n={2} title="Invite your roommates">Send the link on WhatsApp or email. They sign up and are matched to their name.</Tip>
          <Tip n={3} title="Let it run">Turns rotate on their own, bills remind you when they're due, and the grocery list stays shared.</Tip>
        </ol>
      </div>
    </div>
  );
}

function Tip({ n, title, children }: { n: number; title: string; children: string }) {
  return (
    <li className="flex gap-3">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">{n}</span>
      <span>
        <span className="block font-semibold text-slate-800">{title}</span>
        <span className="text-slate-600">{children}</span>
      </span>
    </li>
  );
}
