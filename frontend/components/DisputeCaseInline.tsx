'use client';

import { useEffect, useState } from 'react';
import { safeDate } from '@/lib/utils';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface PanelMember {
  uuid: string | null;
  username: string | null;
  role_class: string | null;
  vote: string | null;
  voted_at?: any;
}

interface DisputeCase {
  exists: boolean;
  case_id?: string;
  action_id?: number;
  token_id?: number;
  kind?: string;
  status?: string;
  outcome?: string | null;
  created_at?: any;
  closed_at?: any;
  panel?: PanelMember[];
}

export function DisputeCaseInline({ actionId }: { actionId: number }) {
  const [data, setData] = useState<DisputeCase | null>(null);

  useEffect(() => {
    if (!actionId) return;
    fetch(`${API}/api/disputes/${actionId}/case`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setData(d))
      .catch(() => {});
  }, [actionId]);

  if (!data || !data.exists) return null;

  const panel = (data.panel || []).filter((m) => m.uuid);
  const outcome = data.outcome;
  const tone =
    outcome === 'Upheld' ? 'var(--ok,#15803d)'
    : outcome === 'Repudiated' ? 'var(--danger,#b91c1c)'
    : outcome === 'Split' ? 'var(--warn,#b45309)'
    : 'var(--fg-faint)';

  return (
    <div
      className="mt-3 p-3 rounded-md border text-[13px]"
      style={{ borderColor: 'var(--border)', background: 'var(--bg-subtle)' }}
    >
      <p className="meta mb-2">
        Arbiter panel
        {data.status === 'closed' && outcome && (
          <span className="ml-2" style={{ color: tone }}>
            · outcome: <strong>{outcome}</strong>
          </span>
        )}
        {data.status === 'open' && (
          <span className="ml-2" style={{ color: 'var(--warn)' }}>· awaiting votes</span>
        )}
      </p>
      <ul className="space-y-1">
        {panel.map((m) => (
          <li key={m.uuid || ''} className="flex items-baseline justify-between gap-3">
            <span>
              <span className="font-medium">{m.role_class}</span>
              <span className="meta ml-2">
                {m.username ? m.username : (m.uuid ? `${m.uuid.slice(0, 8)}…` : '?')}
              </span>
            </span>
            <span style={{ color: m.vote ? tone : 'var(--fg-faint)' }}>
              {m.vote
                ? <>voted <strong>{m.vote}</strong> · {safeDate(m.voted_at, 'datetime')}</>
                : 'has not voted yet'}
            </span>
          </li>
        ))}
      </ul>
      <p className="meta mt-2" style={{ color: 'var(--fg-faint)' }}>
        Drawn {safeDate(data.created_at, 'datetime')}
        {data.closed_at && (
          <> · resolved {safeDate(data.closed_at, 'datetime')}</>
        )}
      </p>
    </div>
  );
}
