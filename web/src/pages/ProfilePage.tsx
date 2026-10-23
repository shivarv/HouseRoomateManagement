import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { authApi } from "../api/auth";
import { Button, Card, ErrorText, Input, PageTitle } from "../components/ui";
import { useAuth } from "../features/auth/AuthContext";

/** My name (first, and last if I want one) and email. */
export function ProfilePage() {
  const { user, updateUser } = useAuth();
  const queryClient = useQueryClient();
  const [first, setFirst] = useState(user?.first_name ?? "");
  const [last, setLast] = useState(user?.last_name ?? "");
  const save = useMutation({
    mutationFn: () => authApi.updateProfile(first.trim(), last.trim()),
    onSuccess: (u) => {
      updateUser(u);
      queryClient.invalidateQueries(); // houses that use my name pick up the change
    },
  });
  if (!user) return null;
  const changed = first.trim() !== user.first_name || last.trim() !== user.last_name;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (first.trim() && changed) save.mutate();
  };

  return (
    <>
      <PageTitle title="Your profile" subtitle="How you show up in your homes. The last name is optional." />
      <Card className="max-w-lg">
        <form onSubmit={submit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <Input label="First name" value={first} maxLength={50} required onChange={(e) => setFirst(e.target.value)} autoComplete="given-name" />
            <Input label="Last name (optional)" value={last} maxLength={50} onChange={(e) => setLast(e.target.value)} autoComplete="family-name" />
          </div>
          <Input label="Email" value={user.email} disabled />
          <p className="text-xs text-slate-500">
            Homes that call you by your full name update with it; if a home renamed you (e.g. a nickname), that stays.
          </p>
          <ErrorText error={save.error} />
          <div className="flex items-center gap-3">
            <Button type="submit" disabled={!first.trim() || !changed || save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
            {save.isSuccess && !changed && <span className="text-sm text-emerald-600">Saved</span>}
          </div>
        </form>
      </Card>
    </>
  );
}
