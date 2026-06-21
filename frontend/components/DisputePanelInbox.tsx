'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { safeDate } from '@/lib/utils';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface PanelMember {
  uuid: string | null;
  username: string | null;
  role_class: string | null;
  vote: string | null;
}

interface PanelCase {
  case_id: string;
  action_id: number;
  token_id: number;
  kind: string;
  created_at: any;
  my_role_class: string;
  my_vote: string | null;
  panel: PanelMember[];
}

export function DisputePanelInbox({ actorAddress }: { actorAddress: string | null }) {
  const [cases, setCases] = useState<PanelCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState<string | null>(null);

  const reload = async () => {
    if (!actorAddress) return;
    try {
      setLoading(true);
      const r = await fetch(
        `${API}/api/disputes/mine?actor=${encodeURIComponent(actorAddress)}`,
      );
      if (!r.ok) return;
      const d = await r.json();
      setCases(d.cases || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [actorAddress]);

  const submitVote = async (caseItem: PanelCase, vote: 'Upheld' | 'Repudiated') => {
    if (!actorAddress) return;
    setSubmitting(caseItem.case_id);
    try {
      let signature: string | null = null;
      try {
        const finalStatus = vote === 'Upheld' ? 'ResolvedValid' : 'ResolvedInvalid';
        const dr = await fetch(
          `${API}/api/disputes/${caseItem.action_id}/digest`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ final_status: finalStatus }),
          },
        );
        if (dr.ok) {
          const dd = await dr.json();
          signature = dd.digest;
        }
      } catch {}

      const r = await fetch(`${API}/api/disputes/${caseItem.action_id}/vote`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          voter_address: actorAddress,
          vote,
          ...(signature ? { signature } : {}),
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      const d = await r.json();
      if (d.finalised) {
        toast.success(`Panel agreed - ${d.outcome}. Resolved on chain.`);
      } else {
        toast.success('Vote recorded. Waiting for the other panel member.');
      }
      reload();
    } catch (err: any) {
      toast.error(err.message || 'Failed to submit vote');
    } finally {
      setSubmitting(null);
    }
  };

  if (!actorAddress || (!loading && cases.length === 0)) return null;

  return (
    <section className="surface overflow-hidden mb-8">
      <header
        className="px-6 py-4 border-b flex items-baseline justify-between"
        style={{ borderColor: 'var(--border)' }}
      >
        <h2 className="text-base font-semibold tracking-tight">
          Disputes awaiting your vote
        </h2>
        <span className="meta">{cases.length}</span>
      </header>

      {loading ? (
        <div className="px-6 py-8 meta">Loading…</div>
      ) : (
        <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
          {cases.map((c) => {
            const otherMember = c.panel.find(
              (m) => m.uuid && m.role_class && m.role_class !== c.my_role_class,
            );
            return (
              <li key={c.case_id} className="px-6 py-4">
                <div className="flex items-baseline justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <p className="text-[14px] font-medium">
                      Action #{c.action_id} on token #{c.token_id}{' '}
                      <span className="meta">
                        ({c.kind === 'envelope' ? 'envelope claim' : 'identity binding'})
                      </span>
                    </p>
                    <p
                      className="text-[12.5px] mt-1"
                      style={{ color: 'var(--fg-subtle)' }}
                    >
                      Drawn {safeDate(c.created_at, 'datetime')} · Your role on the panel:{' '}
                      <span className="font-medium">{c.my_role_class}</span>
                    </p>
                    {otherMember && (
                      <p
                        className="text-[12.5px] mt-0.5"
                        style={{ color: 'var(--fg-faint)' }}
                      >
                        Other panel member ({otherMember.role_class}):{' '}
                        {otherMember.vote ? (
                          <>has voted <strong>{otherMember.vote}</strong></>
                        ) : (
                          <>has not voted yet</>
                        )}
                      </p>
                    )}
                  </div>
                  <Link
                    href={`/model/${c.token_id}`}
                    className="link-muted text-[13px] shrink-0"
                  >
                    View card
                  </Link>
                </div>

                {c.my_vote ? (
                  <p
                    className="mt-3 text-[12.5px]"
                    style={{ color: 'var(--ok,#15803d)' }}
                  >
                    You voted <strong>{c.my_vote}</strong>. Waiting for finalisation.
                  </p>
                ) : (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={() => submitVote(c, 'Upheld')}
                      disabled={submitting === c.case_id}
                      className="btn btn-primary btn-sm"
                    >
                      {submitting === c.case_id ? 'Submitting…' : 'Uphold'}
                    </button>
                    <button
                      onClick={() => submitVote(c, 'Repudiated')}
                      disabled={submitting === c.case_id}
                      className="btn btn-danger btn-sm"
                    >
                      Vote Repudiate
                    </button>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
