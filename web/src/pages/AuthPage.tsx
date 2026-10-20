import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router";
import { authApi } from "../api/auth";
import { Button, Card, ErrorText, Input } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";

export function AuthPage({ mode }: { mode: "login" | "register" }) {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const submit = useMutation({
    mutationFn: () => (mode === "login" ? authApi.login(email, password) : authApi.register(name, email, password)),
    onSuccess: (res) => {
      signIn(res);
      navigate(from, { replace: true });
    },
  });

  if (user) return <Navigate to="/" replace />;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit.mutate();
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <Card className="w-full max-w-sm">
        <h1 className="mb-1 text-xl font-semibold">🏠 Roommates</h1>
        <p className="mb-6 text-sm text-slate-500">{mode === "login" ? "Sign in to see today's chores." : "Create your account."}</p>
        <form onSubmit={onSubmit} className="space-y-4">
          {mode === "register" && <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} required />}
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
          <ErrorText error={submit.error} />
          <Button type="submit" className="w-full" disabled={submit.isPending}>
            {mode === "login" ? "Sign in" : "Create account"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-slate-500">
          {mode === "login" ? (
            <>New here? <Link className="text-indigo-600 hover:underline" to="/register">Create an account</Link></>
          ) : (
            <>Have an account? <Link className="text-indigo-600 hover:underline" to="/login">Sign in</Link></>
          )}
        </p>
      </Card>
    </div>
  );
}
