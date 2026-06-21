'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { toast } from 'sonner';
import { safeDate } from '@/lib/utils';
import { PriorRevisionsWarning, RevisionNotesButton } from '@/components/RevisionDialogue';

interface ModelCard {
  token_id: number;
  model_name: string;
  description?: string;
  version: string;
  organization: string;
  status: string;
  created_at: string;
  creator_address?: string;
  algorithms_used?: string;
  intended_purpose?: string;
}

const STATUS_TONE: Record<string, string> = {
  Created: 'pill-muted',
  InEvaluation: 'pill-warn',
  Validated: 'pill-info',
  Published: 'pill-ok',
  Rejected: 'pill-danger',
  RevisionRequested: 'pill-warn',
  Revised: 'pill-info',
  Deprecated: 'pill-muted',
};

const STATUS_LABEL: Record<string, string> = {
  Created: 'Draft',
  InEvaluation: 'Under Review',
  Validated: 'Reviewed',
  Published: 'Published',
  Rejected: 'Declined',
  RevisionRequested: 'Changes Requested',
  Revised: 'Revised',
  Deprecated: 'Archived',
};

export default function WorkflowPage() {
  const router = useRouter();
  const { isAuthenticated, role, getWalletAddress, isLoading: authLoading } = useAuth();

  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [cards, setCards] = useState<ModelCard[]>([]);
  const [expandedCard, setExpandedCard] = useState<number | null>(null);
  const [canAct, setCanAct] = useState<Record<number, { ok: boolean; reason?: string; canDeprecate?: boolean }>>({});

  const [actionModal, setActionModal] = useState<{
    type: 'reject' | 'revision' | 'deprecate' | null;
    tokenId: number | null;
    modelName: string;
  }>({ type: null, tokenId: null, modelName: '' });
  const [actionReason, setActionReason] = useState('');

  useEffect(() => {
    if (!authLoading && !isAuthenticated) router.push('/auth');
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (isAuthenticated && role) fetchPendingCards();
  }, [isAuthenticated, role]);

  const fetchPendingCards = async () => {
    setLoading(true);
    try {
      const walletAddress = getWalletAddress();
      let endpoint = '';
      if (role === 'AIDeveloper') {
        endpoint = `http://localhost:8000/api/dashboard/developer?developer_address=${walletAddress}`;
      } else if ((role === 'Reviewer' || role === 'Authenticator')) {
        endpoint = `http://localhost:8000/api/dashboard/authenticator?authenticator_address=${walletAddress}`;
      } else if (role === 'Publisher') {
        endpoint = `http://localhost:8000/api/dashboard/publisher?publisher_address=${walletAddress}`;
      } else {
        endpoint = 'http://localhost:8000/api/model-cards';
      }

      const res = await fetch(endpoint);
      if (res.ok) {
        const data = await res.json();
        let transformed: ModelCard[] = [];
        if (role === 'AIDeveloper' && data.grouped) {
          const needsAction = [
            ...(data.grouped.needs_submission || []),
            ...(data.grouped.needs_revision || []),
          ];
          transformed = needsAction.map((c: any) => ({
            token_id: c.token_id,
            model_name: c.model_name,
            version: c.version,
            organization: c.organization,
            status: c.status,
            created_at: c.created_at,
          }));
        } else if ((role === 'Reviewer' || role === 'Authenticator') && data.pending_validation) {
          transformed = data.pending_validation.map((c: any) => ({
            token_id: c.token_id,
            model_name: c.model_name,
            version: c.version,
            organization: c.organization,
            status: 'InEvaluation',
            created_at: c.created_at,
            creator_address: c.creator_address,
          }));
        } else if (role === 'Publisher') {
          const ready = (data.ready_to_publish || []).map((c: any) => ({ ...c, status: 'Validated' }));
          const published = (data.published_cards || []).map((c: any) => ({ ...c, status: 'Published' }));
          transformed = [...ready, ...published];
        } else if (data.model_cards) {
          transformed = data.model_cards;
        }
        setCards(transformed);

        // Pre-fetch can-act per card to enforce separation-of-duties for review/publish roles.
        if (walletAddress && transformed.length && ((role === 'Reviewer' || role === 'Authenticator') || role === 'Publisher')) {
          const entries = await Promise.all(
            transformed.map(async (c) => {
              try {
                const r = await fetch(
                  `http://localhost:8000/api/model-cards/${c.token_id}/can-act?actor=${encodeURIComponent(walletAddress)}`
                );
                if (!r.ok) {
                  return [c.token_id, { ok: false, reason: 'Permission check failed.' }] as const;
                }
                const d = await r.json();
                const action = (role === 'Reviewer' || role === 'Authenticator') ? !!d.can?.validate : !!d.can?.publish;
                return [c.token_id, {
                  ok: action,
                  reason: d.reason_if_blocked || undefined,
                  canDeprecate: !!d.can?.deprecate,
                }] as const;
              } catch {
                return [c.token_id, { ok: false, reason: 'Permission check failed.' }] as const;
              }
            })
          );
          setCanAct(Object.fromEntries(entries));
        } else {
          setCanAct({});
        }
      }
    } catch (e) {
      console.error('Failed to fetch cards:', e);
      toast.error('Failed to load cards');
    } finally {
      setLoading(false);
    }
  };

  const fetchCardDetails = async (tokenId: number) => {
    try {
      const res = await fetch(`http://localhost:8000/api/model-cards/${tokenId}`);
      if (res.ok) {
        const data = await res.json();
        setCards((prev) =>
          prev.map((c) =>
            c.token_id === tokenId
              ? {
                  ...c,
                  description: data.metadata?.['1. Model Details']?.Description,
                  algorithms_used: data.metadata?.['1. Model Details']?.['Algorithm(s) Used'],
                  intended_purpose: data.metadata?.['1. Model Details']?.['Intended Purpose'],
                }
              : c
          )
        );
      }
    } catch (e) {
      console.error('Failed to fetch card details:', e);
    }
  };

  const toggleExpand = (tokenId: number) => {
    if (expandedCard === tokenId) {
      setExpandedCard(null);
    } else {
      setExpandedCard(tokenId);
      fetchCardDetails(tokenId);
    }
  };

  const callAction = async (
    endpoint: string,
    body: Record<string, unknown>,
    successMsg: string,
    tokenId: number
  ) => {
    setActionLoading(tokenId);
    try {
      const res = await fetch(`http://localhost:8000/api/model-cards/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        toast.success(successMsg);
        fetchPendingCards();
      } else {
        const error = await res.json();
        toast.error(error.detail || `${endpoint} failed`);
      }
    } catch (e) {
      toast.error(`Failed to ${endpoint}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSubmit = (id: number) => {
    const wallet = getWalletAddress();
    if (!wallet) return;
    callAction('submit', { token_id: id, initiator_address: wallet }, 'Card submitted for evaluation', id);
  };

  const handleValidate = (id: number) => {
    const wallet = getWalletAddress();
    if (!wallet) return;
    callAction(
      'validate',
      { token_id: id, validator_address: wallet, validation_notes: 'Validated via workflow' },
      'Card validated',
      id
    );
  };

  const handlePublish = (id: number) => {
    const wallet = getWalletAddress();
    if (!wallet) return;
    callAction('publish', { token_id: id, publisher_address: wallet }, 'Card published', id);
  };

  const handleActionWithReason = async () => {
    if (!actionModal.tokenId || !actionReason.trim()) {
      toast.error('Provide a reason');
      return;
    }
    const wallet = getWalletAddress();
    if (!wallet) return;
    let endpoint = '';
    const body: Record<string, unknown> = { token_id: actionModal.tokenId };
    if (actionModal.type === 'reject') {
      endpoint = 'reject';
      body.rejector_address = wallet;
      body.reason = actionReason;
    } else if (actionModal.type === 'revision') {
      endpoint = 'request-revision';
      body.requester_address = wallet;
      body.feedback = actionReason;
    } else if (actionModal.type === 'deprecate') {
      endpoint = 'deprecate';
      body.deprecator_address = wallet;
      body.reason = actionReason;
    }
    setActionLoading(actionModal.tokenId);
    try {
      const res = await fetch(`http://localhost:8000/api/model-cards/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        toast.success('Action recorded');
        setActionModal({ type: null, tokenId: null, modelName: '' });
        setActionReason('');
        fetchPendingCards();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Action failed');
      }
    } catch (e) {
      toast.error('Failed to complete action');
    } finally {
      setActionLoading(null);
    }
  };

  const roleHeader = (() => {
    switch (role) {
      case 'AIDeveloper':
        return { eyebrow: 'Developer', title: 'My tasks', subtitle: 'Cards that need your action.' };
      case 'Reviewer':
      case 'Authenticator':
        return { eyebrow: 'Reviewer', title: 'Review center', subtitle: 'Endorse, request changes, or decline submitted cards.' };
      case 'Publisher':
        return { eyebrow: 'Publisher', title: 'Publication queue', subtitle: 'List endorsed cards in the public registry, or archive stale ones.' };
      default:
        return { eyebrow: 'Workflow', title: 'Workflow', subtitle: 'Manage model card lifecycle.' };
    }
  })();

  if (authLoading || loading) {
    return (
      <main className="container-app py-16">
        <div className="space-y-3 animate-pulse">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="surface h-24" />
          ))}
        </div>
      </main>
    );
  }

  return (
    <main className="container-app py-10 lg:py-14">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between mb-10">
        <div>
          <p className="meta mb-3">{roleHeader.eyebrow}</p>
          <h1 className="text-3xl lg:text-4xl font-semibold tracking-tight">{roleHeader.title}</h1>
          <p className="mt-3 max-w-xl" style={{ color: 'var(--fg-muted)' }}>
            {roleHeader.subtitle}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={fetchPendingCards} className="btn btn-secondary">
            Refresh
          </button>
          {role === 'AIDeveloper' && (
            <Link href="/create" className="btn btn-primary">
              New card
            </Link>
          )}
        </div>
      </div>

      {cards.length === 0 ? (
        <div className="surface p-16 text-center">
          <h3 className="text-lg font-semibold tracking-tight">No cards need your action</h3>
        </div>
      ) : (
        <ul className="space-y-3">
          {cards.map((card) => {
            const expanded = expandedCard === card.token_id;
            return (
              <li key={card.token_id} className="surface overflow-hidden">
                <button
                  onClick={() => toggleExpand(card.token_id)}
                  className="w-full px-6 py-5 flex items-start justify-between gap-6 text-left hover:bg-[var(--bg-subtle)] transition-colors"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-baseline gap-3">
                      <span className="mono" style={{ color: 'var(--fg-faint)' }}>
                        #{card.token_id}
                      </span>
                      <span className="text-[15px] font-medium truncate">
                        {card.model_name || 'Untitled card'}
                      </span>
                      <span className={`pill ${STATUS_TONE[card.status] || 'pill-muted'}`}>
                        {STATUS_LABEL[card.status] || card.status}
                      </span>
                    </div>
                    <p className="text-[13px] mt-1.5 truncate" style={{ color: 'var(--fg-subtle)' }}>
                      {card.organization || 'Unknown organization'} ·{' '}
                      <span className="mono">v{card.version}</span> ·{' '}
                      {safeDate(card.created_at)}
                    </p>
                  </div>
                  <span className="meta shrink-0">{expanded ? 'Hide' : 'Details'}</span>
                </button>

                {expanded && (
                  <div className="px-6 pb-5 border-t pt-5 space-y-4" style={{ borderColor: 'var(--border)' }}>
                    {card.description && (
                      <div>
                        <p className="meta mb-1">Description</p>
                        <p className="text-[14px] leading-[1.6]" style={{ color: 'var(--fg-muted)' }}>
                          {card.description}
                        </p>
                      </div>
                    )}
                    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-[13.5px]">
                      {card.intended_purpose && (
                        <div>
                          <dt className="meta">Intended purpose</dt>
                          <dd className="mt-1">{card.intended_purpose}</dd>
                        </div>
                      )}
                      {card.algorithms_used && (
                        <div>
                          <dt className="meta">Algorithms</dt>
                          <dd className="mt-1">{card.algorithms_used}</dd>
                        </div>
                      )}
                      {card.creator_address && (
                        <div>
                          <dt className="meta">Creator</dt>
                          <dd className="mono mt-1 truncate">{card.creator_address}</dd>
                        </div>
                      )}
                    </dl>

                    <div className="flex flex-wrap items-center gap-2 pt-2">
                      <Link href={`/model/${card.token_id}`} className="btn btn-secondary btn-sm">
                        Open card
                      </Link>
                      <RevisionNotesButton tokenId={card.token_id} />

                      {role === 'AIDeveloper' && (card.status === 'Created' || card.status === 'Revised') && (
                        <button
                          onClick={() => handleSubmit(card.token_id)}
                          disabled={actionLoading === card.token_id}
                          className="btn btn-primary btn-sm"
                        >
                          {actionLoading === card.token_id ? 'Submitting...' : 'Submit for evaluation'}
                        </button>
                      )}
                      {role === 'AIDeveloper' && card.status === 'RevisionRequested' && (
                        <Link href={`/create?revise=${card.token_id}`} className="btn btn-primary btn-sm">
                          Revise
                        </Link>
                      )}

                      {(role === 'Reviewer' || role === 'Authenticator') && card.status === 'InEvaluation' && (() => {
                        const ca = canAct[card.token_id];
                        const isChecking = ca === undefined;
                        const isAllowed = ca?.ok === true;
                        const reason = ca?.reason;
                        return (
                          <>
                            <button
                              onClick={() => handleValidate(card.token_id)}
                              disabled={actionLoading === card.token_id || !isAllowed}
                              className="btn btn-primary btn-sm"
                              title={reason || ''}
                            >
                              {actionLoading === card.token_id ? 'Endorsing...' : 'Endorse'}
                            </button>
                            <button
                              onClick={() =>
                                setActionModal({
                                  type: 'revision',
                                  tokenId: card.token_id,
                                  modelName: card.model_name,
                                })
                              }
                              disabled={!isAllowed}
                              className="btn btn-secondary btn-sm"
                              title={reason || ''}
                            >
                              Request revision
                            </button>
                            <button
                              onClick={() =>
                                setActionModal({
                                  type: 'reject',
                                  tokenId: card.token_id,
                                  modelName: card.model_name,
                                })
                              }
                              disabled={!isAllowed}
                              className="btn btn-danger btn-sm"
                              title={reason || ''}
                            >
                              Reject
                            </button>
                            {isChecking && (
                              <span className="text-[12.5px]" style={{ color: 'var(--fg-faint)' }}>
                                Checking permissions…
                              </span>
                            )}
                            {ca?.ok === false && reason && (
                              <span className="basis-full text-[12.5px]" style={{ color: 'var(--warn,#b45309)' }}>
                                {reason}
                              </span>
                            )}
                          </>
                        );
                      })()}

                      {role === 'Publisher' && card.status === 'Validated' && (() => {
                        const ca = canAct[card.token_id];
                        const isChecking = ca === undefined;
                        const isAllowed = ca?.ok === true;
                        const reason = ca?.reason;
                        return (
                          <>
                            <button
                              onClick={() => handlePublish(card.token_id)}
                              disabled={actionLoading === card.token_id || !isAllowed}
                              className="btn btn-primary btn-sm"
                              title={reason || ''}
                            >
                              {actionLoading === card.token_id ? 'Publishing...' : 'Publish'}
                            </button>
                            {isChecking && (
                              <span className="text-[12.5px]" style={{ color: 'var(--fg-faint)' }}>
                                Checking permissions…
                              </span>
                            )}
                            {ca?.ok === false && reason && (
                              <span className="basis-full text-[12.5px]" style={{ color: 'var(--warn,#b45309)' }}>
                                {reason}
                              </span>
                            )}
                          </>
                        );
                      })()}
                      {role === 'Publisher' && card.status === 'Published' && (
                        <button
                          onClick={() =>
                            setActionModal({
                              type: 'deprecate',
                              tokenId: card.token_id,
                              modelName: card.model_name,
                            })
                          }
                          className="btn btn-danger btn-sm"
                        >
                          Archive
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {actionModal.type && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.4)' }}
          onClick={() => setActionModal({ type: null, tokenId: null, modelName: '' })}
        >
          <div
            className="surface w-full max-w-md overflow-hidden"
            style={{ boxShadow: 'var(--shadow-lg)' }}
            onClick={(e) => e.stopPropagation()}
          >
            <header className="px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
              <p className="meta">
                {actionModal.type === 'reject'
                  ? 'Decline card'
                  : actionModal.type === 'revision'
                    ? 'Request changes'
                    : 'Archive card'}
              </p>
              <h2 className="text-lg font-semibold tracking-tight mt-1">
                #{actionModal.tokenId} · {actionModal.modelName}
              </h2>
            </header>
            <div className="px-6 py-5">
              {actionModal.type === 'revision' && actionModal.tokenId && (
                <PriorRevisionsWarning tokenId={actionModal.tokenId} />
              )}
              <label className="label">
                {actionModal.type === 'reject'
                  ? 'Rejection reason'
                  : actionModal.type === 'revision'
                    ? 'Revision feedback'
                    : 'Deprecation reason'}
              </label>
              <textarea
                value={actionReason}
                onChange={(e) => setActionReason(e.target.value)}
                rows={4}
                className="input"
                placeholder="Explain your decision so the developer (or auditor) can act on it."
                autoFocus
              />
            </div>
            <footer
              className="px-6 py-4 border-t flex items-center justify-end gap-2"
              style={{ borderColor: 'var(--border)' }}
            >
              <button
                onClick={() => {
                  setActionModal({ type: null, tokenId: null, modelName: '' });
                  setActionReason('');
                }}
                className="btn btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleActionWithReason}
                disabled={!actionReason.trim() || actionLoading === actionModal.tokenId}
                className={
                  actionModal.type === 'reject' || actionModal.type === 'deprecate'
                    ? 'btn btn-danger'
                    : 'btn btn-primary'
                }
              >
                {actionLoading === actionModal.tokenId
                  ? 'Working...'
                  : actionModal.type === 'reject'
                    ? 'Decline'
                    : actionModal.type === 'revision'
                      ? 'Request changes'
                      : 'Archive'}
              </button>
            </footer>
          </div>
        </div>
      )}
    </main>
  );
}
