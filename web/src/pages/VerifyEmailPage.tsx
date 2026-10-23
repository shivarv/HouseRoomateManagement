import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link, useSearchParams } from "react-router";
import { authApi } from "../api/auth";
import { Button, Card, ErrorText, Loading } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";

/** /verify-email?token=… — where the link in the verification email lands. Signed in or not. */
export function VerifyEmailPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { user, updateUser } = useAuth();
  const verify = useQuery({ queryKey: ["verify-email", token], queryFn: () => authApi.verifyEmail(token), retry: false, enabled: !!token });

  // Signed in as this person: the banner goes away straight away.
  useEffect(() => {
    if (verify.data && user?.id === verify.data.id) updateUser(verify.data);
  }, [verify.data, user?.id, updateUser]);

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute -left-24 top-10 h-80 w-80 rounded-full bg-indigo-400/30 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-0 h-96 w-96 rounded-full bg-fuchsia-400/30 blur-3xl" />
      <Card className="relative w-full max-w-md p-7 shadow-xl shadow-indigo-500/10">
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-linear-to-br from-indigo-500 to-fuchsia-500 text-2xl shadow-lg shadow-indigo-500/30">
          📧
        </div>
        {verify.isLoading ? (
          <Loading />
        ) : verify.data ? (
          <>
            <h1 className="text-2xl font-extrabold tracking-tight">Email confirmed 🎉</h1>
            <p className="mt-2 text-sm text-slate-600">
              Thanks, {verify.data.first_name}. <b>{verify.data.email}</b> is confirmed.
            </p>
          </>
        ) : (
          <>
            <h1 className="text-2xl font-extrabold tracking-tight">This link doesn't work</h1>
            <p className="mt-2 text-sm text-slate-600">It may have expired or been mistyped. Log in and choose “Send it again” for a new one.</p>
            <ErrorText error={verify.error} />
          </>
        )}
        <Link to={user ? "/" : "/login"} className="mt-6 block">
          <Button className="w-full">{user ? "Go to the app" : "Log in"}</Button>
        </Link>
      </Card>
    </div>
  );
}
