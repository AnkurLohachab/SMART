'use client';

import { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { ActionList, ResolveModal, type ActionRecord } from '@/components/Governance';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Props {
  getAuthHeaders: () => HeadersInit;
}

export function IdentityDisputesTab({ getAuthHeaders }: Props) {
  const [loading, setLoading] = useState(true);
  const [disputes, setDisputes] = useState<ActionRecord[]>([]);
  const [target, setTarget] = useState<ActionRecord | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/governance/disputes`, { headers: getAuthHeaders() });
      if (r.ok) {
        const d = await r.json();
        setDisputes(d.disputes || []);
      } else if (r.status === 401 || r.status === 403) {
        toast.error('Admin authorization required');
      } else {
        toast.error('Failed to load dispute queue');
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
  }, []);

  const resolve = async (action_id: number, final_status: 'ResolvedValid' | 'ResolvedInvalid') => {
    const r = await fetch(`${API}/api/actions/${action_id}/resolve`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ final_status }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.detail || `HTTP ${r.status}`);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
        <div className="flex items-baseline justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-white">Identity disputes</h3>
            <p className="text-sm text-gray-400 mt-1">Resolve challenged actions.</p>
          </div>
          <button onClick={load} className="text-sm text-indigo-400 hover:text-indigo-300">Refresh</button>
        </div>

        {loading ? (
          <div className="h-32 bg-gray-700/30 rounded-xl animate-pulse" />
        ) : disputes.length === 0 ? (
          <div className="px-6 py-12 text-center bg-gray-700/20 rounded-xl">
            <p className="text-sm text-gray-400 uppercase tracking-wide mb-2">No disputes</p>
            <p className="text-sm text-gray-500">
              No challenged actions are awaiting resolution.
            </p>
          </div>
        ) : (
          <div className="bg-gray-900/40 rounded-xl p-4">
            <div className="text-gray-200">
              <ActionList actions={disputes} showToken />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {disputes.map((d) => (
                <button
                  key={d.action_id}
                  onClick={() => setTarget(d)}
                  className="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-white rounded-lg"
                >
                  Resolve action #{d.action_id}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <ResolveModal
        action={target}
        onClose={() => setTarget(null)}
        onSuccess={() => {
          toast.success('Action resolved');
          load();
        }}
        resolveFetcher={resolve}
      />
    </div>
  );
}
