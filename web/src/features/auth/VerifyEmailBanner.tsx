import { useMutation } from "@tanstack/react-query";
import { authApi } from "../../api/auth";
import { useAuth } from "./AuthContext";

/** Until I open the link we emailed: a reminder, with a way to get the email again. */
export function VerifyEmailBanner() {
  const { user, updateUser } = useAuth();
  const resend = useMutation({ mutationFn: authApi.resendVerification });
  // Verified in another tab? Check again before sending another email.
  const refresh = useMutation({ mutationFn: authApi.me, onSuccess: updateUser });
  if (!user || user.email_verified) return null;

  const result = resend.data;
  return (
    <div className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-900">
      <span className="flex-1">
        📧 Confirm your email: open the link we sent to <b>{user.email}</b>.
        {result?.sent && " Sent again — check your inbox (and spam)."}
        {result && !result.sent && !result.email_enabled && " Email isn't set up on this server yet, so nothing was sent."}
        {resend.isError && " Couldn't send it — try again in a bit."}
      </span>
      <span className="flex gap-3">
        <button className="font-semibold text-amber-800 underline-offset-2 hover:underline" disabled={refresh.isPending} onClick={() => refresh.mutate()}>
          I've done it
        </button>
        <button className="font-semibold text-amber-800 underline-offset-2 hover:underline disabled:opacity-50" disabled={resend.isPending} onClick={() => resend.mutate()}>
          {resend.isPending ? "Sending…" : "Send it again"}
        </button>
      </span>
    </div>
  );
}
