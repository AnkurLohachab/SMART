'use client';

import { useEffect, useState } from 'react';
import { safeDate } from '@/lib/utils';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface Cycle {
  cycle: number | null;
  request: { by: string; feedback: string; at: any } | null;
  response: { by: string; notes: string; at: any } | null;
}

interface History {
  token_id: number;
  revision_count: number;
  open_requests: number;
  cycles: Cycle[];
}

function shortAddr(a: string | undefined): string {
  if (!a) return '-';
  return a.length > 14 ? `${a.slice(0, 6)}…${a.slice(-4)}` : a;
}

export function RevisionDialogue({ tokenId }: { tokenId: number }) {
  const [data, setData] = useState<History | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokenId) return;
    fetch(`${API}/api/model-cards/${tokenId}/revision-history`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [tokenId]);

  if (loading) return null;
  if (!data || (data.cycles || []).length === 0) return null;

  return (
    <section className="bg-white border border-gray-200 rounded-lg overflow-hidden mb-8">
      <header
        className="px-6 py-4 border-b border-gray-200 flex items-baseline justify-between"
      >
        <div>
          <h2 className="text-base font-semibold">Revision dialogue</h2>
          <p className="text-[12.5px] text-gray-500 mt-0.5">
            Back-and-forth between the reviewer and the author across the
            card's lifecycle. Recorded on chain.
          </p>
        </div>
        <div className="text-[12.5px] text-gray-500 text-right">
          {data.revision_count} completed
          {data.open_requests > 0 && (
            <span className="ml-2 px-1.5 py-0.5 rounded text-[11px] font-medium" style={{ background: 'rgba(180,83,9,0.10)', color: 'var(--warn,#b45309)' }}>
              {data.open_requests} awaiting author
            </span>
          )}
        </div>
      </header>

      <ol className="divide-y divide-gray-200">
        {data.cycles.map((c, idx) => (
          <li key={idx} className="px-6 py-4">
            <p className="text-[12px] uppercase tracking-wide text-gray-500 mb-2">
              Cycle {c.cycle ?? '?'}
              {c.request && !c.response && (
                <span className="ml-2 text-amber-700 font-medium normal-case tracking-normal">
                  · awaiting author response
                </span>
              )}
            </p>

            {c.request && (
              <div className="mb-3 pl-3 border-l-2 border-amber-300">
                <p className="text-[12.5px] text-gray-500 mb-0.5">
                  Reviewer · {shortAddr(c.request.by)} · {safeDate(c.request.at, 'datetime')}
                </p>
                <p className="text-[14px] text-gray-800 whitespace-pre-wrap">
                  {c.request.feedback || <em className="text-gray-400">(no feedback text)</em>}
                </p>
              </div>
            )}

            {c.response && (
              <div className="pl-3 border-l-2 border-blue-300">
                <p className="text-[12.5px] text-gray-500 mb-0.5">
                  AI Developer · {shortAddr(c.response.by)} · {safeDate(c.response.at, 'datetime')}
                </p>
                <p className="text-[14px] text-gray-800 whitespace-pre-wrap">
                  {c.response.notes || <em className="text-gray-400">(no response text)</em>}
                </p>
              </div>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}

export function RevisionNotesButton({ tokenId }: { tokenId: number }) {
  const [data, setData] = useState<History | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!tokenId) return;
    fetch(`${API}/api/model-cards/${tokenId}/revision-history`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [tokenId]);

  const total = (data?.cycles || []).length;
  const enabled = !loading && total > 0;

  return (
    <>
      <button
        onClick={() => enabled && setOpen(true)}
        disabled={!enabled}
        title={
          loading
            ? 'Loading…'
            : enabled
              ? `${total} revision cycle${total === 1 ? '' : 's'}`
              : 'No revisions yet'
        }
        className="btn btn-secondary btn-sm"
        style={!enabled ? { opacity: 0.45, cursor: 'not-allowed' } : undefined}
      >
        Revision notes{enabled ? ` (${total})` : ''}
      </button>

      {open && data && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center px-4"
          style={{ background: 'rgba(0,0,0,0.5)' }}
          onClick={() => setOpen(false)}
        >
          <div
            className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="px-6 py-4 border-b border-gray-200 flex items-baseline justify-between">
              <div>
                <h2 className="text-base font-semibold">Revision dialogue · token #{tokenId}</h2>
                <p className="text-[12px] text-gray-500 mt-0.5">
                  {data.revision_count} completed
                  {data.open_requests > 0 && ` · ${data.open_requests} awaiting author`}
                </p>
              </div>
              <button onClick={() => setOpen(false)} className="text-gray-500 hover:text-gray-700 text-sm">
                Close
              </button>
            </header>
            <ol className="overflow-y-auto divide-y divide-gray-200">
              {data.cycles.map((c, idx) => (
                <li key={idx} className="px-6 py-4">
                  <p className="text-[12px] uppercase tracking-wide text-gray-500 mb-2">
                    Cycle {c.cycle ?? '?'}
                    {c.request && !c.response && (
                      <span className="ml-2 text-amber-700 font-medium normal-case tracking-normal">
                        · awaiting author response
                      </span>
                    )}
                  </p>
                  {c.request && (
                    <div className="mb-3 pl-3 border-l-2 border-amber-300">
                      <p className="text-[12px] text-gray-500 mb-0.5">
                        Reviewer · {shortAddr(c.request.by)} · {safeDate(c.request.at, 'datetime')}
                      </p>
                      <p className="text-[14px] text-gray-800 whitespace-pre-wrap">
                        {c.request.feedback || <em className="text-gray-400">(no feedback text)</em>}
                      </p>
                    </div>
                  )}
                  {c.response && (
                    <div className="pl-3 border-l-2 border-blue-300">
                      <p className="text-[12px] text-gray-500 mb-0.5">
                        AI Developer · {shortAddr(c.response.by)} · {safeDate(c.response.at, 'datetime')}
                      </p>
                      <p className="text-[14px] text-gray-800 whitespace-pre-wrap">
                        {c.response.notes || <em className="text-gray-400">(no response text)</em>}
                      </p>
                    </div>
                  )}
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </>
  );
}

export function PriorRevisionsWarning({ tokenId }: { tokenId: number }) {
  const [data, setData] = useState<History | null>(null);

  useEffect(() => {
    if (!tokenId) return;
    fetch(`${API}/api/model-cards/${tokenId}/revision-history`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setData(d))
      .catch(() => {});
  }, [tokenId]);

  if (!data || (data.cycles || []).length === 0) return null;
  const last = data.cycles[data.cycles.length - 1];
  const count = data.revision_count;

  return (
    <div className="rounded-md border p-3 mb-3" style={{ borderColor: 'var(--warn,#b45309)', background: 'rgba(180,83,9,0.06)' }}>
      <p className="text-[13px] font-medium" style={{ color: 'var(--warn,#b45309)' }}>
        This card has been revised {count} time{count === 1 ? '' : 's'} already.
      </p>
      {last?.request && (
        <div className="mt-2 text-[12.5px] text-gray-700">
          <p className="text-[11.5px] text-gray-500 mb-0.5">Last reviewer feedback:</p>
          <p className="italic">"{last.request.feedback}"</p>
        </div>
      )}
      {last?.response && (
        <div className="mt-2 text-[12.5px] text-gray-700">
          <p className="text-[11.5px] text-gray-500 mb-0.5">Author's response:</p>
          <p className="italic">"{last.response.notes}"</p>
        </div>
      )}
      <p className="mt-2 text-[12px] text-gray-600">
        If your previous feedback wasn't fully addressed, say so explicitly in
        your new request - the author and any auditor will see the full thread.
      </p>
    </div>
  );
}
