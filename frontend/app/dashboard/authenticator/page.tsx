'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';
import { ClaimStatusCard, ActionList, type ClaimStatus, type ActionRecord } from '@/components/Governance';
import { DisputePanelInbox } from '@/components/DisputePanelInbox';
import { safeDate } from '@/lib/utils';

interface PendingCard {
  token_id: number;
  model_name: string;
  organization: string;
  version: string;
  created_at: string;
  creator_address: string;
}

interface MyAction {
  token_id: number;
  model_name: string;
  current_status: string;
  last_action: string;
  action_timestamp: string;
}

interface DashboardStats {
  pending_count: number;
  total_in_evaluation: number;
  total_validated: number;
  total_rejected: number;
  actions_count: number;
}

type ActionType = 'validate' | 'reject' | 'request-revision';

export default function AuthenticatorDashboard() {
  const router = useRouter();
  const { isAuthenticated, role, getWalletAddress, isLoading: authLoading } = useAuth();

  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [pending, setPending] = useState<PendingCard[]>([]);
  const [myActions, setMyActions] = useState<MyAction[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [reasonInputs, setReasonInputs] = useState<Record<number, string>>({});
  const [claim, setClaim] = useState<ClaimStatus | null>(null);
  const [challenges, setChallenges] = useState<ActionRecord[]>([]);
  const [canAct, setCanAct] = useState<Record<number, { ok: boolean; reason?: string }>>({});

  useEffect(() => {
    if (!authLoading && (!isAuthenticated || (role !== 'Reviewer' && role !== 'Authenticator'))) {
      router.push('/auth');
    }
  }, [isAuthenticated, role, authLoading, router]);

  useEffect(() => {
    if (isAuthenticated && (role === 'Reviewer' || role === 'Authenticator')) fetchDashboard();
  }, [isAuthenticated, role]);

  const fetchDashboard = async () => {
    setLoading(true);
    try {
      const wallet = getWalletAddress();
      const url = wallet
        ? `http://localhost:8000/api/dashboard/authenticator?authenticator_address=${wallet}`
        : 'http://localhost:8000/api/dashboard/authenticator';
      const res = await fetch(url);
      if (!res.ok) {
        toast.error('Failed to load dashboard');
        return;
      }
      const data = await res.json();
      setPending(data.pending_validation || []);
      setMyActions(data.my_actions || []);
      setStats(data.stats || null);

      // Pre-fetch can-act for every pending card to enforce separation-of-duties.
      if (wallet && (data.pending_validation || []).length) {
        const entries = await Promise.all(
          (data.pending_validation as PendingCard[]).map(async (c) => {
            try {
              const r = await fetch(
                `http://localhost:8000/api/model-cards/${c.token_id}/can-act?actor=${encodeURIComponent(wallet)}`
              );
              if (!r.ok) {
                console.warn(`can-act fetch failed for token ${c.token_id}: HTTP ${r.status}`);
                return [c.token_id, { ok: false, reason: 'Permission check failed.' }] as const;
              }
              const d = await r.json();
              return [c.token_id, {
                ok: !!(d.can?.validate && d.can?.reject && d.can?.request_revision),
                reason: d.reason_if_blocked || undefined,
              }] as const;
            } catch (err) {
              console.warn(`can-act fetch error for token ${c.token_id}:`, err);
              return [c.token_id, { ok: false, reason: 'Permission check failed.' }] as const;
            }
          })
        );
        setCanAct(Object.fromEntries(entries));
      } else {
        setCanAct({});
      }

      if (wallet) {
        try {
          const cr = await fetch(`http://localhost:8000/api/identity/claim/${wallet}?claim_type=2`);
          if (cr.ok) setClaim(await cr.json());
        } catch (_) {}
        try {
          const dr = await fetch(`http://localhost:8000/api/identity/actions/by-actor/${wallet}`);
          if (dr.ok) {
            const dd = await dr.json();
            const flagged = (dd.actions || []).filter((a: ActionRecord) =>
              a.identity_status === 'Disputed' || a.identity_status === 'ResolvedInvalid'
            );
            setChallenges(flagged);
          }
        } catch (_) {}
      }
    } catch (e) {
      console.error('Dashboard fetch error:', e);
      toast.error('Failed to connect to server');
    } finally {
      setLoading(false);
    }
  };

  const performAction = async (tokenId: number, action: ActionType) => {
    const wallet = getWalletAddress();
    if (!wallet) {
      toast.error('Wallet address not found');
      return;
    }
    const needsReason = action === 'reject' || action === 'request-revision';
    const reason = reasonInputs[tokenId]?.trim();
    if (needsReason && !reason) {
      toast.error(action === 'reject' ? 'Provide a rejection reason' : 'Provide revision feedback');
      return;
    }
    setActionLoading(tokenId);
    try {
      const body: Record<string, unknown> = { token_id: tokenId };
      if (action === 'validate') {
        body.validator_address = wallet;
        body.validation_notes = reason || '';
      } else if (action === 'reject') {
        body.rejector_address = wallet;
        body.reason = reason;
      } else {
        body.requester_address = wallet;
        body.feedback = reason;
      }
      const res = await fetch(`http://localhost:8000/api/model-cards/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || `Failed to ${action} card`);
        return;
      }
      toast.success(`Card #${tokenId}: ${action.replace('-', ' ')}`);
      setReasonInputs((prev) => {
        const next = { ...prev };
        delete next[tokenId];
        return next;
      });
      await fetchDashboard();
    } catch (e) {
      console.error(`${action} error:`, e);
      toast.error('Network error');
    } finally {
      setActionLoading(null);
    }
  };

  if (authLoading || loading) {
    return (
      <main className="container-app py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-10 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="surface h-20" />
          ))}
        </div>
      </main>
    );
  }

  return (
    <main className="container-app py-10 lg:py-14">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between mb-10">
        <div>
          <p className="meta mb-3">Authenticator</p>
          <h1 className="text-3xl lg:text-4xl font-semibold tracking-tight">Review</h1>
        </div>
        <button onClick={fetchDashboard} className="btn btn-secondary">
          Refresh
        </button>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-10">
          <Stat label="Pending review" value={stats.pending_count} accent={stats.pending_count > 0} />
          <Stat label="In evaluation" value={stats.total_in_evaluation} />
          <Stat label="Endorsed" value={stats.total_validated} tone="ok" />
          <Stat label="Rejected" value={stats.total_rejected} tone="danger" />
        </div>
      )}

      <div className="mb-10">
        <ClaimStatusCard claim={claim} />
      </div>

      <DisputePanelInbox actorAddress={getWalletAddress() || null} />

      {challenges.length > 0 && (
        <section className="surface overflow-hidden mb-10" style={{ borderColor: 'var(--warn)' }}>
          <header className="px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
            <h2 className="text-base font-semibold tracking-tight" style={{ color: 'var(--warn)' }}>
              Challenges to your actions
            </h2>
            <p className="meta mt-1">
              {challenges.length} action{challenges.length === 1 ? '' : 's'}
              {challenges.some(c => c.identity_status === 'ResolvedInvalid') ? ' invalidated' : ' under review'}
            </p>
          </header>
          <div className="px-6 py-4">
            <ActionList actions={challenges} showToken />
          </div>
        </section>
      )}

      <section className="surface overflow-hidden mb-10">
        <header className="flex items-baseline justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <h2 className="text-base font-semibold tracking-tight">Cards pending review</h2>
          <span className="meta">{pending.length} card{pending.length !== 1 ? 's' : ''}</span>
        </header>

        {pending.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <h3 className="text-lg font-semibold tracking-tight">No model cards in evaluation.</h3>
            <p className="mt-2 text-[14px]" style={{ color: 'var(--fg-muted)' }}>
              No cards awaiting review.
            </p>
          </div>
        ) : (
          <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {pending.map((card) => (
              <li key={card.token_id} className="px-6 py-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-2">
                      <span className="mono" style={{ color: 'var(--fg-faint)' }}>
                        #{card.token_id}
                      </span>
                      <span className="text-[15px] font-medium truncate">
                        {card.model_name}
                      </span>
                      <span className="mono text-[12px]" style={{ color: 'var(--fg-subtle)' }}>
                        v{card.version}
                      </span>
                    </div>
                    <p className="mt-1 text-[13px]" style={{ color: 'var(--fg-subtle)' }}>
                      {card.organization} · created {safeDate(card.created_at)}
                    </p>
                  </div>
                  <Link href={`/model/${card.token_id}`} className="link-muted text-[13px] shrink-0">
                    Open card
                  </Link>
                </div>

                {(() => {
                  const ca = canAct[card.token_id];
                  const isChecking = ca === undefined;
                  const isBlocked = ca?.ok === false;
                  const isAllowed = ca?.ok === true;
                  return (
                    <>
                      <input
                        type="text"
                        value={reasonInputs[card.token_id] || ''}
                        onChange={(e) =>
                          setReasonInputs((prev) => ({ ...prev, [card.token_id]: e.target.value }))
                        }
                        placeholder="Notes (required to reject or request revision)"
                        className="input mt-4"
                        disabled={!isAllowed}
                      />

                      {isChecking && (
                        <p className="mt-3 text-[12.5px]" style={{ color: 'var(--fg-faint)' }}>
                          Checking permissions…
                        </p>
                      )}

                      {isBlocked && (
                        <p className="mt-3 text-[12.5px]" style={{ color: 'var(--warn,#b45309)' }}>
                          {ca?.reason || "Conflict of interest - you can't act on this card."}
                        </p>
                      )}

                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          onClick={() => performAction(card.token_id, 'validate')}
                          disabled={actionLoading === card.token_id || !isAllowed}
                          className="btn btn-primary btn-sm"
                          title={ca?.reason || ''}
                        >
                          {actionLoading === card.token_id ? 'Working...' : 'Endorse'}
                        </button>
                        <button
                          onClick={() => performAction(card.token_id, 'request-revision')}
                          disabled={actionLoading === card.token_id || !isAllowed}
                          className="btn btn-secondary btn-sm"
                          title={ca?.reason || ''}
                        >
                          Request revision
                        </button>
                        <button
                          onClick={() => performAction(card.token_id, 'reject')}
                          disabled={actionLoading === card.token_id || !isAllowed}
                          className="btn btn-danger btn-sm"
                          title={ca?.reason || ''}
                        >
                          Reject
                        </button>
                      </div>
                    </>
                  );
                })()}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="surface overflow-hidden">
        <header className="flex items-baseline justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <h2 className="text-base font-semibold tracking-tight">Recent actions</h2>
          <span className="meta">{myActions.length}</span>
        </header>
        {myActions.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="meta mb-2">Nothing yet</p>
            <p className="text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>
              No review actions yet.
            </p>
          </div>
        ) : (
          <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {myActions.map((a) => (
              <li
                key={`${a.token_id}-${a.action_timestamp}`}
                className="px-6 py-3 flex items-center justify-between gap-4"
              >
                <div className="flex items-baseline gap-3 min-w-0">
                  <span className="mono" style={{ color: 'var(--fg-faint)' }}>
                    #{a.token_id}
                  </span>
                  <span className="text-[14px] font-medium truncate">{a.model_name}</span>
                  <span className="meta">
                    {a.last_action} to {a.current_status}
                  </span>
                </div>
                <Link href={`/model/${a.token_id}`} className="link-muted text-[12.5px]">
                  {safeDate(a.action_timestamp)}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function Stat({
  label,
  value,
  accent,
  tone,
}: {
  label: string;
  value: number;
  accent?: boolean;
  tone?: 'ok' | 'danger';
}) {
  const color = tone === 'ok' ? 'var(--ok)' : tone === 'danger' ? 'var(--danger)' : accent ? 'var(--warn)' : 'var(--fg)';
  return (
    <div
      className="surface p-4"
      style={{ borderColor: accent ? 'var(--warn)' : 'var(--border)' }}
    >
      <p className="text-2xl font-semibold tabular-nums" style={{ color }}>
        {value}
      </p>
      <p className="meta mt-1">{label}</p>
    </div>
  );
}
