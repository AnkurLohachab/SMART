'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { safeDate } from '@/lib/utils';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface PanelMember {
  uuid: string | null;
  username: string | null;
  role_class: string | null;
  vote: string | null;
  voted_at?: any;
}

interface SplitCase {
  case_id: string;
  action_id: number;
  token_id: number;
  kind: string;
  status: string;
  outcome: string | null;
  challenger_uuid: string | null;
  created_at: any;
  closed_at: any;
  panel: PanelMember[];
}

interface Props {
  getAuthHeaders: () => HeadersInit;
}

export function SplitVotesTab({ getAuthHeaders }: Props) {
  const [loading, setLoading] = useState(true);
  const [cases, setCases] = useState<SplitCase[]>([]);
  const [resolving, setResolving] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/governance/dispute-cases?outcome=Split`, {
        headers: getAuthHeaders(),
      });
      if (!r.ok) {
        if (r.status === 401 || r.status === 403) {
          toast.error('Admin authorization required');
        } else {
          toast.error('Failed to load split-vote queue');
        }
        return;
      }
      const d = await r.json();
      setCases(d.cases || []);
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

  const resolve = async (actionId: number, finalStatus: 'ResolvedValid' | 'ResolvedInvalid') => {
    setResolving(actionId);
    try {
      const r = await fetch(`${API}/api/actions/${actionId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ final_status: finalStatus }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      toast.success(`Action #${actionId} ruled ${finalStatus}`);
      load();
    } catch (err: any) {
      toast.error(err.message || 'Resolve failed');
    } finally {
      setResolving(null);
    }
  };

  return (
    <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden">
      <header className="flex items-baseline justify-between px-6 py-4 border-b border-gray-700">
        <div>
          <h2 className="text-base font-semibold text-white">Split-vote queue</h2>
          <p className="text-xs text-gray-400 mt-1">
            Panels where Reviewer + Publisher disagreed. As admin you cast the deciding vote
            using <code className="font-mono">/api/actions/&lt;id&gt;/resolve</code>.
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
          <p className="text-gray-400 text-sm">No split votes pending.</p>
          <p className="text-gray-500 text-xs mt-1">
            No split votes to resolve.
          </p>
        </div>
      ) : (
        <ul className="divide-y divide-gray-700">
          {cases.map((c) => (
            <li key={c.case_id} className="px-6 py-5">
              <div className="flex items-baseline justify-between gap-3 flex-wrap">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white">
                    Action #{c.action_id} · token #{c.token_id} ·{' '}
                    <span className="text-xs text-gray-400">{c.kind}</span>
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    Drawn {safeDate(c.created_at, 'datetime')} · split{' '}
                    {safeDate(c.closed_at, 'datetime')}
                  </p>
                </div>
              </div>

              <ul className="mt-3 space-y-1">
                {(c.panel || []).filter((m) => m.uuid).map((m) => (
                  <li
                    key={m.uuid || ''}
                    className="text-xs text-gray-300 flex items-baseline justify-between gap-3"
                  >
                    <span>
                      <span className="font-medium">{m.role_class}</span>{' '}
                      <span className="text-gray-500">
                        {m.username || (m.uuid ? `${m.uuid.slice(0, 8)}…` : '')}
                      </span>
                    </span>
                    <span
                      className={
                        m.vote === 'Upheld'
                          ? 'text-emerald-400'
                          : m.vote === 'Repudiated'
                          ? 'text-red-400'
                          : 'text-gray-500'
                      }
                    >
                      {m.vote || 'no vote'}
                    </span>
                  </li>
                ))}
              </ul>

              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  onClick={() => resolve(c.action_id, 'ResolvedValid')}
                  disabled={resolving === c.action_id}
                  className="px-3 py-1.5 text-xs rounded bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50"
                >
                  {resolving === c.action_id ? 'Resolving…' : 'Override · Uphold'}
                </button>
                <button
                  onClick={() => resolve(c.action_id, 'ResolvedInvalid')}
                  disabled={resolving === c.action_id}
                  className="px-3 py-1.5 text-xs rounded bg-red-600 hover:bg-red-500 text-white disabled:opacity-50"
                >
                  Override · Repudiate
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
