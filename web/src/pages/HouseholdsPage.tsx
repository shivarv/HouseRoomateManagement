import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { householdsApi } from "../api/households";
import { Button, Card, ErrorText, Input, Loading, PageTitle } from "../components/ui";
import { useAcceptInvite, useHouseholds } from "../features/households/hooks";
import { lastHousehold } from "../lib/lastHousehold";

/** /households: with a house, My day is home; with none, set one up. */
export function HouseholdsPage() {
  const households = useHouseholds();
  if (households.isLoading) return <Loading />;
  if ((households.data?.length ?? 0) > 0) return <Navigate to="/" replace />;
  return <AddHouseholdPage />;
}

/** Create a new house (the guided setup) or join one with an invite code (/households/new, or when I have none). */
export function AddHouseholdPage() {
  const households = useHouseholds();
  const hasHouses = (households.data?.length ?? 0) > 0;
  return (
    <>
      <PageTitle
        title={hasHouses ? "Add a household" : "Households"}
        subtitle={hasHouses ? "Start another house, or join one with an invite code." : "You're not in a household yet. Create one, or join with an invite code."}
      />
      <ErrorText error={households.error} />
      <div className="grid gap-4 sm:grid-cols-2">
        {/* Creating always goes through the guided setup, so every new house starts complete. */}
        <Link
          to="/households/new/setup"
          className="card-hover flex flex-col rounded-2xl border border-indigo-200 bg-linear-to-br from-indigo-50 to-fuchsia-50 p-5 shadow-sm ring-1 ring-indigo-100"
        >
          <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-linear-to-br from-indigo-500 to-fuchsia-500 text-2xl text-white shadow-md">✨</span>
          <span className="flex items-center gap-2 font-semibold text-indigo-900">
            Create a new home <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">Recommended</span>
          </span>
          <span className="mt-1 text-sm text-slate-600">
            A few quick steps: your roommates, chores, groceries and bills, prefilled from a template. You'll be its admin.
          </span>
          <span className="mt-4 inline-flex w-fit items-center gap-1 rounded-xl bg-linear-to-r from-indigo-500 to-fuchsia-500 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-indigo-500/30">
            Start setup →
          </span>
        </Link>
        <JoinHousehold />
      </div>
    </>
  );
}

function JoinHousehold() {
  const navigate = useNavigate();
  const [code, setCode] = useState("");
  const preview = useMutation({ mutationFn: () => householdsApi.previewInvite(code.trim()) });
  const accept = useAcceptInvite();

  const join = (memberId: string | null) =>
    accept.mutate({ code: code.trim(), memberId }, { onSuccess: (h) => (lastHousehold.set(h.id), navigate("/")) });

  return (
    <Card>
      <h2 className="mb-1 font-semibold">Join with an invite code</h2>
      <p className="mb-4 text-sm text-slate-500">Ask your house admin for the 8-character code.</p>
      {!preview.data ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            preview.mutate();
          }}
          className="space-y-3"
        >
          <Input label="Invite code" placeholder="ABCD2345" value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} required />
          <ErrorText error={preview.error} />
          <Button type="submit" variant="secondary" disabled={preview.isPending}>Find household</Button>
        </form>
      ) : (
        <div className="space-y-3">
          <p className="text-sm">
            Joining <span className="font-semibold">{preview.data.household_name}</span>. Which one is you?
          </p>
          <div className="flex flex-wrap gap-2">
            {preview.data.unclaimed_members.map((m) => (
              <Button key={m.id} variant="secondary" disabled={accept.isPending} onClick={() => join(m.id)}>
                I'm {m.display_name}
              </Button>
            ))}
            <Button variant="ghost" disabled={accept.isPending} onClick={() => join(null)}>
              I'm not listed — add me
            </Button>
          </div>
          <ErrorText error={accept.error} />
          <button className="text-xs text-slate-500 hover:underline" onClick={() => preview.reset()}>Use a different code</button>
        </div>
      )}
    </Card>
  );
}
