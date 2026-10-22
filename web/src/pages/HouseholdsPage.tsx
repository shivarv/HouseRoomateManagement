import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router";
import { householdsApi } from "../api/households";
import { Button, Card, ErrorText, Input, Loading, PageTitle } from "../components/ui";
import { useAcceptInvite, useCreateHousehold, useHouseholds } from "../features/households/hooks";
import { browserTimezone } from "../lib/format";
import { lastHousehold } from "../lib/lastHousehold";

/** /households: with a house, My day is home; with none, set one up. */
export function HouseholdsPage() {
  const households = useHouseholds();
  if (households.isLoading) return <Loading />;
  if ((households.data?.length ?? 0) > 0) return <Navigate to="/" replace />;
  return <AddHouseholdPage />;
}

/** Create a new house or join one with an invite code (/households/new, or when I have none). */
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
        <CreateHousehold />
        <JoinHousehold />
      </div>
    </>
  );
}

function CreateHousehold() {
  const navigate = useNavigate();
  const create = useCreateHousehold();
  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState(browserTimezone());

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate({ name, timezone }, { onSuccess: (h) => (lastHousehold.set(h.id), navigate("/")) });
  };

  return (
    <Card>
      <h2 className="mb-1 font-semibold">Create a household</h2>
      <p className="mb-4 text-sm text-slate-500">Comes with Cooking, Clean hall and Dispose garbage.</p>
      <form onSubmit={onSubmit} className="space-y-3">
        <Input label="Name" placeholder="e.g. Maple Street House" value={name} onChange={(e) => setName(e.target.value)} required />
        <Input label="Timezone" value={timezone} onChange={(e) => setTimezone(e.target.value)} required />
        <ErrorText error={create.error} />
        <Button type="submit" disabled={create.isPending}>Create</Button>
      </form>
    </Card>
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
