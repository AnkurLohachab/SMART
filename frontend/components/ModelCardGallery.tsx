'use client';

import { useEffect, useState } from 'react';
import { API_URL } from '../lib/web3/config';
import { safeDate } from '@/lib/utils';

interface ModelCardNFT {
  tokenId: number;
  name: string;
  version: string;
  developer: string;
  status: string;
  description: string;
  purpose: string;
  createdAt: string;
}

const STATUS_TONE: Record<string, string> = {
  Created: 'pill-muted',
  InEvaluation: 'pill-warn',
  Validated: 'pill-info',
  Rejected: 'pill-danger',
  RevisionRequested: 'pill-warn',
  Revised: 'pill-info',
  Published: 'pill-ok',
  Deprecated: 'pill-muted',
};

const STATUS_LABEL: Record<string, string> = {
  Created: 'Draft',
  InEvaluation: 'Under Review',
  Validated: 'Reviewed',
  Rejected: 'Declined',
  RevisionRequested: 'Changes Requested',
  Revised: 'Revised',
  Published: 'Published',
  Deprecated: 'Archived',
};

export function ModelCardGallery() {
  const [modelCards, setModelCards] = useState<ModelCardNFT[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  const fetchModelCards = async () => {
    try {
      setLoading(true);
      setError(null);
      const url =
        statusFilter === 'all'
          ? `${API_URL}/model-cards`
          : `${API_URL}/model-cards?status=${statusFilter}`;
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Failed to fetch model cards: ${response.statusText}`);
      const data = await response.json();
      const cards: ModelCardNFT[] = (data.model_cards || []).map((record: any) => {
        const mc = record.mc || record;
        return {
          tokenId: mc.token_id,
          name: mc.model_name || 'Untitled model',
          version: mc.version || '1.0.0',
          developer: mc.developer_organization || mc.blockchain_address || 'Unknown',
          status: mc.current_status || 'Unknown',
          description: mc.description || 'No description available.',
          purpose: mc.intended_purpose || 'Not specified',
          createdAt: mc.created_at || new Date().toISOString(),
        };
      });
      setModelCards(cards);
    } catch (err: any) {
      console.error('Error fetching model cards:', err);
      setError(err.message || 'Failed to fetch model cards');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchModelCards();
  }, [statusFilter]);

  if (loading) {
    return (
      <div className="grid-cards">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="surface p-6 animate-pulse">
            <div className="h-3 w-16 mb-4 rounded" style={{ background: 'var(--bg-muted)' }} />
            <div className="h-5 w-2/3 mb-3 rounded" style={{ background: 'var(--bg-muted)' }} />
            <div className="h-3 w-full mb-2 rounded" style={{ background: 'var(--bg-muted)' }} />
            <div className="h-3 w-5/6 rounded" style={{ background: 'var(--bg-muted)' }} />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="surface p-6">
        <p className="meta mb-2">Error</p>
        <h3 className="text-base font-semibold tracking-tight mb-2">Failed to load model cards</h3>
        <p className="text-sm" style={{ color: 'var(--fg-muted)' }}>
          {error}
        </p>
        <button onClick={fetchModelCards} className="btn btn-secondary btn-sm mt-4">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6">
        <div>
          <p className="meta mb-2">Cards</p>
          <h2 className="text-xl font-semibold tracking-tight">All model cards</h2>
        </div>
        <div className="flex items-center gap-2">
          <label className="meta">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input"
            style={{ width: 'auto', height: 32, padding: '0 32px 0 12px', fontSize: 13 }}
          >
            <option value="all">All</option>
            <option value="Created">Draft</option>
            <option value="InEvaluation">Under Review</option>
            <option value="Validated">Reviewed</option>
            <option value="Published">Published</option>
            <option value="Deprecated">Archived</option>
          </select>
          <button onClick={fetchModelCards} className="btn btn-secondary btn-sm">
            Refresh
          </button>
        </div>
      </div>

      {modelCards.length === 0 ? (
        <div className="surface p-16 text-center">
          <h3 className="text-lg font-semibold tracking-tight">No model cards found</h3>
          <p className="mt-2 text-sm" style={{ color: 'var(--fg-muted)' }}>
            Create a new model card to get started.
          </p>
        </div>
      ) : (
        <div className="grid-cards">
          {modelCards.map((card) => {
            const tone = STATUS_TONE[card.status] || 'pill-muted';
            const label = STATUS_LABEL[card.status] || card.status;
            return (
              <article key={card.tokenId} className="surface surface-hover p-6 flex flex-col">
                <div className="flex items-baseline justify-between mb-4">
                  <span className="mono" style={{ color: 'var(--fg-faint)' }}>
                    #{card.tokenId}
                  </span>
                  <span className={`pill ${tone}`}>{label}</span>
                </div>
                <h3 className="text-base font-semibold tracking-tight line-clamp-2">{card.name}</h3>
                <p className="mt-1 text-[13px]" style={{ color: 'var(--fg-subtle)' }}>
                  <span className="mono">v{card.version}</span> · {card.developer}
                </p>
                <p className="mt-4 text-[14px] leading-[1.55] line-clamp-3" style={{ color: 'var(--fg-muted)' }}>
                  {card.description}
                </p>
                <dl className="mt-5 space-y-2 text-[13px]">
                  <div className="flex justify-between gap-4">
                    <dt style={{ color: 'var(--fg-subtle)' }}>Purpose</dt>
                    <dd className="text-right" style={{ color: 'var(--fg)' }}>
                      {card.purpose}
                    </dd>
                  </div>
                  <div className="flex justify-between gap-4">
                    <dt style={{ color: 'var(--fg-subtle)' }}>Created</dt>
                    <dd className="text-right" style={{ color: 'var(--fg)' }}>
                      {safeDate(card.createdAt)}
                    </dd>
                  </div>
                </dl>
                <button
                  onClick={() => window.open(`/model/${card.tokenId}`, '_blank')}
                  className="btn btn-secondary mt-6"
                >
                  View details
                </button>
              </article>
            );
          })}
        </div>
      )}

      <p className="meta mt-6">
        {modelCards.length} card{modelCards.length !== 1 ? 's' : ''}
      </p>
    </div>
  );
}
