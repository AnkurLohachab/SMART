'use client';

import { useState } from 'react';
import { DisputeCaseInline } from '@/components/DisputeCaseInline';

// Maps the on-chain identity enum to a user-facing label, factoring in attestation level.
function humanIdentityStatus(s: string | undefined, attestationLevel?: string): string {
  switch (s) {
    case 'Bound':
      if (attestationLevel === 'institutional') return 'Institutionally verified';
      if (attestationLevel === 'self') return 'Self-attested';
      return 'Identity recorded';
    case 'UnboundOptimistic': return 'No identity claim (optimistic)';
    case 'UnboundMissing': return 'No identity claim';
    case 'Disputed': return 'Challenged';
    case 'ResolvedValid': return 'Upheld by panel';
    case 'ResolvedInvalid': return 'Ruled invalid';
    default: return s || '-';
  }
}

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export type GovernanceState =
  | 'clean'
  | 'self_attested'
  | 'unbound'
  | 'review'
  | 'compromised'
  | 'no_history'
  | 'unknown';

export interface ActionRecord {
  action_id: number;
  token_id: number;
  actor: string;
  from_state: string;
  to_state: string;
  to_state_index: number;
  transition: string;
  transition_index: number;
  content_hash: string;
  claim_ref: string;
  issuer_ref: string;
  context_ref: string;
  timestamp: number;
  block_number: number;
  registry_version: number;
  identity_status: string;
  identity_status_index: number;
  challenge_reason: string;
  arbiter: string;
  claim_attestation_level?: 'self' | 'institutional' | 'none' | 'unknown';
}

export interface GovernancePayload {
  state: GovernanceState;
  reason: string | null;
  actions: ActionRecord[];
  bound_count: number;
  disputed_count: number;
  invalid_count: number;
  unbound_count?: number;
  self_attested_count?: number;
  highest_repudiated_to_state: string | null;
  latest_action_id: number | null;
}

export interface ClaimStatus {
  actor: string;
  claim_type: number;
  claim_type_name: string;
  has_claim: boolean;
  claim_ref: string;
  issuer_address: string | null;
  issuer_name: string | null;
  issuer_active: boolean | null;
  valid_from: number | null;
  valid_until: number | null;
  registry_version: number;
  attestation_level?: 'self' | 'institutional';
  attestation_label?: string;
  institution?: string | null;
}

export const REPUDIATION_REASONS = [
  'NoClaim',
  'ExpiredClaim',
  'RevokedClaim',
  'InvalidIssuer',
  'SubjectMismatch',
  'ContextMismatch',
  'SignatureInvalid',
  'RegistryInconsistency',
];

function shortAddr(addr: string | null | undefined): string {
  if (!addr) return '-';
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

function shortHash(h: string | null | undefined): string {
  if (!h) return '-';
  const clean = h.startsWith('0x') ? h.slice(2) : h;
  if (clean === '0'.repeat(64)) return '-';
  return `${clean.slice(0, 8)}…`;
}

function fmtTs(ts: number | null | undefined): string {
  if (!ts) return '-';
  return new Date(ts * 1000).toLocaleString();
}

export function GovernanceStrip({ governance, tokenId }: { governance: GovernancePayload; tokenId: number }) {
  if (!governance || governance.state === 'unknown') return null;

  const palette: Record<Exclude<GovernanceState, 'unknown'>, { fg: string; bg: string; label: string }> = {
    clean: { fg: 'var(--ok)', bg: 'rgba(21, 128, 61, 0.06)', label: 'Institutionally verified' },
    self_attested: { fg: 'var(--warn)', bg: 'rgba(180, 83, 9, 0.07)', label: 'Self-attested only' },
    unbound: { fg: 'var(--warn)', bg: 'rgba(180, 83, 9, 0.07)', label: 'Identity unverified' },
    review: { fg: 'var(--warn)', bg: 'rgba(180, 83, 9, 0.07)', label: 'Under review' },
    compromised: { fg: 'var(--danger)', bg: 'rgba(185, 28, 28, 0.07)', label: 'Identity invalid' },
    no_history: { fg: 'var(--fg-faint)', bg: 'rgba(115, 115, 115, 0.05)', label: 'No history' },
  };
  const p = palette[governance.state];
  if (!p) return null;

  const totalActions =
    governance.bound_count +
    (governance.unbound_count || 0) +
    (governance.disputed_count || 0) +
    (governance.invalid_count || 0);
  const counters = totalActions > 0 ? (
    <span className="meta">{totalActions} step{totalActions === 1 ? '' : 's'}</span>
  ) : null;

  return (
    <div className="mb-8 px-5 py-4 rounded-md border" style={{ borderColor: p.fg, background: p.bg }}>
      <div className="flex items-baseline gap-3 mb-1 flex-wrap">
        <span className="text-[13px] font-medium uppercase tracking-wide" style={{ color: p.fg }}>
          {p.label}
        </span>
        {governance.state !== 'no_history' && counters}
      </div>

      {(governance.state === 'review' ||
        governance.state === 'compromised' ||
        governance.state === 'unbound' ||
        governance.state === 'self_attested') && governance.reason && (
        <p className="text-[13px] mt-1" style={{ color: 'var(--fg-muted)' }}>
          {governance.reason}
        </p>
      )}
    </div>
  );
}

export function IdentityAttribution({ action }: { action: ActionRecord }) {
  const status = action.identity_status;
  const issuerAddr = action.issuer_ref && action.issuer_ref !== '0'.repeat(64)
    ? `0x${action.issuer_ref.slice(-40)}`
    : null;
  const level = action.claim_attestation_level || 'unknown';

  let attribution: React.ReactNode;
  let tone = 'var(--fg-subtle)';

  if (status === 'Bound') {
    if (level === 'self') {
      attribution = <>self-attested · institutional verification pending</>;
      tone = 'var(--warn)';
    } else if (level === 'institutional') {
      attribution = <>attested by issuer <span className="mono">{shortAddr(issuerAddr)}</span></>;
      tone = 'var(--ok)';
    } else {
      attribution = <>attested by <span className="mono">{shortAddr(issuerAddr)}</span></>;
    }
  } else if (status === 'UnboundOptimistic' || status === 'UnboundMissing') {
    attribution = <>no identity attestation on file</>;
    tone = 'var(--warn)';
  } else if (status === 'Disputed') {
    attribution = <>attestation under review</>;
    tone = 'var(--warn)';
  } else if (status === 'ResolvedInvalid') {
    attribution = <>attestation invalidated</>;
    tone = 'var(--danger)';
  } else if (status === 'ResolvedValid') {
    attribution = <>attestation upheld</>;
    tone = 'var(--ok)';
  } else {
    attribution = <>-</>;
  }

  return (
    <div className="text-[13px]">
      <span style={{ color: 'var(--fg-muted)' }}>
        {action.transition} by <span className="mono">{shortAddr(action.actor)}</span>
      </span>
      <span style={{ color: tone }}> · {attribution}</span>
    </div>
  );
}

export function ClaimStatusCard({
  claim,
  showUpgradeLink = true,
}: {
  claim: ClaimStatus | null;
  showUpgradeLink?: boolean;
}) {
  if (!claim) return null;
  const expiresLabel = claim.valid_until
    ? new Date(claim.valid_until * 1000).toLocaleDateString()
    : 'No expiry recorded';
  const issuedLabel = claim.valid_from ? new Date(claim.valid_from * 1000).toLocaleDateString() : '-';
  const isSelf = claim.attestation_level === 'self';

  return (
    <div
      className="surface p-5"
      style={isSelf ? { borderColor: 'var(--warn)' } : undefined}
    >
      <p className="meta mb-2">Your identity claim</p>
      {claim.has_claim ? (
        <>
          <div className="text-[15px] mb-1">
            <span className="font-medium">{claim.claim_type_name}</span>
            <span style={{ color: 'var(--fg-subtle)' }}> attestation</span>
            <span
              className="ml-2 text-[12px] px-2 py-0.5 rounded"
              style={{
                color: isSelf ? 'var(--warn)' : 'var(--ok)',
                border: `1px solid ${isSelf ? 'var(--warn)' : 'var(--ok)'}`,
              }}
            >
              {isSelf ? 'self-attested' : 'institutional'}
            </span>
          </div>
          <div className="text-[13px]" style={{ color: 'var(--fg-muted)' }}>
            {claim.institution ? (
              <>{claim.institution} · </>
            ) : null}
            Issued by <span className="mono">{shortAddr(claim.issuer_address)}</span> ·{' '}
            {claim.issuer_active ? 'issuer active' : 'issuer inactive'}
          </div>
          <div className="text-[13px] mt-1" style={{ color: 'var(--fg-subtle)' }}>
            From {issuedLabel} · expires {expiresLabel}
          </div>
          {isSelf && showUpgradeLink && (
            <div className="text-[13px] mt-3 pt-3 border-t" style={{ borderColor: 'var(--border)' }}>
              <a href="/profile/identity" className="link" style={{ color: 'var(--warn)' }}>
                Request institutional attestation
              </a>
            </div>
          )}
        </>
      ) : (
        <>
          <div className="text-[15px] mb-1" style={{ color: 'var(--warn)' }}>
            No {claim.claim_type_name} claim on file
          </div>
          {showUpgradeLink && (
            <div className="mt-3">
              <a href="/profile/identity" className="link" style={{ color: 'var(--warn)' }}>
                Request a claim
              </a>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function ActionList({
  actions,
  showToken = false,
  onChallenge,
}: {
  actions: ActionRecord[];
  showToken?: boolean;
  onChallenge?: (action: ActionRecord) => void;
}) {
  if (!actions || actions.length === 0) {
    return <p className="text-[13.5px]" style={{ color: 'var(--fg-subtle)' }}>No actions.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-[13px]">
        <thead>
          <tr style={{ color: 'var(--fg-subtle)' }}>
            <th className="text-left py-2 pr-4 font-medium">#</th>
            {showToken && <th className="text-left py-2 pr-4 font-medium">token</th>}
            <th className="text-left py-2 pr-4 font-medium">transition</th>
            <th className="text-left py-2 pr-4 font-medium">actor</th>
            <th className="text-left py-2 pr-4 font-medium">identity</th>
            <th className="text-left py-2 pr-4 font-medium">when</th>
            {onChallenge && <th></th>}
          </tr>
        </thead>
        <tbody>
          {actions.map((a) => {
            const tone =
              a.identity_status === 'Bound' || a.identity_status === 'ResolvedValid'
                ? 'var(--ok)'
                : a.identity_status === 'Disputed'
                ? 'var(--warn)'
                : a.identity_status === 'ResolvedInvalid'
                ? 'var(--danger)'
                : 'var(--fg-subtle)';
            const challengeable =
              onChallenge &&
              (a.identity_status === 'Bound' ||
                a.identity_status === 'UnboundOptimistic' ||
                a.identity_status === 'UnboundMissing');
            return (
              <tr key={a.action_id} className="border-t" style={{ borderColor: 'var(--border)' }}>
                <td className="py-2 pr-4 mono">{a.action_id}</td>
                {showToken && <td className="py-2 pr-4 mono">#{a.token_id}</td>}
                <td className="py-2 pr-4">
                  {a.transition}
                  {a.from_state !== a.to_state && (
                    <span style={{ color: 'var(--fg-faint)' }}> · {a.from_state} to {a.to_state}</span>
                  )}
                </td>
                <td className="py-2 pr-4 mono">{shortAddr(a.actor)}</td>
                <td className="py-2 pr-4" style={{ color: tone }}>
                  {humanIdentityStatus(a.identity_status, a.claim_attestation_level)}
                  {a.challenge_reason !== 'NoClaim' && a.identity_status !== 'Bound' && (
                    <span style={{ color: 'var(--fg-faint)' }}> · {a.challenge_reason}</span>
                  )}
                </td>
                <td className="py-2 pr-4" style={{ color: 'var(--fg-subtle)' }}>{fmtTs(a.timestamp)}</td>
                {onChallenge && (
                  <td className="py-2 pr-4 text-right">
                    {challengeable ? (
                      <button onClick={() => onChallenge(a)} className="link" style={{ color: 'var(--warn)' }}>
                        challenge
                      </button>
                    ) : (
                      <span style={{ color: 'var(--fg-faint)' }}>-</span>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
      {actions
        .filter((a) =>
          a.identity_status === 'Disputed' ||
          a.identity_status === 'ResolvedValid' ||
          a.identity_status === 'ResolvedInvalid',
        )
        .map((a) => (
          <DisputeCaseInline key={`case-${a.action_id}`} actionId={a.action_id} />
        ))}
    </div>
  );
}

export function ChallengeModal({
  action,
  onClose,
  onSuccess,
}: {
  action: ActionRecord | null;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [reason, setReason] = useState<string>(REPUDIATION_REASONS[0]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!action) return null;

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      // challenger_address lets the backend SoD guard block self-challenges.
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
        setError('Wallet not found. Please sign out and back in.');
        setSubmitting(false);
        return;
      }
      const r = await fetch(`${API}/api/actions/${action.action_id}/challenge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reason,
          ...(challengerAddress ? { challenger_address: challengerAddress } : {}),
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
      <div
        className="surface p-6 max-w-lg w-full"
        onClick={(e) => e.stopPropagation()}
      >
        <p className="meta mb-2">Challenge action #{action.action_id}</p>
        <h2 className="text-lg font-semibold mb-4">{action.transition} on token #{action.token_id}</h2>

        <label className="text-[13px] block mb-1" style={{ color: 'var(--fg-subtle)' }}>Reason</label>
        <select
          className="input mb-4 w-full"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        >
          {REPUDIATION_REASONS.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>

        {error && (
          <p className="text-[13px] mb-3" style={{ color: 'var(--danger)' }}>{error}</p>
        )}

        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="btn" onClick={submit} disabled={submitting}>
            {submitting ? 'Submitting…' : 'Challenge'}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ResolveModal({
  action,
  onClose,
  onSuccess,
  resolveFetcher,
}: {
  action: ActionRecord | null;
  onClose: () => void;
  onSuccess: () => void;
  resolveFetcher?: (action_id: number, final_status: 'ResolvedValid' | 'ResolvedInvalid') => Promise<void>;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!action) return null;

  const submit = async (final_status: 'ResolvedValid' | 'ResolvedInvalid') => {
    setSubmitting(true);
    setError(null);
    try {
      if (resolveFetcher) {
        await resolveFetcher(action.action_id, final_status);
      } else {
        const r = await fetch(`${API}/api/actions/${action.action_id}/resolve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ final_status }),
        });
        if (!r.ok) {
          const e = await r.json().catch(() => ({}));
          throw new Error(e.detail || `HTTP ${r.status}`);
        }
      }
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Resolve failed');
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
        <p className="meta mb-2">Resolve action #{action.action_id}</p>
        <h2 className="text-lg font-semibold mb-2">{action.transition} on token #{action.token_id}</h2>
        <p className="text-[13px] mb-4" style={{ color: 'var(--fg-subtle)' }}>
          Challenged: <span className="mono">{action.challenge_reason}</span>
        </p>

        {error && <p className="text-[13px] mb-3" style={{ color: 'var(--danger)' }}>{error}</p>}

        <div className="flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose} disabled={submitting}>Cancel</button>
          <button
            className="btn-ghost"
            style={{ borderColor: 'var(--ok)', color: 'var(--ok)' }}
            onClick={() => submit('ResolvedValid')}
            disabled={submitting}
          >
            Uphold claim
          </button>
          <button
            className="btn"
            style={{ background: 'var(--danger)', borderColor: 'var(--danger)' }}
            onClick={() => submit('ResolvedInvalid')}
            disabled={submitting}
          >
            Invalidate claim
          </button>
        </div>
      </div>
    </div>
  );
}
