'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { safeDate } from '@/lib/utils';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface ClaimRequest {
  request_id: string;
  uuid: string;
  eoa: string;
  claim_type: number;
  claim_type_name?: string;
  institution: string;
  supporting_url?: string;
  note?: string;
  status: 'pending' | 'approved' | 'rejected';
  created_at: string;
  resolved_at?: string;
  rejection_reason?: string;
  on_chain_tx_hash?: string;
}

interface Props {
  getAuthHeaders: () => HeadersInit;
}

export function ClaimRequestsTab({ getAuthHeaders }: Props) {
  const [filter, setFilter] = useState<'pending' | 'approved' | 'rejected' | 'all'>('pending');
  const [requests, setRequests] = useState<ClaimRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(
        `${API}/api/identity/claim-requests/admin?status_filter=${filter}`,
        { headers: getAuthHeaders() },
      );
      if (r.ok) {
        const d = await r.json();
        setRequests(d.requests || []);
      } else if (r.status === 401 || r.status === 403) {
        toast.error('Admin authorization required');
      } else {
        toast.error('Failed to load claim requests');
      }
    } catch (_) {
      toast.error('Network error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  const approve = async (rid: string) => {
    setBusy(rid);
    try {
      const r = await fetch(`${API}/api/identity/claim-requests/${rid}/approve`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      toast.success('Approved · institutional claim issued');
      load();
    } catch (err: any) {
      toast.error(err.message || 'Approval failed');
    } finally {
      setBusy(null);
    }
  };

  const reject = async (rid: string) => {
    if (!rejectReason.trim()) {
      toast.error('Provide a rejection reason');
      return;
    }
    setBusy(rid);
    try {
      const r = await fetch(`${API}/api/identity/claim-requests/${rid}/reject`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ reason: rejectReason.trim() }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      toast.success('Rejected');
      setRejectingId(null);
      setRejectReason('');
      load();
    } catch (err: any) {
      toast.error(err.message || 'Rejection failed');
    } finally {
      setBusy(null);
    }
  };

  const statusColor = (s: string) =>
    s === 'approved' ? 'text-emerald-300 border-emerald-500/40 bg-emerald-500/10'
    : s === 'rejected' ? 'text-rose-300 border-rose-500/40 bg-rose-500/10'
    : 'text-amber-300 border-amber-500/40 bg-amber-500/10';

  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
        <div className="flex items-baseline justify-between mb-4 flex-wrap gap-3">
          <div>
            <h3 className="text-lg font-semibold text-white">Claim requests</h3>
            <p className="text-sm text-gray-400 mt-1">Approve institutional upgrades.</p>
          </div>
          <div className="flex gap-1.5">
            {(['pending', 'approved', 'rejected', 'all'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1.5 text-xs rounded-lg ${
                  filter === f
                    ? 'bg-indigo-600 text-white'
                    : 'bg-gray-700/50 text-gray-300 hover:bg-gray-700'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="h-32 bg-gray-700/30 rounded-xl animate-pulse" />
        ) : requests.length === 0 ? (
          <div className="px-6 py-12 text-center bg-gray-700/20 rounded-xl">
            <p className="text-sm text-gray-400 uppercase tracking-wide mb-2">No requests</p>
            <p className="text-sm text-gray-500">
              No {filter === 'all' ? '' : filter + ' '}requests.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-700/50">
            {requests.map((r) => (
              <li key={r.request_id} className="py-5">
                <div className="flex items-baseline justify-between gap-3 flex-wrap mb-2">
                  <div className="min-w-0">
                    <p className="text-base font-medium text-white">{r.institution}</p>
                    <p className="text-xs mt-1 text-gray-400">
                      <span className="font-mono">{r.eoa.slice(0, 10)}…{r.eoa.slice(-6)}</span>
                      {' · '}
                      {r.claim_type_name || `claim_type=${r.claim_type}`}
                      {' · '}
                      submitted {safeDate(r.created_at, 'datetime')}
                    </p>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded border ${statusColor(r.status)}`}>
                    {r.status}
                  </span>
                </div>

                {r.supporting_url && (
                  <p className="text-xs mb-1">
                    <a href={r.supporting_url} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:text-indigo-300 underline">
                      {r.supporting_url}
                    </a>
                  </p>
                )}
                {r.note && <p className="text-sm text-gray-400 mb-2">{r.note}</p>}

                {r.status === 'rejected' && r.rejection_reason && (
                  <p className="text-sm text-gray-400 mt-2">Rejected: {r.rejection_reason}</p>
                )}
                {r.status === 'approved' && r.on_chain_tx_hash && (
                  <p className="text-xs mt-2 font-mono truncate text-gray-500">tx {r.on_chain_tx_hash}</p>
                )}

                {r.status === 'pending' && (
                  <div className="mt-3">
                    {rejectingId === r.request_id ? (
                      <div className="flex flex-col gap-2 sm:flex-row">
                        <input
                          className="flex-1 px-3 py-1.5 text-sm bg-gray-900 border border-gray-700 rounded-lg text-white placeholder-gray-500"
                          placeholder="Reason for rejection"
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          disabled={busy === r.request_id}
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => reject(r.request_id)}
                            className="px-3 py-1.5 text-sm bg-rose-600 hover:bg-rose-500 text-white rounded-lg disabled:opacity-50"
                            disabled={busy === r.request_id || !rejectReason.trim()}
                          >
                            Confirm reject
                          </button>
                          <button
                            onClick={() => { setRejectingId(null); setRejectReason(''); }}
                            className="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg"
                            disabled={busy === r.request_id}
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex gap-2 flex-wrap">
                        <button
                          onClick={() => approve(r.request_id)}
                          className="px-3 py-1.5 text-sm bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg disabled:opacity-50"
                          disabled={busy === r.request_id}
                        >
                          {busy === r.request_id ? 'Issuing on chain…' : 'Approve · issue claim'}
                        </button>
                        <button
                          onClick={() => setRejectingId(r.request_id)}
                          className="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg"
                          disabled={busy === r.request_id}
                        >
                          Reject…
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
