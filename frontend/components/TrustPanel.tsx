'use client';

import type { GovernancePayload } from '@/components/Governance';
import type { LinePayload, VersionRecord } from '@/components/Lineage';

interface Props {
  governance: GovernancePayload | null | undefined;
  line: LinePayload | null;
  version: VersionRecord | null;
}

const STATE_LABEL: Record<string, { text: string; tone: string; tip: string }> = {
  clean: {
    text: 'Institutionally verified',
    tone: 'text-emerald-700',
    tip: 'Every on-chain action on this card was signed by an actor whose institutional credentials were verified at action time. No challenges have been raised.',
  },
  self_attested: {
    text: 'Self-attested only',
    tone: 'text-amber-700',
    tip: 'Actions are bound to identity claims, but those claims are self-attested rather than institutionally verified. Any reader can challenge them.',
  },
  unbound: {
    text: 'Identity unverified',
    tone: 'text-amber-700',
    tip: 'At least one action on this card was performed by an address with no active identity claim on chain. The lifecycle history is intact, but the actor identity is unverified for those steps.',
  },
  review: {
    text: 'Under review',
    tone: 'text-amber-700',
    tip: 'A challenge has been raised against an action on this card. Awaiting arbiter resolution by a 2-of-N panel (Reviewer + Publisher).',
  },
  compromised: {
    text: 'Identity invalid',
    tone: 'text-red-700',
    tip: 'An arbiter ruled that an actor\'s identity claim was invalid for the action they performed. Trust is withdrawn from that step.',
  },
  no_history: {
    text: 'No on-chain history',
    tone: 'text-gray-500',
    tip: 'No actions recorded for this token.',
  },
};

const ENVELOPE_LABEL: Record<string, { text: string; tone: string; tip: string }> = {
  none: {
    text: 'No change plan',
    tone: 'text-gray-600',
    tip: 'No predetermined-change plan for this version.',
  },
  asserted: {
    text: 'Within change plan',
    tone: 'text-emerald-700',
    tip: 'Author claims this version stays within the pinned change plan. Challengeable for 90 days.',
  },
  disputed: {
    text: 'Change-plan claim challenged',
    tone: 'text-amber-700',
    tip: 'Someone has challenged the author\'s claim that this version stays within the change plan. Awaiting arbiter ruling.',
  },
  upheld: {
    text: 'Change-plan claim upheld',
    tone: 'text-emerald-700',
    tip: 'The arbiter ruled that this version does stay within the change plan.',
  },
  repudiated: {
    text: 'Change-plan claim invalid',
    tone: 'text-red-700',
    tip: 'The arbiter ruled that this version does NOT stay within the pinned change plan.',
  },
};

function envelopeKey(version: VersionRecord | null): keyof typeof ENVELOPE_LABEL {
  if (!version) return 'none';
  if (!version.within_envelope) return 'none';
  const s = (version.envelope_status || '').toLowerCase();
  if (s === 'asserted') return 'asserted';
  if (s === 'disputed') return 'disputed';
  if (s === 'upheld') return 'upheld';
  if (s === 'repudiated') return 'repudiated';
  return 'asserted';
}

function shortHex(s: string | undefined | null, n = 6): string {
  if (!s) return '-';
  const clean = s.startsWith('0x') ? s.slice(2) : s;
  if (clean.length <= n * 2) return s;
  return `${s.slice(0, 2 + n)}…${s.slice(-n)}`;
}

function HelpIcon({ tip }: { tip: string }) {
  return (
    <span className="relative inline-flex group">
      <span
        tabIndex={0}
        aria-label={tip}
        className="inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold cursor-help select-none focus:outline-none"
        style={{ background: 'var(--bg-subtle)', color: 'var(--fg-muted)', border: '1px solid var(--border)' }}
      >
        ?
      </span>
      <span
        role="tooltip"
        className="pointer-events-none absolute right-0 top-full mt-2 w-64 z-50 rounded-md border p-2.5 text-[12.5px] leading-snug opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity"
        style={{
          background: 'var(--bg)',
          color: 'var(--fg)',
          borderColor: 'var(--border)',
          boxShadow: '0 6px 24px rgba(0,0,0,0.12)',
        }}
      >
        {tip}
      </span>
    </span>
  );
}

export function TrustPanel({ governance, line, version }: Props) {
  const totalActions =
    (governance?.bound_count || 0) +
    (governance?.unbound_count || 0) +
    (governance?.disputed_count || 0) +
    (governance?.invalid_count || 0);

  const challengeCount =
    (governance?.disputed_count || 0) +
    (governance?.invalid_count || 0) +
    ((governance?.actions || []).filter((a: any) => a.identity_status === 'ResolvedValid').length);
  const revisionCount = (governance?.actions || []).filter(
    (a: any) => a.transition === 'Revise',
  ).length;

  const identityKey = (governance?.state as keyof typeof STATE_LABEL) || 'no_history';
  const identity = STATE_LABEL[identityKey] || STATE_LABEL.no_history;

  const envKey = envelopeKey(version);
  const envelope = ENVELOPE_LABEL[envKey];

  const identityTip = identity.tip;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
      <h3 className="text-sm font-semibold text-gray-900">More info</h3>

      <Row
        label="Identity"
        value={identity.text}
        tone={identity.tone}
        tip={identityTip}
        sub={
          totalActions > 0
            ? `${totalActions} step${totalActions === 1 ? '' : 's'} on chain` +
              (challengeCount > 0
                ? ` · ${challengeCount} challenge${challengeCount === 1 ? '' : 's'}`
                : '') +
              (revisionCount > 0
                ? ` · ${revisionCount} revision${revisionCount === 1 ? '' : 's'}`
                : '')
            : undefined
        }
      />

      <Row
        label="Change plan"
        value={envelope.text}
        tone={envelope.tone}
        tip={envelope.tip}
        sub={
          version
            ? version.supersedes
              ? `${version.relation} · supersedes #${version.supersedes}`
              : `${version.relation} · root of line`
            : undefined
        }
      />

      {line?.has_name_record && (
        <Row
          label="Line"
          value={line.name}
          tone="text-gray-700"
          tip={`Versions of this model are recorded under the slug "${line.name}". The first claimant owns the name forever and is the only party allowed to mint future versions.`}
          sub={`${(line.versions || []).length} version${(line.versions || []).length === 1 ? '' : 's'}`}
          mono
        />
      )}
    </div>
  );
}

function Row({
  label,
  value,
  tone,
  tip,
  sub,
  mono,
}: {
  label: string;
  value: string;
  tone: string;
  tip: string;
  sub?: string;
  mono?: boolean;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[12px] uppercase tracking-wide text-gray-500 flex items-center gap-1.5">
          {label}
          <HelpIcon tip={tip} />
        </span>
        <span
          className={`text-[13px] font-medium ${tone} ${mono ? 'font-mono' : ''} text-right truncate max-w-[60%]`}
        >
          {value}
        </span>
      </div>
      {sub && (
        <p className="text-[11.5px] text-gray-500 mt-0.5">{sub}</p>
      )}
    </div>
  );
}
