'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface DisputeCase {
  case_id: string;
  action_id: number;
  token_id: number;
  kind: string;
  status: string;
  outcome: string | null;
  challenger_uuid: string | null;
  panel: Array<{
    uuid: string | null;
    username: string | null;
    role_class: string | null;
    vote: string | null;
  }>;
  created_at: any;
}

interface Candidate {
  uuid: string;
  username: string | null;
  eoa: string;
}

interface Candidates {
  reviewers: Candidate[];
  publishers: Candidate[];
  note: string;
}

interface Props {
  getAuthHeaders: () => HeadersInit;
}

export function AssignPanelTab({ getAuthHeaders }: Props) {
  const [loading, setLoading] = useState(true);
  const [cases, setCases] = useState<DisputeCase[]>([]);
  const [candidatesByAction, setCandidatesByAction] = useState<Record<number, Candidates>>({});
  const [reviewerPick, setReviewerPick] = useState<Record<number, string>>({});
  const [publisherPick, setPublisherPick] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/governance/dispute-cases?status=open`, {
        headers: getAuthHeaders(),
      });
      if (!r.ok) {
        if (r.status === 401 || r.status === 403) toast.error('Admin authorization required');
        else toast.error('Failed to load dispute cases');
        return;
      }
      const d = await r.json();
      const all: DisputeCase[] = d.cases || [];
      const needs = all.filter((c) => {
        const real = (c.panel || []).filter((m) => m.uuid);
        return real.length < 2;
      });
      setCases(needs);

      const pools: Record<number, Candidates> = {};
      await Promise.all(
        needs.map(async (c) => {
          try {
            const cr = await fetch(`${API}/api/disputes/${c.action_id}/candidates`, {
              headers: getAuthHeaders(),
            });
            if (cr.ok) {
              pools[c.action_id] = await cr.json();
            }
          } catch {}
        }),
      );
      setCandidatesByAction(pools);
    } catch {
      toast.error('Network error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submitPanel = async (actionId: number) => {
    const reviewer = reviewerPick[actionId];
    const publisher = publisherPick[actionId];
    if (!reviewer || !publisher) {
      toast.error('Pick a Reviewer and a Publisher first');
      return;
    }
    setSubmitting(actionId);
    try {
      const r = await fetch(`${API}/api/disputes/${actionId}/set-panel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          reviewer_uuid: reviewer,
          publisher_uuid: publisher,
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      toast.success(`Panel assigned for action #${actionId}`);
      load();
    } catch (err: any) {
      toast.error(err.message || 'Failed to assign panel');
    } finally {
      setSubmitting(null);
    }
  };

  return (
    <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden">
      <header className="flex items-baseline justify-between px-6 py-4 border-b border-gray-700">
        <div>
          <h2 className="text-base font-semibold text-white">Panel assignment</h2>
          <p className="text-xs text-gray-400 mt-1">
            Open disputes whose panel hasn't been formed yet. Pick one Reviewer
            and one Publisher per case - the contract verifies their signatures
            and decides the outcome. You assign, you don't decide.
          </p>
        </div>
        <button
          onClick={load}
          className="px-3 py-1.5 text-xs rounded border border-gray-700 hover:bg-gray-700 text-gray-300"
        >
          Refresh
        </button>
      </header>

      {loading ? (
        <div className="px-6 py-12 text-center text-gray-400">Loading…</div>
      ) : cases.length === 0 ? (
        <div className="px-6 py-12 text-center">
          <p className="text-gray-400 text-sm">No disputes pending panel assignment.</p>
          <p className="text-gray-500 text-xs mt-1">
            New challenges auto-draw a panel. They only land here when no eligible
            Reviewer or Publisher exists at challenge time.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-gray-700">
          {cases.map((c) => {
            const pool = candidatesByAction[c.action_id];
            const reviewerOpts = pool?.reviewers || [];
            const publisherOpts = pool?.publishers || [];
            const blocked = reviewerOpts.length === 0 || publisherOpts.length === 0;
            return (
              <li key={c.case_id} className="px-6 py-5">
                <div className="flex items-baseline justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-white">
                      Action #{c.action_id} · token #{c.token_id} ·{' '}
                      <span className="text-xs text-gray-400">{c.kind}</span>
                    </p>
                    {(c.panel || []).filter((m) => m.uuid).length > 0 && (
                      <p className="text-xs text-amber-400 mt-1">
                        Partial panel - {(c.panel || []).filter((m) => m.uuid).length}/2 members assigned.
                      </p>
                    )}
                  </div>
                </div>

                {(() => {
                  // A candidate holding both roles must not be selectable in both seats.
                  const pickedReviewer = reviewerPick[c.action_id];
                  const pickedPublisher = publisherPick[c.action_id];
                  const reviewerEoaPicked = reviewerOpts.find((r) => r.uuid === pickedReviewer)?.eoa.toLowerCase();
                  const publisherEoaPicked = publisherOpts.find((p) => p.uuid === pickedPublisher)?.eoa.toLowerCase();

                  const reviewersFiltered = reviewerOpts.filter(
                    (r) =>
                      r.uuid !== pickedPublisher &&
                      (!publisherEoaPicked || r.eoa.toLowerCase() !== publisherEoaPicked),
                  );
                  const publishersFiltered = publisherOpts.filter(
                    (p) =>
                      p.uuid !== pickedReviewer &&
                      (!reviewerEoaPicked || p.eoa.toLowerCase() !== reviewerEoaPicked),
                  );

                  const functionallyBlocked =
                    reviewersFiltered.length === 0 || publishersFiltered.length === 0;

                  if (blocked) {
                    return (
                      <p className="mt-3 text-xs" style={{ color: 'var(--warn,#b45309)' }}>
                        {reviewerOpts.length === 0 && 'No eligible Reviewer with an active institutional claim. '}
                        {publisherOpts.length === 0 && 'No eligible Publisher with an active institutional claim. '}
                        Promote more users via Role Requests + Claim Requests, then refresh.
                      </p>
                    );
                  }
                  if (functionallyBlocked && !pickedReviewer && !pickedPublisher) {
                    const distinctEoas = new Set(
                      [...reviewerOpts, ...publisherOpts].map((u) => u.eoa.toLowerCase()),
                    );
                    if (distinctEoas.size < 2) {
                      return (
                        <p className="mt-3 text-xs" style={{ color: 'var(--warn,#b45309)' }}>
                          This dispute needs two distinct users (one Reviewer, one
                          Publisher), but only {distinctEoas.size} can serve. Promote
                          another user with an active institutional claim.
                        </p>
                      );
                    }
                  }

                  return (
                    <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3">
                      <div>
                        <label className="text-xs text-gray-400 block mb-1">Reviewer</label>
                        <select
                          value={pickedReviewer || ''}
                          onChange={(e) =>
                            setReviewerPick((prev) => ({ ...prev, [c.action_id]: e.target.value }))
                          }
                          className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-white"
                        >
                          <option value="">- select -</option>
                          {reviewersFiltered.map((r) => (
                            <option key={r.uuid} value={r.uuid}>
                              {r.username || r.uuid.slice(0, 8) + '…'} · {r.eoa.slice(0, 6)}…{r.eoa.slice(-4)}
                            </option>
                          ))}
                        </select>
                        {pickedPublisher && reviewersFiltered.length === 0 && reviewerOpts.length > 0 && (
                          <p className="text-[11px] text-amber-400 mt-1">
                            No remaining Reviewer - your Publisher pick is the only candidate, change it to free up a Reviewer.
                          </p>
                        )}
                      </div>
                      <div>
                        <label className="text-xs text-gray-400 block mb-1">Publisher</label>
                        <select
                          value={pickedPublisher || ''}
                          onChange={(e) =>
                            setPublisherPick((prev) => ({ ...prev, [c.action_id]: e.target.value }))
                          }
                          className="w-full bg-gray-900 border border-gray-700 rounded px-2 py-1.5 text-sm text-white"
                        >
                          <option value="">- select -</option>
                          {publishersFiltered.map((p) => (
                            <option key={p.uuid} value={p.uuid}>
                              {p.username || p.uuid.slice(0, 8) + '…'} · {p.eoa.slice(0, 6)}…{p.eoa.slice(-4)}
                            </option>
                          ))}
                        </select>
                        {pickedReviewer && publishersFiltered.length === 0 && publisherOpts.length > 0 && (
                          <p className="text-[11px] text-amber-400 mt-1">
                            No remaining Publisher - your Reviewer pick is the only candidate, change it to free up a Publisher.
                          </p>
                        )}
                      </div>
                      <div className="flex items-end">
                        <button
                          onClick={() => submitPanel(c.action_id)}
                          disabled={
                            submitting === c.action_id ||
                            !pickedReviewer ||
                            !pickedPublisher
                          }
                          className="px-3 py-1.5 text-sm rounded bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50"
                        >
                          {submitting === c.action_id ? 'Assigning…' : 'Assign panel'}
                        </button>
                      </div>
                    </div>
                  );
                })()}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
