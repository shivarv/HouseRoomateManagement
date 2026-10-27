import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { authApi } from "../api/auth";
import { Button, Card, ErrorText, Input, PageTitle } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";

/** Deleting my account, for good, after a confirmation that says what happens to my homes. */
function DeleteAccount() {
  const { signOut } = useAuth();
  const remove = useMutation({ mutationFn: authApi.deleteAccount, onSuccess: signOut });
  const ask = () =>
    confirm(
      "Delete your account? This can't be undone.\n\n" +
        "Homes where you're the only one are deleted. In shared homes your past turns and payments stay under your name, " +
        "and if you're the only admin, the roommate who joined first becomes admin.",
    ) && remove.mutate();

  return (
    <Card className="max-w-lg space-y-2">
      <h2 className="font-semibold text-red-700">Delete account</h2>
      <p className="text-sm text-slate-600">Removes your account and email for good.</p>
      <ErrorText error={remove.error} />
      <Button variant="danger" disabled={remove.isPending} onClick={ask}>
        {remove.isPending ? "Deleting…" : "Delete account"}
      </Button>
    </Card>
  );
}

/** My name (first, and last if I want one) and email. */
export function ProfilePage() {
  const { user, updateUser } = useAuth();
  const queryClient = useQueryClient();
  const [first, setFirst] = useState(user?.first_name ?? "");
  const [last, setLast] = useState(user?.last_name ?? "");
  const [phone, setPhone] = useState(user?.phone ?? "");
  const [email, setEmail] = useState("");  // only for accounts without one yet
  const save = useMutation({
    mutationFn: () =>
      authApi.updateProfile(first.trim(), last.trim(), {
        phone: phone.trim(),
        ...(user?.email == null && email.trim() ? { email: email.trim() } : {}),
      }),
    onSuccess: (u) => {
      updateUser(u);
      queryClient.invalidateQueries(); // houses that use my name pick up the change
    },
  });
  if (!user) return null;
  const changed =
    first.trim() !== user.first_name || last.trim() !== user.last_name || phone.trim() !== (user.phone ?? "") || !!email.trim();
  // Always a first or last name, and an email or phone.
  const valid = (first.trim() || last.trim()) && (user.email || email.trim() || phone.trim());

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (valid && changed) save.mutate();
  };

  return (
    <>
      <PageTitle title="Your profile" subtitle="How you show up in your homes. A first or last name is enough." />
      <Card className="max-w-lg">
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Input label="First name" value={first} maxLength={50} onChange={(e) => setFirst(e.target.value)} autoComplete="given-name" />
            <Input label="Last name" value={last} maxLength={50} onChange={(e) => setLast(e.target.value)} autoComplete="family-name" />
          </div>
          {user.email ? (
            <>
              <Input label="Email" value={user.email} disabled />
              <p className={`text-xs font-medium ${user.email_verified ? "text-emerald-600" : "text-amber-700"}`}>
                {user.email_verified ? "✓ Email confirmed" : "Email not confirmed yet"}
              </p>
            </>
          ) : (
            <Input label="Email (optional)" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          )}
          <Input label={user.email ? "Phone (optional)" : "Phone"} type="tel" value={phone} maxLength={32} onChange={(e) => setPhone(e.target.value)} placeholder="+1 617 555 0100" autoComplete="tel" />
          <p className="text-xs text-slate-500">
            Homes that call you by your full name update with it; if a home renamed you (e.g. a nickname), that stays.
          </p>
          <ErrorText error={save.error} />
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={!valid || !changed || save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
            {save.isSuccess && !changed && <span className="text-sm text-emerald-600">Saved</span>}
          </div>
        </form>
      </Card>
      <p className="mt-6 max-w-lg text-sm text-slate-500">
        <Link className="font-medium text-indigo-700 hover:underline" to="/support">Help &amp; support</Link>
        {" · "}
        <Link className="font-medium text-indigo-700 hover:underline" to="/privacy">Privacy policy</Link>
      </p>
      <div className="mt-6">
        <DeleteAccount />
      </div>
    </>
  );
}
