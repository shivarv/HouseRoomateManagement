import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { authApi } from "../api/auth";
import { Button, Card, ErrorText, Loading } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";

/** A path on our own site, never another host. */
const safeNext = (next: string | null) => (next && next.startsWith("/") && !next.startsWith("//") ? next : "/");

/**
 * /verify-email?token=…&next=… — where the link in the confirmation email lands. The first open
 * confirms the address and signs in, then goes on to `next` (e.g. the invite they signed up from).
 */
export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const next = safeNext(params.get("next"));
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const verify = useQuery({ queryKey: ["verify-email", token], queryFn: () => authApi.verifyEmail(token), retry: false, enabled: !!token, staleTime: Infinity });

  useEffect(() => {
    const res = verify.data;
    if (!res?.access_token) return;
    signIn({ access_token: res.access_token, token_type: "bearer", user: res.user });
    navigate(next, { replace: true });
  }, [verify.data, signIn, navigate, next]);

  const signedIn = !!user;
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute -left-24 top-10 h-80 w-80 rounded-full bg-indigo-400/30 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-fuchsia-400/30 blur-3xl" />
      <Card className="relative w-full max-w-md p-7 shadow-xl shadow-indigo-500/10">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-linear-to-br from-indigo-500 to-fuchsia-500 text-2xl shadow-lg shadow-indigo-500/30">
          📧
        </div>
        {verify.isLoading || verify.data?.access_token ? (
          <Loading />
        ) : verify.data ? (
          <>
            <h1 className="text-2xl font-extrabold tracking-tight">Email already confirmed</h1>
            <p className="mt-2 text-sm text-slate-600">
              <b>{verify.data.user.email}</b> is confirmed. {signedIn ? "You're all set." : "Log in to continue."}
            </p>
          </>
        ) : (
          <>
            <h1 className="text-2xl font-extrabold tracking-tight">This link doesn't work</h1>
            <p className="mt-2 text-sm text-slate-600">It may have expired or been mistyped. Log in with your email and password and we'll offer to send a new one.</p>
            <ErrorText error={verify.error} />
          </>
        )}
        {!verify.isLoading && !verify.data?.access_token && (
          <Link to={signedIn ? next : "/login"} state={signedIn ? undefined : { from: next }} className="mt-6 block">
            <Button className="w-full">{signedIn ? "Go to the app" : "Log in"}</Button>
          </Link>
        )}
      </Card>
    </div>
  );
}
