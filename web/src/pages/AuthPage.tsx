import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { authApi } from "../api/auth";
import { Button, Card, ErrorText, Input } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";

/** Where to go after signing in, and (from an invite link) which house is waiting. */
type AuthState = { from?: string; invite?: string } | null;

/** The start screen: log in or sign up, on one card. An invite link's house is shown on top. */
export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const state = useLocation().state as AuthState;
  const from = state?.from ?? "/";
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = useMutation({
    mutationFn: () => (mode === "login" ? authApi.login(email, password) : authApi.register(firstName.trim(), lastName.trim(), email, password)),
    onSuccess: (res) => {
      signIn(res);
      navigate(from, { replace: true });
    },
  });

  if (user) return <Navigate to={from} replace />;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit.mutate();
  };
  const tab = (to: "login" | "register", label: string) => (
    <Link
      to={to === "login" ? "/login" : "/register"}
      state={state} // switching keeps where to go next (e.g. back to an invite)
      replace
      className={`flex-1 rounded-xl px-3 py-2 text-center text-sm font-semibold transition ${
        mode === to ? "bg-linear-to-r from-indigo-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30" : "text-slate-600 hover:bg-indigo-50"
      }`}
    >
      {label}
    </Link>
  );

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute -left-24 top-10 h-80 w-80 rounded-full bg-indigo-400/30 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-fuchsia-400/30 blur-3xl" />
      <Card className="relative w-full max-w-sm p-7 shadow-xl shadow-indigo-500/10">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-linear-to-br from-indigo-500 to-fuchsia-500 text-2xl shadow-lg shadow-indigo-500/30">
          🏠
        </div>
        <h1 className="mb-1 text-2xl font-extrabold tracking-tight">
          <span className="text-gradient">Roommates</span>
        </h1>
        <p className="mb-4 text-sm text-slate-500">Chores, groceries and bills for your home, without the group-chat chaos.</p>

        {state?.invite && (
          <div className="mb-4 rounded-xl bg-indigo-50 px-3 py-2 text-sm text-indigo-900 ring-1 ring-indigo-100">
            🎉 You're invited to <b>{state.invite}</b>. {mode === "register" ? "Create your account" : "Log in"} and you'll join right after.
          </div>
        )}

        <div className="mb-5 flex gap-1 rounded-2xl bg-slate-100 p-1">
          {tab("login", "Log in")}
          {tab("register", "Sign up")}
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          {mode === "register" && (
            <div className="grid grid-cols-2 gap-3">
              <Input label="First name" value={firstName} onChange={(e) => setFirstName(e.target.value)} required maxLength={50} autoComplete="given-name" />
              <Input label="Last name (optional)" value={lastName} onChange={(e) => setLastName(e.target.value)} maxLength={50} autoComplete="family-name" />
            </div>
          )}
          <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={mode === "register" ? 8 : undefined}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
          {mode === "register" && (
            <ul className="space-y-1 text-xs text-slate-500">
              <li>✓ Use an email you'll remember — it's how you log in on any device.</li>
              <li>✓ At least 8 characters for the password.</li>
              <li>✓ Next you'll create your home, or join one with a code or link.</li>
            </ul>
          )}
          <ErrorText error={submit.error} />
          <Button type="submit" className="w-full" disabled={submit.isPending}>
            {submit.isPending ? "One moment…" : mode === "login" ? "Log in" : state?.invite ? `Create account & join ${state.invite}` : "Create account"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-500">
          {mode === "login" ? (
            <>
              New here?{" "}
              <Link className="font-medium text-indigo-600 hover:underline" to="/register" state={state} replace>
                Sign up
              </Link>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <Link className="font-medium text-indigo-600 hover:underline" to="/login" state={state} replace>
                Log in
              </Link>
            </>
          )}
        </p>
      </Card>
    </div>
  );
}
