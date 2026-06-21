'use client';

import { useState } from 'react';
import { safeDate } from '@/lib/utils';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface VersionRecord {
  token_id: number;
  name_hash: string;
  supersedes: number;
  relation: string;
  relation_index: number;
  envelope_hash: string;
  within_envelope: boolean;
  envelope_status: string;
  envelope_status_index: number;
  minted_at: number;
  minted_by: string;
  challenger: string;
  challenged_at: number;
  arbiter: string;
  resolved_at: number;
}

export interface LinePayload {
  name: string;
  name_hash: string;
  alias: string;
  has_name_record: boolean;
  controller: string | null;
  first_claimed_at: number;
  envelope: {
    hash: string;
    pinned_at: number;
    updated_at: number;
    pinned_by: string;
  };
  versions: VersionRecord[];
}

function shortHash(h?: string | null): string {
  if (!h) return '-';
  const clean = h.startsWith('0x') ? h.slice(2) : h;
  if (!clean || /^0+$/.test(clean)) return 'none';
  return `${clean.slice(0, 8)}…`;
}

function shortAddr(a?: string | null): string {
  if (!a || a === '0x0000000000000000000000000000000000000000') return '-';
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}

export function LineageStrip({ version, line }: { version: VersionRecord | null; line?: LinePayload | null }) {
  if (!version || !version.token_id) return null;

  const status = version.envelope_status;

  const palette = {
    none: { fg: 'var(--fg-faint)', bg: 'rgba(115,115,115,0.05)', label: 'Outside the pre-approved change plan' },
    asserted: { fg: 'var(--ok)', bg: 'rgba(21,128,61,0.06)', label: 'Within the pre-approved change plan' },
    disputed: { fg: 'var(--warn)', bg: 'rgba(180,83,9,0.07)', label: 'Change-plan claim challenged' },
    upheld: { fg: 'var(--ok)', bg: 'rgba(21,128,61,0.08)', label: 'Change-plan claim upheld by arbiter' },
    repudiated: { fg: 'var(--danger)', bg: 'rgba(185,28,28,0.07)', label: 'Change-plan claim ruled invalid' },
  } as const;

  let key: keyof typeof palette = 'none';
  if (version.within_envelope) {
    if (status === 'Asserted') key = 'asserted';
    else if (status === 'Disputed') key = 'disputed';
    else if (status === 'Upheld') key = 'upheld';
    else if (status === 'Repudiated') key = 'repudiated';
  }
  const p = palette[key];

  return (
    <div className="mb-8 px-5 py-4 rounded-md border" style={{ borderColor: p.fg, background: p.bg }}>
      <div className="flex items-baseline gap-3 mb-1 flex-wrap">
        <span className="text-[13px] font-medium uppercase tracking-wide" style={{ color: p.fg }}>{p.label}</span>
        <span className="meta">
          {version.supersedes
            ? <>change type: <strong>{version.relation}</strong> · replaces token #{version.supersedes}</>
            : <>change type: <strong>{version.relation}</strong> · first version of this line</>}
        </span>
      </div>
      <p className="text-[13px]" style={{ color: 'var(--fg-muted)' }}>
        {key === 'none' && 'The author did not claim that this version stays within the model\'s pre-approved change plan. (They may not have one - a change plan is optional.)'}
        {key === 'asserted' && 'The author claims this version stays within the change plan they pinned at line creation. Anyone can challenge this claim within 90 days.'}
        {key === 'disputed' && `Challenged by ${shortAddr(version.challenger)} - waiting for the arbiter to rule.`}
        {key === 'upheld' && `Arbiter ${shortAddr(version.arbiter)} ruled the claim valid.`}
        {key === 'repudiated' && `Arbiter ${shortAddr(version.arbiter)} ruled the claim invalid.`}
      </p>
    </div>
  );
}

export function LineageTree({ line, currentTokenId }: { line: LinePayload | null; currentTokenId: number }) {
  if (!line || !line.has_name_record) return null;
  const versions = [...(line.versions || [])].sort((a, b) => a.token_id - b.token_id);
  if (versions.length === 0) return null;

  return (
    <div className="surface p-5 mb-6">
      <div className="flex items-baseline justify-between mb-3">
        <h3 className="text-sm font-semibold">Line: <span className="mono">{line.name}</span></h3>
        <span className="meta">{versions.length} version{versions.length === 1 ? '' : 's'}</span>
      </div>
      <p className="meta mb-3">
        alias <span className="mono">{shortHash(line.alias)}</span> · controller{' '}
        <span className="mono">{shortAddr(line.controller)}</span> · envelope{' '}
        <span className="mono">{shortHash(line.envelope?.hash)}</span>
        {line.envelope?.pinned_at && line.envelope.pinned_at > 0 ? (
          <> · pinned {safeDate(line.envelope.pinned_at * 1000, 'date')}</>
        ) : (
          <> · envelope <em>not pinned</em></>
        )}
      </p>

      <ol className="space-y-2 mt-4">
        {versions.map((v) => {
          const isCurrent = Number(v.token_id) === Number(currentTokenId);
          const tone =
            v.envelope_status === 'Repudiated' ? 'var(--danger)' :
            v.envelope_status === 'Disputed' ? 'var(--warn)' :
            v.envelope_status === 'Upheld' ? 'var(--ok)' :
            v.within_envelope ? 'var(--ok)' :
            'var(--fg-subtle)';
          return (
            <li
              key={v.token_id}
              className="flex items-baseline justify-between gap-3 py-2 px-3 rounded"
              style={{
                background: isCurrent ? 'var(--bg-subtle)' : 'transparent',
                border: isCurrent ? '1px solid var(--border-strong)' : '1px solid transparent',
              }}
            >
              <div className="flex items-baseline gap-3 min-w-0">
                <span className="mono text-[13px]" style={{ color: 'var(--fg-faint)' }}>#{v.token_id}</span>
                <span className="text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>
                  {v.relation}
                  {v.supersedes ? <> from #{v.supersedes}</> : <> (root)</>}
                </span>
              </div>
              <span className="text-[12.5px]" style={{ color: tone }}>
                {v.within_envelope ? `envelope ${v.envelope_status.toLowerCase()}` : 'out-of-envelope'}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export function ChallengeEnvelopeModal({
  version,
  onClose,
  onSuccess,
}: {
  version: VersionRecord | null;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!version) return null;
  const submit = async () => {
    if (!reason.trim()) {
      setError('Reason required');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      let challengerAddress: string | null = null;
      if (typeof window !== 'undefined') {
        try {
          const wi = window.localStorage.getItem('walletInfo');
          if (wi) {
            const parsed = JSON.parse(wi);
            challengerAddress = parsed?.smartAccount || parsed?.eoaAddress || null;
          }
        } catch {}
      }
      if (!challengerAddress) {
        setError('Cannot determine your wallet - please sign out and back in.');
        setSubmitting(false);
        return;
      }
      const r = await fetch(`${API}/api/versions/${version.token_id}/challenge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reason: reason.trim(),
          challenger_address: challengerAddress,
        }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        throw new Error(e.detail || `HTTP ${r.status}`);
      }
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Challenge failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: 'rgba(0,0,0,0.5)' }}
      onClick={onClose}
    >
      <div className="surface p-6 max-w-lg w-full" onClick={(e) => e.stopPropagation()}>
        <p className="meta mb-2">Challenge envelope claim</p>
        <h2 className="text-lg font-semibold mb-1">Version #{version.token_id} ({version.relation})</h2>
        <p className="text-[13px] mb-4" style={{ color: 'var(--fg-subtle)' }}>
          Envelope <span className="mono">{shortHash(version.envelope_hash)}</span>
        </p>
        <label className="text-[13px] block mb-1" style={{ color: 'var(--fg-subtle)' }}>Reason</label>
        <textarea
          className="input w-full mb-4"
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reason for challenge"
        />
        {error && <p className="text-[13px] mb-3" style={{ color: 'var(--danger)' }}>{error}</p>}
        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="btn" onClick={submit} disabled={submitting}>
            {submitting ? 'Submitting…' : 'Submit challenge'}
          </button>
        </div>
      </div>
    </div>
  );
}
