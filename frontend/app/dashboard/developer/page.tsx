'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';
import { ClaimStatusCard, ActionList, type ClaimStatus, type ActionRecord } from '@/components/Governance';

interface ModelCard {
  token_id: number;
  model_name: string;
  status: string;
  version: string;
  created_at: string;
  organization: string;
  event_count: number;
  action_needed: string;
}

interface GroupedCards {
  needs_submission: ModelCard[];
  needs_revision: ModelCard[];
  in_progress: ModelCard[];
  live: ModelCard[];
  archived: ModelCard[];
  rejected: ModelCard[];
}

interface DashboardStats {
  total: number;
  needs_attention: number;
  in_progress: number;
  live: number;
  archived: number;
  rejected: number;
}

const STATUS_TONE: Record<string, string> = {
  Created: 'pill-muted',
  InEvaluation: 'pill-warn',
  Validated: 'pill-info',
  Published: 'pill-ok',
  Deprecated: 'pill-muted',
  Rejected: 'pill-danger',
  RevisionRequested: 'pill-warn',
  Revised: 'pill-info',
};

const STATUS_LABEL: Record<string, string> = {
  Created: 'Draft',
  InEvaluation: 'Under Review',
  Validated: 'Reviewed',
  Published: 'Published',
  Deprecated: 'Archived',
  Rejected: 'Declined',
  RevisionRequested: 'Changes Requested',
  Revised: 'Revised',
};

export default function DeveloperDashboard() {
  const router = useRouter();
  const { isAuthenticated, role, getWalletAddress, isLoading: authLoading } = useAuth();

  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [allCards, setAllCards] = useState<ModelCard[]>([]);
  const [grouped, setGrouped] = useState<GroupedCards>({
    needs_submission: [],
    needs_revision: [],
    in_progress: [],
    live: [],
    archived: [],
    rejected: [],
  });
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [activeFilter, setActiveFilter] = useState<string>('all');
  const [claim, setClaim] = useState<ClaimStatus | null>(null);
  const [challenges, setChallenges] = useState<ActionRecord[]>([]);

  useEffect(() => {
    if (!authLoading && (!isAuthenticated || role !== 'AIDeveloper')) {
      router.push('/auth');
    }
  }, [isAuthenticated, role, authLoading, router]);

  useEffect(() => {
    if (isAuthenticated && role === 'AIDeveloper') {
      fetchDashboardData();
    }
  }, [isAuthenticated, role]);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      let walletAddress = getWalletAddress();
      if (!walletAddress) {
        const uuid = localStorage.getItem('uuid');
        if (uuid) {
          try {
            const userInfoRes = await fetch(`http://localhost:8000/api/user/${uuid}`);
            if (userInfoRes.ok) {
              const userInfo = await userInfoRes.json();
              walletAddress = userInfo.eoa_address;
              if (walletAddress) {
                localStorage.setItem(
                  'walletInfo',
                  JSON.stringify({ eoaAddress: walletAddress, smartAccount: null })
                );
              }
            }
          } catch (e) {
            console.error('Failed to fetch user info:', e);
          }
        }
      }
      if (!walletAddress) {
        toast.error('Wallet address not found');
        setLoading(false);
        return;
      }

      const uuid = localStorage.getItem('uuid');
      const url = `http://localhost:8000/api/dashboard/developer?developer_address=${walletAddress}${uuid ? `&uuid=${uuid}` : ''}`;
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setAllCards(data.all_cards || []);
        setGrouped(
          data.grouped || {
            needs_submission: [],
            needs_revision: [],
            in_progress: [],
            live: [],
            archived: [],
            rejected: [],
          }
        );
        setStats(data.stats || null);
      } else {
        toast.error('Failed to load dashboard');
      }

      try {
        const cr = await fetch(`http://localhost:8000/api/identity/claim/${walletAddress}?claim_type=1`);
        if (cr.ok) setClaim(await cr.json());
      } catch (_) {}
      try {
        const dr = await fetch(`http://localhost:8000/api/identity/actions/by-actor/${walletAddress}`);
        if (dr.ok) {
          const dd = await dr.json();
          const flagged = (dd.actions || []).filter((a: ActionRecord) =>
            a.identity_status === 'Disputed' || a.identity_status === 'ResolvedInvalid'
          );
          setChallenges(flagged);
        }
      } catch (_) {}
    } catch (e) {
      console.error('Dashboard fetch error:', e);
      toast.error('Failed to connect to server');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (tokenId: number) => {
    const walletAddress = getWalletAddress();
    if (!walletAddress) {
      toast.error('Wallet address not found');
      return;
    }
    setActionLoading(tokenId);
    try {
      const res = await fetch('http://localhost:8000/api/model-cards/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token_id: tokenId, initiator_address: walletAddress }),
      });
      if (res.ok) {
        toast.success(`Card #${tokenId} submitted for evaluation`);
        fetchDashboardData();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Submission failed');
      }
    } catch (e) {
      toast.error('Failed to submit');
    } finally {
      setActionLoading(null);
    }
  };

  const filtered = (() => {
    switch (activeFilter) {
      case 'attention': return [...grouped.needs_submission, ...grouped.needs_revision];
      case 'in_progress': return grouped.in_progress;
      case 'live': return grouped.live;
      case 'archived': return grouped.archived;
      case 'rejected': return grouped.rejected;
      default: return allCards;
    }
  })();

  if (authLoading || loading) {
    return (
      <main className="container-app py-16">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-10 animate-pulse">
          {Array.from({ length: 6 }).map((_, i) => (
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
          <p className="meta mb-3">Developer</p>
          <h1 className="text-3xl lg:text-4xl font-semibold tracking-tight">Cards</h1>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchDashboardData} className="btn btn-secondary">
            Refresh
          </button>
          <Link href="/workflow" className="btn btn-secondary">
            Workflow
          </Link>
          <Link href="/create" className="btn btn-primary">
            New card
          </Link>
        </div>
      </div>

      <FilterRow
        items={[
          { key: 'all', label: 'All', value: stats?.total || 0 },
          { key: 'attention', label: 'Needs attention', value: stats?.needs_attention || 0, accent: true },
          { key: 'in_progress', label: 'In progress', value: stats?.in_progress || 0 },
          { key: 'live', label: 'Live', value: stats?.live || 0 },
          { key: 'archived', label: 'Archived', value: stats?.archived || 0 },
          { key: 'rejected', label: 'Rejected', value: stats?.rejected || 0 },
        ]}
        active={activeFilter}
        onChange={setActiveFilter}
      />

      <div className="mb-10">
        <ClaimStatusCard claim={claim} />
      </div>

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

      {(grouped.needs_submission.length > 0 || grouped.needs_revision.length > 0) &&
        activeFilter === 'all' && (
          <section className="surface p-6 mb-10" style={{ borderColor: 'var(--warn)' }}>
            <p className="meta mb-3" style={{ color: 'var(--warn)' }}>
              Action required
            </p>
            <ul className="space-y-3">
              {grouped.needs_submission.map((c) => (
                <ActionRow
                  key={c.token_id}
                  card={c}
                  message="Ready to submit for evaluation"
                  cta="Submit"
                  loading={actionLoading === c.token_id}
                  onClick={() => handleSubmit(c.token_id)}
                />
              ))}
              {grouped.needs_revision.map((c) => (
                <ActionRow
                  key={c.token_id}
                  card={c}
                  message="Changes requested by Reviewer"
                  cta="Revise"
                  href={`/workflow?tokenId=${c.token_id}&action=revise`}
                />
              ))}
            </ul>
          </section>
        )}

      <section className="surface overflow-hidden">
        <header
          className="flex items-baseline justify-between px-6 py-4 border-b"
          style={{ borderColor: 'var(--border)' }}
        >
          <h2 className="text-base font-semibold tracking-tight">
            {activeFilter === 'all'
              ? 'All cards'
              : activeFilter === 'attention'
                ? 'Needs attention'
                : activeFilter === 'in_progress'
                  ? 'In progress'
                  : activeFilter === 'live'
                    ? 'Live'
                    : activeFilter === 'archived'
                      ? 'Archived'
                      : 'Rejected'}
          </h2>
          <span className="meta">{filtered.length} card{filtered.length !== 1 ? 's' : ''}</span>
        </header>

        {filtered.length === 0 ? (
          <div className="px-6 py-16 text-center">
            <h3 className="text-lg font-semibold tracking-tight">
              {activeFilter === 'all'
                ? "You haven't created any cards yet"
                : 'No cards in this category'}
            </h3>
            {activeFilter === 'all' && (
              <Link href="/create" className="btn btn-primary mt-6">
                Create your first card
              </Link>
            )}
          </div>
        ) : (
          <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {filtered.map((card) => (
              <li
                key={card.token_id}
                className="px-6 py-4 flex items-center justify-between gap-6 hover:bg-[var(--bg-subtle)] transition-colors"
              >
                <div className="flex items-baseline gap-3 min-w-0">
                  <span className="mono" style={{ color: 'var(--fg-faint)' }}>
                    #{card.token_id}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[14.5px] font-medium truncate">
                      {card.model_name || 'Untitled card'}
                    </p>
                    <p className="text-[12.5px] mt-0.5 truncate" style={{ color: 'var(--fg-subtle)' }}>
                      {card.organization} · <span className="mono">v{card.version}</span>
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className={`pill ${STATUS_TONE[card.status] || 'pill-muted'}`}>
                    {STATUS_LABEL[card.status] || card.status}
                  </span>
                  {(card.status === 'Created' || card.status === 'Revised') && (
                    <button
                      onClick={() => handleSubmit(card.token_id)}
                      disabled={actionLoading === card.token_id}
                      className="btn btn-secondary btn-sm"
                    >
                      {actionLoading === card.token_id
                        ? 'Submitting...'
                        : (card.status === 'Revised' ? 'Submit for re-review' : 'Submit')}
                    </button>
                  )}
                  {card.status === 'RevisionRequested' && (
                    <Link
                      href={`/create?revise=${card.token_id}`}
                      className="btn btn-secondary btn-sm"
                    >
                      Revise
                    </Link>
                  )}
                  <DownloadMenu tokenId={card.token_id} />
                  <Link href={`/model/${card.token_id}`} className="link-muted text-[13px]">
                    Open
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

function FilterRow({
  items,
  active,
  onChange,
}: {
  items: Array<{ key: string; label: string; value: number; accent?: boolean }>;
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-10">
      {items.map((item) => {
        const isActive = active === item.key;
        return (
          <button
            key={item.key}
            onClick={() => onChange(item.key)}
            className="surface p-4 text-left transition-colors"
            style={{
              borderColor: isActive
                ? 'var(--fg)'
                : item.accent && item.value > 0
                  ? 'var(--warn)'
                  : 'var(--border)',
              background: isActive ? 'var(--bg-subtle)' : 'var(--bg)',
            }}
          >
            <p
              className="text-2xl font-semibold tabular-nums"
              style={{
                color:
                  item.accent && item.value > 0 && !isActive
                    ? 'var(--warn)'
                    : 'var(--fg)',
              }}
            >
              {item.value}
            </p>
            <p className="meta mt-1">{item.label}</p>
          </button>
        );
      })}
    </div>
  );
}

function ActionRow({
  card,
  message,
  cta,
  href,
  onClick,
  loading,
}: {
  card: ModelCard;
  message: string;
  cta: string;
  href?: string;
  onClick?: () => void;
  loading?: boolean;
}) {
  return (
    <li className="flex items-center justify-between gap-4">
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="mono" style={{ color: 'var(--fg-faint)' }}>
            #{card.token_id}
          </span>
          <span className="text-[14.5px] font-medium truncate">
            {card.model_name || 'Untitled card'}
          </span>
          <span className="mono text-[12px]" style={{ color: 'var(--fg-subtle)' }}>
            v{card.version}
          </span>
        </div>
        <p className="text-[13px] mt-1" style={{ color: 'var(--warn)' }}>
          {message}
        </p>
      </div>
      {href ? (
        <Link href={href} className="btn btn-primary btn-sm">
          {cta}
        </Link>
      ) : (
        <button onClick={onClick} disabled={loading} className="btn btn-primary btn-sm">
          {loading ? 'Submitting...' : cta}
        </button>
      )}
    </li>
  );
}

function DownloadMenu({ tokenId }: { tokenId: number }) {
  const [open, setOpen] = useState(false);
  const base = `http://localhost:8000/api/model-cards/${tokenId}/export`;
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="btn btn-secondary btn-sm"
      >
        Download ▾
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div
            className="absolute right-0 mt-2 z-20 surface overflow-hidden text-[13px]"
            style={{ minWidth: '8rem' }}
          >
            <a href={`${base}?format=json`} download className="block px-3 py-2 hover:bg-[var(--bg-subtle)]">JSON</a>
            <a href={`${base}?format=md`} download className="block px-3 py-2 hover:bg-[var(--bg-subtle)]">Markdown</a>
            <a href={`${base}?format=html`} download className="block px-3 py-2 hover:bg-[var(--bg-subtle)]">HTML</a>
          </div>
        </>
      )}
    </div>
  );
}
