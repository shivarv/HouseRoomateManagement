import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { householdsApi } from "../api/households";
import { Badge, Button, Card, Empty, ErrorText, Input, Loading, PageTitle } from "../components/ui";
import { useAcceptInvite, useCreateHousehold, useHouseholds } from "../features/households/hooks";
import { browserTimezone } from "../lib/format";

export function HouseholdsPage() {
  const households = useHouseholds();
  return (
    <>
      <PageTitle title="Households" subtitle="The houses you share. Create one, or join with an invite code." />
      {households.isLoading ? (
        <Loading />
      ) : households.data?.length ? (
        <div className="mb-8 grid gap-3 sm:grid-cols-2">
          {households.data.map((h) => (
            <Link key={h.id} to={`/households/${h.id}`} className="card-hover rounded-2xl border border-white/70 bg-white/90 p-5 shadow-sm ring-1 ring-slate-900/5 hover:ring-indigo-200">
              <div className="flex items-center justify-between">
                <span className="font-medium">{h.name}</span>
                {h.my_role === "admin" && <Badge tone="indigo">Admin</Badge>}
              </div>
              <p className="mt-1 text-xs text-slate-500">{h.timezone}</p>
            </Link>
          ))}
        </div>
      ) : (
        <div className="mb-8">
          <Empty>No households yet.</Empty>
        </div>
      )}
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
    create.mutate({ name, timezone }, { onSuccess: (h) => navigate(`/households/${h.id}/people`) });
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
    accept.mutate({ code: code.trim(), memberId }, { onSuccess: (h) => navigate(`/households/${h.id}`) });

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
