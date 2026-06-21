'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';
import { ClaimStatusCard, ActionList, type ClaimStatus, type ActionRecord } from '@/components/Governance';
import { DisputePanelInbox } from '@/components/DisputePanelInbox';
import { safeDate } from '@/lib/utils';

interface ReadyCard {
  token_id: number;
  model_name: string;
  organization: string;
  version: string;
  created_at: string;
}

interface PublishedCard {
  token_id: number;
  model_name: string;
  organization: string;
  version: string;
  created_at: string;
}

interface MyAction {
  token_id: number;
  model_name: string;
  current_status: string;
  last_action: string;
  action_timestamp: string;
}

interface DashboardStats {
  ready_count: number;
  published_count: number;
  total_deprecated: number;
  actions_count: number;
}

export default function PublisherDashboard() {
  const router = useRouter();
  const { isAuthenticated, role, getWalletAddress, isLoading: authLoading } = useAuth();

  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [readyCards, setReadyCards] = useState<ReadyCard[]>([]);
  const [publishedCards, setPublishedCards] = useState<PublishedCard[]>([]);
  const [myActions, setMyActions] = useState<MyAction[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [claim, setClaim] = useState<ClaimStatus | null>(null);
  const [challenges, setChallenges] = useState<ActionRecord[]>([]);
  const [canAct, setCanAct] = useState<Record<number, { ok: boolean; reason?: string }>>({});

  useEffect(() => {
    if (!authLoading && (!isAuthenticated || role !== 'Publisher')) {
      router.push('/auth');
    }
  }, [isAuthenticated, role, authLoading, router]);

  useEffect(() => {
    if (isAuthenticated && role === 'Publisher') fetchDashboardData();
  }, [isAuthenticated, role]);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      const wallet = getWalletAddress();
      const url = wallet
        ? `http://localhost:8000/api/dashboard/publisher?publisher_address=${wallet}`
        : 'http://localhost:8000/api/dashboard/publisher';
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setReadyCards(data.ready_to_publish || []);
        setPublishedCards(data.published_cards || []);
        setMyActions(data.my_actions || []);
        setStats(data.stats || null);

        // A publisher cannot publish a card they created or validated.
        if (wallet && (data.ready_to_publish || []).length) {
          const entries = await Promise.all(
            (data.ready_to_publish as ReadyCard[]).map(async (c) => {
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
                  ok: !!d.can?.publish,
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
      } else {
        toast.error('Failed to load dashboard');
      }

      if (wallet) {
        try {
          const cr = await fetch(`http://localhost:8000/api/identity/claim/${wallet}?claim_type=3`);
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

  const handlePublish = async (tokenId: number) => {
    const wallet = getWalletAddress();
    if (!wallet) {
      toast.error('Wallet address not found');
      return;
    }
    setActionLoading(tokenId);
    try {
      const res = await fetch('http://localhost:8000/api/model-cards/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token_id: tokenId, publisher_address: wallet }),
      });
      if (res.ok) {
        toast.success(`Card #${tokenId} published`);
        fetchDashboardData();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Publication failed');
      }
    } catch (e) {
      toast.error('Failed to publish');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDeprecate = async (tokenId: number) => {
    const wallet = getWalletAddress();
    if (!wallet) {
      toast.error('Wallet address not found');
      return;
    }
    const reason = prompt('Enter deprecation reason:');
    if (!reason) return;
    setActionLoading(tokenId);
    try {
      const res = await fetch('http://localhost:8000/api/model-cards/deprecate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token_id: tokenId, deprecator_address: wallet, reason }),
      });
      if (res.ok) {
        toast.success(`Card #${tokenId} deprecated`);
        fetchDashboardData();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Deprecation failed');
      }
    } catch (e) {
      toast.error('Failed to deprecate');
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
          <p className="meta mb-3">Publisher</p>
          <h1 className="text-3xl lg:text-4xl font-semibold tracking-tight">Publish</h1>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchDashboardData} className="btn btn-secondary">
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-10">
        <Stat label="Ready to publish" value={stats?.ready_count || 0} accent={(stats?.ready_count || 0) > 0} />
        <Stat label="Published" value={stats?.published_count || 0} />
        <Stat label="Archived" value={stats?.total_deprecated || 0} />
        <Stat label="My actions" value={stats?.actions_count || 0} />
      </div>

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

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-10">
        <Section title="Ready to publish" count={readyCards.length}>
          {readyCards.length === 0 ? (
           <Empty title="No cards to publish" />
          ) : (
            <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {readyCards.map((card) => (
                <li key={card.token_id} className="px-6 py-4 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-2">
                      <span className="mono" style={{ color: 'var(--fg-faint)' }}>
                        #{card.token_id}
                      </span>
                      <span className="text-[14.5px] font-medium truncate">
                        {card.model_name || 'Untitled card'}
                      </span>
                    </div>
                    <p className="text-[12.5px] mt-1 truncate" style={{ color: 'var(--fg-subtle)' }}>
                      {card.organization} · <span className="mono">v{card.version}</span>
                    </p>
                  </div>
                  {(() => {
                    const ca = canAct[card.token_id];
                    const isChecking = ca === undefined;
                    const isBlocked = ca?.ok === false;
                    const isAllowed = ca?.ok === true;
                    return (
                      <>
                        <div className="flex items-center gap-2 shrink-0">
                          <Link href={`/model/${card.token_id}`} className="link-muted text-[13px]">
                            View
                          </Link>
                          <button
                            onClick={() => handlePublish(card.token_id)}
                            disabled={actionLoading === card.token_id || !isAllowed}
                            className="btn btn-primary btn-sm"
                            title={ca?.reason || ''}
                          >
                            {actionLoading === card.token_id ? 'Publishing...' : 'Publish'}
                          </button>
                        </div>
                        {isChecking && (
                          <p className="basis-full mt-1 text-[12px]" style={{ color: 'var(--fg-faint)' }}>
                            Checking permissions…
                          </p>
                        )}
                        {isBlocked && (
                          <p className="basis-full mt-1 text-[12px]" style={{ color: 'var(--warn,#b45309)' }}>
                            {ca?.reason}
                          </p>
                        )}
                      </>
                    );
                  })()}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Published" count={publishedCards.length}>
          {publishedCards.length === 0 ? (
            <Empty title="No published cards" />
          ) : (
            <ul className="divide-y max-h-[480px] overflow-auto" style={{ borderColor: 'var(--border)' }}>
              {publishedCards.map((card) => (
                <li key={card.token_id} className="px-6 py-4 flex items-center justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-baseline gap-2">
                      <span className="mono" style={{ color: 'var(--fg-faint)' }}>
                        #{card.token_id}
                      </span>
                      <span className="text-[14.5px] font-medium truncate">
                        {card.model_name || 'Untitled card'}
                      </span>
                      <span className="pill pill-ok">Published</span>
                    </div>
                    <p className="text-[12.5px] mt-1 truncate" style={{ color: 'var(--fg-subtle)' }}>
                      {card.organization} · <span className="mono">v{card.version}</span>
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Link href={`/model/${card.token_id}`} className="link-muted text-[13px]">
                      View
                    </Link>
                    <button
                      onClick={() => handleDeprecate(card.token_id)}
                      disabled={actionLoading === card.token_id}
                      className="btn btn-danger btn-sm"
                    >
                      Archive
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>

      <Section title="Recent actions" count={myActions.length}>
        {myActions.length === 0 ? (
          <Empty title="No actions" />
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
                  <span className="text-[14px] font-medium truncate">
                    {a.model_name || 'Untitled card'}
                  </span>
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
      </Section>
    </main>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div
      className="surface p-4"
      style={{ borderColor: accent ? 'var(--warn)' : 'var(--border)' }}
    >
      <p
        className="text-2xl font-semibold tabular-nums"
        style={{ color: accent ? 'var(--warn)' : 'var(--fg)' }}
      >
        {value}
      </p>
      <p className="meta mt-1">{label}</p>
    </div>
  );
}

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <section className="surface overflow-hidden">
      <header
        className="flex items-baseline justify-between px-6 py-4 border-b"
        style={{ borderColor: 'var(--border)' }}
      >
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        <span className="meta">{count}</span>
      </header>
      {children}
    </section>
  );
}

function Empty({ title, body }: { title: string; body?: string }) {
  return (
    <div className="px-6 py-12 text-center">
      <h3 className="text-base font-semibold tracking-tight">{title}</h3>
      {body && (
        <p className="mt-2 text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>
          {body}
        </p>
      )}
    </div>
  );
}
