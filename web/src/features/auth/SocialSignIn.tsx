import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { authApi } from "../../api/auth";
import { Button, ErrorText, Input } from "../../components/ui";
import type { OAuthResult, SocialProvider, TokenResponse } from "../../types/api";

// The providers' own scripts, loaded only on the sign-in screen.
declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize(options: { client_id: string; callback: (res: { credential: string }) => void; ux_mode?: string }): void;
          renderButton(el: HTMLElement, options: Record<string, unknown>): void;
        };
      };
    };
    FB?: {
      init(options: { appId: string; version: string; cookie?: boolean; xfbml?: boolean }): void;
      login(cb: (res: { authResponse?: { accessToken: string } | null }) => void, options: { scope: string }): void;
    };
  }
}

const loaded = new Map<string, Promise<void>>();
function loadScript(src: string): Promise<void> {
  if (!loaded.has(src)) {
    loaded.set(
      src,
      new Promise((resolve, reject) => {
        const el = document.createElement("script");
        el.src = src;
        el.async = true;
        el.onload = () => resolve();
        el.onerror = () => reject(new Error("Couldn't load the sign-in button. Check your connection."));
        document.head.appendChild(el);
      }),
    );
  }
  return loaded.get(src)!;
}

/**
 * "Continue with Google / Facebook": the provider's sign-in, then our backend. A new account the
 * provider didn't give enough for (a name, and an email or phone) gets a short form first.
 * Mirrors iOS AuthView's buttons.
 */
export function SocialSignIn({ onSignedIn }: { onSignedIn: (res: TokenResponse) => void }) {
  const config = useQuery({ queryKey: ["auth-providers"], queryFn: authApi.providers, staleTime: 60 * 60_000 });
  const [pending, setPending] = useState<{ provider: SocialProvider; token: string; result: OAuthResult } | null>(null);
  const signIn = useMutation({
    mutationFn: ({ provider, token }: { provider: SocialProvider; token: string }) =>
      authApi.oauth(provider, token).then((result) => ({ provider, token, result })),
    onSuccess: ({ provider, token, result }) => {
      setExisting(null);
      if (result.access_token && result.user) onSignedIn({ access_token: result.access_token, token_type: "bearer", user: result.user });
      else if (result.existing_email) setExisting({ provider, email: result.existing_email });
      else setPending({ provider, token, result });
    },
  });
  // Their email has a password account: log in with it, then connect this provider in Profile.
  const [existing, setExisting] = useState<{ provider: SocialProvider; email: string } | null>(null);

  const google = config.data?.google?.web_client_id;
  const facebook = config.data?.facebook?.app_id;
  if (!google && !facebook) return null;

  if (pending) {
    return <FinishProfile {...pending} onSignedIn={onSignedIn} onCancel={() => setPending(null)} />;
  }
  return (
    <div className="space-y-3">
      {google && <GoogleButton clientId={google} onToken={(token) => signIn.mutate({ provider: "google", token })} />}
      {facebook && <FacebookButton appId={facebook} busy={signIn.isPending} onToken={(token) => signIn.mutate({ provider: "facebook", token })} />}
      <ErrorText error={signIn.error} />
      {existing && (
        <p className="rounded-xl bg-indigo-50 p-3 text-sm text-indigo-900">
          <b>{existing.email}</b> already has an account. Log in with its password below, then connect{" "}
          {existing.provider === "google" ? "Google" : "Facebook"} in Profile → Ways to sign in.
        </p>
      )}
      <div className="flex items-center gap-3 text-xs font-medium uppercase tracking-wider text-slate-400">
        <span className="h-px flex-1 bg-slate-200" /> or <span className="h-px flex-1 bg-slate-200" />
      </div>
    </div>
  );
}

/** Google draws its own button (its branding rules); we size it to the card. */
export function GoogleButton({
  clientId,
  onToken,
  text = "continue_with",
  width,
}: {
  clientId: string;
  onToken: (idToken: string) => void;
  text?: "continue_with" | "signin_with";
  width?: number;
}) {
  const box = useRef<HTMLDivElement>(null);
  const latest = useRef(onToken);
  latest.current = onToken;
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let live = true;
    loadScript("https://accounts.google.com/gsi/client")
      .then(() => {
        if (!live || !box.current || !window.google) return;
        window.google.accounts.id.initialize({ client_id: clientId, callback: (res) => latest.current(res.credential) });
        window.google.accounts.id.renderButton(box.current, {
          type: "standard", theme: "outline", size: "large", text, shape: "pill",
          width: width ?? Math.min(400, box.current.clientWidth || 320),
        });
      })
      .catch((e: Error) => live && setError(e));
    return () => {
      live = false;
    };
  }, [clientId, text, width]);

  return (
    <>
      <div ref={box} className="flex min-h-11 justify-center" />
      <ErrorText error={error} />
    </>
  );
}

export function FacebookButton({
  appId,
  busy,
  onToken,
  label = "Continue with Facebook",
}: {
  appId: string;
  busy: boolean;
  onToken: (accessToken: string) => void;
  label?: string;
}) {
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    loadScript("https://connect.facebook.net/en_US/sdk.js")
      .then(() => {
        window.FB?.init({ appId, version: "v19.0", cookie: false, xfbml: false });
        setReady(true);
      })
      .catch(setError);
  }, [appId]);

  const click = () =>
    window.FB?.login((res) => res.authResponse?.accessToken && onToken(res.authResponse.accessToken), { scope: "public_profile,email" });

  return (
    <>
      <button
        type="button"
        onClick={click}
        disabled={!ready || busy}
        className="flex h-11 w-full items-center justify-center gap-2 rounded-full bg-[#1877F2] text-sm font-semibold text-white shadow-sm transition hover:brightness-110 disabled:opacity-60"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden="true">
          <path d="M24 12.07C24 5.41 18.63 0 12 0S0 5.41 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.05V9.41c0-3.02 1.8-4.7 4.54-4.7 1.31 0 2.68.24 2.68.24v2.97h-1.51c-1.49 0-1.95.93-1.95 1.88v2.26h3.33l-.53 3.49h-2.8V24C19.61 23.1 24 18.1 24 12.07Z" />
        </svg>
        {label}
      </button>
      <ErrorText error={error} />
    </>
  );
}

/** A new account the provider didn't give enough for: a first or last name, and an email or phone. */
function FinishProfile({
  provider,
  token,
  result,
  onSignedIn,
  onCancel,
}: {
  provider: SocialProvider;
  token: string;
  result: OAuthResult;
  onSignedIn: (res: TokenResponse) => void;
  onCancel: () => void;
}) {
  const [first, setFirst] = useState(result.first_name);
  const [last, setLast] = useState(result.last_name);
  const [email, setEmail] = useState(result.email ?? "");
  const [phone, setPhone] = useState("");
  const askName = result.missing.includes("name");
  const askContact = result.missing.includes("contact");
  const finish = useMutation({
    mutationFn: () =>
      authApi.oauth(provider, token, {
        first_name: first.trim(),
        last_name: last.trim(),
        email: askContact && email.trim() ? email.trim() : undefined,
        phone: askContact && phone.trim() ? phone.trim() : undefined,
      }),
    onSuccess: (res) => res.access_token && res.user && onSignedIn({ access_token: res.access_token, token_type: "bearer", user: res.user }),
  });
  const ok = (!askName || first.trim() || last.trim()) && (!askContact || email.trim() || phone.trim());

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (ok) finish.mutate();
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <h2 className="text-lg font-bold text-slate-900">Finish your profile</h2>
        <p className="text-sm text-slate-500">Your roommates need to know who you are and how to reach you.</p>
      </div>
      {askName && (
        <div className="grid grid-cols-2 gap-3">
          <Input label="First name" value={first} maxLength={50} onChange={(e) => setFirst(e.target.value)} autoComplete="given-name" autoFocus />
          <Input label="Last name" value={last} maxLength={50} onChange={(e) => setLast(e.target.value)} autoComplete="family-name" />
        </div>
      )}
      {askContact && (
        <>
          <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          <Input label="or phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1 617 555 0100" autoComplete="tel" />
          <p className="text-xs text-slate-500">One of the two is enough.</p>
        </>
      )}
      <ErrorText error={finish.error} />
      <div className="flex gap-2">
        <Button type="submit" className="flex-1" disabled={!ok || finish.isPending}>
          {finish.isPending ? "One moment…" : "Continue"}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Back
        </Button>
      </div>
    </form>
  );
}
