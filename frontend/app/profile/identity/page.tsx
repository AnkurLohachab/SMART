'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { ClaimStatusCard, type ClaimStatus } from '@/components/Governance';

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

const CLAIM_TYPE_FOR_ROLE: Record<string, number[]> = {
  AIDeveloper: [1],
  Reviewer: [2],
  Authenticator: [2],   // legacy alias
  Publisher: [3],
  Admin: [1, 3],
  Reader: [],
};

export default function IdentityPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, uuid, role } = useAuth();
  const [claims, setClaims] = useState<Record<number, ClaimStatus | null>>({});
  const [requests, setRequests] = useState<ClaimRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [institution, setInstitution] = useState('');
  const [supportingUrl, setSupportingUrl] = useState('');
  const [note, setNote] = useState('');
  const [targetClaimType, setTargetClaimType] = useState<number | null>(null);
  const [eoaAddress, setEoaAddress] = useState<string | null>(null);
  // All roles the user holds; identity claims are per-role.
  const [userRoles, setUserRoles] = useState<string[]>([]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.push('/auth');
  }, [isAuthenticated, isLoading, router]);

  // Claims are issued on chain against the user's EOA, not the per-role smart account.
  useEffect(() => {
    if (!uuid) return;
    (async () => {
      try {
        const r = await fetch(`${API}/api/user/${uuid}`);
        if (r.ok) {
          const d = await r.json();
          setEoaAddress(d.eoa_address || null);
          setUserRoles(d.roles || []);
        }
      } catch {}
    })();
  }, [uuid]);

  const claimTypes = Array.from(
    new Set(
      (userRoles.length ? userRoles : (role ? [role] : []))
        .flatMap((r) => CLAIM_TYPE_FOR_ROLE[r] || []),
    ),
  );

  useEffect(() => {
    if (claimTypes[0] && targetClaimType === null) setTargetClaimType(claimTypes[0]);
  }, [claimTypes, targetClaimType]);

  const reload = async () => {
    if (!eoaAddress || !uuid) return;
    setLoading(true);
    try {
      const claimResults = await Promise.all(
        claimTypes.map(async (ct) => {
          const r = await fetch(`${API}/api/identity/claim/${eoaAddress}?claim_type=${ct}`);
          if (!r.ok) return [ct, null] as [number, ClaimStatus | null];
          return [ct, (await r.json()) as ClaimStatus] as [number, ClaimStatus | null];
        })
      );
      setClaims(Object.fromEntries(claimResults));

      const rr = await fetch(`${API}/api/identity/claim-requests/mine?uuid=${uuid}`);
      if (rr.ok) {
        const dd = await rr.json();
        setRequests(dd.requests || []);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (eoaAddress && uuid) reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eoaAddress, uuid, role]);

  const submitRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!institution.trim() || targetClaimType === null) {
      toast.error('Institution name is required');
      return;
    }
    setSubmitting(true);
    try {
      const r = await fetch(`${API}/api/identity/claim-requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          uuid,
          claim_type: targetClaimType,
          institution: institution.trim(),
          supporting_url: supportingUrl.trim() || null,
          note: note.trim() || null,
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      toast.success('Request submitted');
      setInstitution('');
      setSupportingUrl('');
      setNote('');
      reload();
    } catch (err: any) {
      toast.error(err.message || 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  if (isLoading || loading) {
    return (
      <main className="container-app py-16">
        <div className="surface h-32 animate-pulse" />
      </main>
    );
  }

  if (claimTypes.length === 0) {
    return (
      <main className="container-app py-10 lg:py-14">
        <h1 className="text-3xl lg:text-4xl font-semibold tracking-tight">Institutional verification</h1>
        <p className="mt-3 max-w-2xl" style={{ color: 'var(--fg-muted)' }}>
          Your role does not require institutional verification. It applies to roles that
          perform on-chain transitions (AI Developer, Reviewer, Publisher, Admin).
        </p>
        <Link href="/profile" className="link-muted text-[13px] mt-6 inline-block">Back to profile</Link>
      </main>
    );
  }

  const pendingForType = (ct: number) =>
    requests.find((r) => r.claim_type === ct && r.status === 'pending');

  return (
    <main className="container-app py-10 lg:py-14">
      <div className="mb-10">
        <p className="meta mb-3">Profile</p>
        <h1 className="text-3xl lg:text-4xl font-semibold tracking-tight">Institutional verification</h1>
        <p className="mt-2 max-w-2xl text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>
          Submit institutional credentials so an admin can elevate your on-chain
          claim from <strong>self-attested</strong> to <strong>institutional</strong>.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-10">
        {claimTypes.map((ct) => (
          <ClaimStatusCard key={ct} claim={claims[ct]} showUpgradeLink={false} />
        ))}
      </div>

      {(() => {
        const eligibleTypes = claimTypes;
        const allInstitutional = claimTypes.every(
          (ct) => claims[ct]?.attestation_level === 'institutional',
        );
        return (
      <section className="surface p-6 mb-10">
        <div className="flex items-baseline justify-between mb-4 gap-2 flex-wrap">
          <h2 className="text-base font-semibold">
            {allInstitutional ? 'Update institutional attestation' : 'Request institutional attestation'}
          </h2>
          {allInstitutional && (
            <span
              className="text-[12px] px-2 py-0.5 rounded border"
              style={{ color: 'var(--ok)', borderColor: 'var(--ok)' }}
            >
              All current claims institutional
            </span>
          )}
        </div>

        {allInstitutional && (
          <p className="text-[13px] mb-4" style={{ color: 'var(--fg-muted)' }}>
            You're already institutionally verified for every required role. Submit
            below only if you need to switch institutions, refresh the attestation,
            or correct existing details. The new claim is appended on chain - older
            claims stay in the audit trail.
          </p>
        )}

        <form onSubmit={submitRequest} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="meta block mb-1.5">Claim type</label>
            <select
              className="input w-full"
              value={
                targetClaimType !== null && eligibleTypes.includes(targetClaimType)
                  ? targetClaimType
                  : (eligibleTypes[0] ?? '')
              }
              onChange={(e) => setTargetClaimType(Number(e.target.value))}
              disabled={submitting}
            >
              {eligibleTypes.map((ct) => {
                const pending = pendingForType(ct);
                const ctype = claims[ct]?.claim_type_name || `claim_type=${ct}`;
                const isInstit = claims[ct]?.attestation_level === 'institutional';
                return (
                  <option key={ct} value={ct} disabled={!!pending}>
                    {ctype}
                    {pending ? ' (pending)' : isInstit ? ' (institutional · update)' : ''}
                  </option>
                );
              })}
            </select>
          </div>

          <div>
            <label className="meta block mb-1.5">Institution *</label>
            <input
              className="input w-full"
              value={institution}
              onChange={(e) => setInstitution(e.target.value)}
              placeholder="e.g., St Mary's Hospital, NHS Trust"
              required
              disabled={submitting}
            />
          </div>

          <div className="md:col-span-2">
            <label className="meta block mb-1.5">Supporting URL (optional)</label>
            <input
              className="input w-full"
              value={supportingUrl}
              onChange={(e) => setSupportingUrl(e.target.value)}
              placeholder="https://… profile, license, or affiliation page"
              disabled={submitting}
            />
          </div>

          <div className="md:col-span-2">
            <label className="meta block mb-1.5">Note (optional)</label>
            <textarea
              className="input w-full"
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Anything an admin should know to verify your institutional affiliation."
              disabled={submitting}
            />
          </div>

          <div className="md:col-span-2">
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Submitting…' : 'Submit request'}
            </button>
          </div>
        </form>
      </section>
        );
      })()}

      <section className="surface overflow-hidden">
        <header className="flex items-baseline justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <h2 className="text-base font-semibold tracking-tight">Request history</h2>
          <span className="meta">{requests.length} total</span>
        </header>
        {requests.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <p className="meta mb-2">Nothing yet</p>
            <p className="text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>
              No requests yet.
            </p>
          </div>
        ) : (
          <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {requests.map((r) => (
              <li key={r.request_id} className="px-6 py-4">
                <div className="flex items-baseline justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <p className="text-[14px] font-medium">
                      {r.claim_type_name || `claim_type=${r.claim_type}`} · {r.institution}
                    </p>
                    <p className="text-[12.5px] mt-1" style={{ color: 'var(--fg-subtle)' }}>
                      {new Date(r.created_at).toLocaleString()}
                      {r.resolved_at && (
                        <>
                          {' · '}resolved {new Date(r.resolved_at).toLocaleString()}
                        </>
                      )}
                    </p>
                  </div>
                  <span
                    className="text-[12px] px-2 py-0.5 rounded border"
                    style={{
                      color:
                        r.status === 'approved'
                          ? 'var(--ok)'
                          : r.status === 'rejected'
                          ? 'var(--danger)'
                          : 'var(--warn)',
                      borderColor:
                        r.status === 'approved'
                          ? 'var(--ok)'
                          : r.status === 'rejected'
                          ? 'var(--danger)'
                          : 'var(--warn)',
                    }}
                  >
                    {r.status}
                  </span>
                </div>
                {r.status === 'rejected' && r.rejection_reason && (
                  <p className="text-[13px] mt-2" style={{ color: 'var(--fg-muted)' }}>
                    Reason: {r.rejection_reason}
                  </p>
                )}
                {r.status === 'approved' && r.on_chain_tx_hash && (
                  <p className="text-[12px] mt-2 mono truncate" style={{ color: 'var(--fg-faint)' }}>
                    tx {r.on_chain_tx_hash}
                  </p>
                )}
                {r.note && (
                  <p className="text-[13px] mt-2" style={{ color: 'var(--fg-subtle)' }}>
                    {r.note}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
