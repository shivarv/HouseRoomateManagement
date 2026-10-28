import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { authApi } from "../../api/auth";
import { Button, Card, ErrorText, Input } from "../../components/ui";
import type { SocialProvider, User } from "../../types/api";
import { useAuth } from "./AuthContext";
import { FacebookButton, GoogleButton } from "./SocialSignIn";

const NAMES: Record<SocialProvider, string> = { google: "Google", facebook: "Facebook", apple: "Apple" };

/**
 * Password, Google, Facebook and Apple: connect any of them and each signs in to this same account.
 * Disconnecting is refused for the last way in (the server checks too). Mirrors iOS SignInMethodsSection.
 */
export function SignInMethods() {
  const { user, updateUser } = useAuth();
  const config = useQuery({ queryKey: ["auth-providers"], queryFn: authApi.providers, staleTime: 60 * 60_000 });
  const [note, setNote] = useState<string | null>(null);
  const [editingPassword, setEditingPassword] = useState(false);
  const link = useMutation({
    mutationFn: ({ provider, token }: { provider: SocialProvider; token: string }) => authApi.linkSignIn(provider, token),
    onSuccess: (u, { provider }) => {
      updateUser(u);
      setNote(`${NAMES[provider]} connected. You can sign in with it now.`);
    },
  });
  const unlink = useMutation({
    mutationFn: authApi.unlinkSignIn,
    onSuccess: (u, provider) => {
      updateUser(u);
      setNote(`${NAMES[provider]} disconnected.`);
    },
  });
  if (!user) return null;

  const identity = (p: SocialProvider) => user.identities?.find((i) => i.provider === p);
  const hasPassword = user.providers.includes("password");
  const ways = (user.identities?.length ?? 0) + (hasPassword ? 1 : 0);
  const busy = link.isPending || unlink.isPending;
  const disconnect = (p: SocialProvider) =>
    confirm(`Disconnect ${NAMES[p]}?\n\nYou won't be able to sign in with ${NAMES[p]} any more. You can connect it again later.`) &&
    unlink.mutate(p);

  const connectButton = (p: SocialProvider) => {
    const onToken = (token: string) => {
      setNote(null);
      link.mutate({ provider: p, token });
    };
    if (p === "google" && config.data?.google?.web_client_id)
      return <GoogleButton clientId={config.data.google.web_client_id} onToken={onToken} text="signin_with" width={200} />;
    if (p === "facebook" && config.data?.facebook?.app_id)
      return (
        <div className="w-48">
          <FacebookButton appId={config.data.facebook.app_id} busy={busy} onToken={onToken} label="Connect" />
        </div>
      );
    return <span className="text-xs text-slate-400">{p === "apple" ? "Connect in the iPhone app" : "Coming soon"}</span>;
  };

  return (
    <Card className="max-w-lg space-y-3">
      <div>
        <h2 className="font-semibold text-slate-900">Ways to sign in</h2>
        <p className="text-sm text-slate-500">Any of these signs in to this same account. You always keep at least one.</p>
      </div>
      <ul className="divide-y divide-slate-100">
        <Row icon="🔑" title="Password" detail={hasPassword ? user.email : "Not set"}>
          <Button variant="ghost" onClick={() => setEditingPassword((v) => !v)}>
            {hasPassword ? "Change" : "Set"}
          </Button>
        </Row>
        {editingPassword && (
          <li className="py-3">
            <PasswordForm
              user={user}
              onSaved={(u) => {
                updateUser(u);
                setEditingPassword(false);
                setNote(hasPassword ? "Password changed." : "Password set. You can log in with your email too.");
              }}
            />
          </li>
        )}
        {(["google", "facebook", "apple"] as const).map((p) => {
          const connected = identity(p);
          return (
            <Row key={p} icon={p === "google" ? "🟢" : p === "facebook" ? "🔵" : "⚫"} title={NAMES[p]}
              detail={connected ? (connected.email ?? "Connected") : "Not connected"}>
              {connected ? (
                <Button variant="ghost" disabled={busy || ways <= 1} onClick={() => disconnect(p)}
                  title={ways <= 1 ? "Your only way to sign in" : undefined}>
                  Disconnect
                </Button>
              ) : (
                connectButton(p)
              )}
            </Row>
          );
        })}
      </ul>
      {note && <p className="text-sm text-emerald-600">{note}</p>}
      <ErrorText error={link.error ?? unlink.error} />
    </Card>
  );
}

function Row({ icon, title, detail, children }: { icon: string; title: string; detail: string | null; children: React.ReactNode }) {
  return (
    <li className="flex items-center justify-between gap-3 py-3">
      <div className="flex min-w-0 items-center gap-3">
        <span aria-hidden="true">{icon}</span>
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-900">{title}</p>
          {detail && <p className="truncate text-xs text-slate-500">{detail}</p>}
        </div>
      </div>
      <div className="shrink-0">{children}</div>
    </li>
  );
}

/** A first password (accounts made with Google, Apple or Facebook), or a new one. */
function PasswordForm({ user, onSaved }: { user: User; onSaved: (u: User) => void }) {
  const hasPassword = user.providers.includes("password");
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const save = useMutation({ mutationFn: () => authApi.setPassword(next, hasPassword ? current : undefined), onSuccess: onSaved });
  if (!user.email) return <p className="text-sm text-slate-500">Add an email above first. It's what you'll log in with.</p>;
  const ok = next.length >= 8 && (!hasPassword || current);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (ok) save.mutate();
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      {hasPassword && (
        <Input label="Current password" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} autoComplete="current-password" />
      )}
      <Input label="New password (8+ characters)" type="password" value={next} maxLength={64} onChange={(e) => setNext(e.target.value)} autoComplete="new-password" />
      <p className="text-xs text-slate-500">You'll log in with {user.email} and this password.</p>
      <ErrorText error={save.error} />
      <Button type="submit" disabled={!ok || save.isPending}>
        {save.isPending ? "Saving…" : "Save password"}
      </Button>
    </form>
  );
}
