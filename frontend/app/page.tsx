'use client';

import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';

export default function HomePage() {
  const { isAuthenticated } = useAuth();

  return (
    <div>
      <section className="border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="container-app pt-20 pb-24 lg:pt-28 lg:pb-32">
          <p className="meta mb-6">SMART</p>
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-semibold leading-[1.04] max-w-5xl">
            Structured, Meaningful, Auditable, Responsible, and Transparent documentation for clinical AI.
          </h1>
          <div className="mt-10 flex flex-wrap items-center gap-3">
            {isAuthenticated ? (
              <>
                <Link href="/create" className="btn btn-primary">
                  Create model card
                </Link>
                <Link href="/gallery" className="btn btn-secondary">
                  Browse registry
                </Link>
              </>
            ) : (
              <>
                <Link href="/register" className="btn btn-primary">
                  Get started
                </Link>
                <Link href="/auth" className="btn btn-secondary">
                  Sign in
                </Link>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="container-app py-20 lg:py-24">
          <header className="mb-14">
            <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight">
              What SMART provides.
            </h2>
          </header>

          <div className="grid-cards">
            <Feature
              n="01"
              eyebrow="Template"
              title="Nothing to invent."
              body="Seven structured sections, schema-validated."
            />
            <Feature
              n="02"
              eyebrow="Cohorts"
              title="Trace every patient."
              body="Populations resolve to real OMOP concept sets. Reviewers can see who the model trained on."
            />
            <Feature
              n="03"
              eyebrow="Lifecycle"
              title="Right step, right role."
              body="Authoring, review, and publication are separate roles, enforced on-chain."
            />
            <Feature
              n="04"
              eyebrow="Provenance"
              title="Authorship stays attached."
              body="Each card is soulbound to its creator. Lineage and revisions remain bound to the original address."
            />
            <Feature
              n="05"
              eyebrow="Audit"
              title="Anyone can verify."
              body="Recompute a card's SHA-256 and check it against the ledger. No special tooling needed."
            />
            <Feature
              n="06"
              eyebrow="Storage"
              title="Your data stays yours."
              body="Your data stays on your infrastructure. Only the hash and pointer go on-chain."
            />
          </div>
        </div>
      </section>

      <section className="border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="container-app py-20 lg:py-24">
          <header className="mb-14">
            <h2 className="text-3xl sm:text-4xl font-semibold tracking-tight">
              From form to published card.
            </h2>
          </header>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-px" style={{ background: 'var(--border)' }}>
            <Step n="01" title="Author" body="Write the card in one structured form. Submit for review." />
            <Step n="02" title="Review" body="An authenticator approves, rejects, or asks for revisions." />
            <Step n="03" title="Publish" body="Publish to the registry. Anyone can verify the content later." />
          </div>
        </div>
      </section>

      <section>
        <div className="container-app py-20 lg:py-24">
          <div className="surface p-10 lg:p-14 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-8">
            <div>
              <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight">
                Runs locally.
              </h2>
              <p className="mt-3" style={{ color: 'var(--fg-muted)' }}>
                <span className="mono">docker compose up</span>
              </p>
            </div>
            <Link href={isAuthenticated ? '/create' : '/register'} className="btn btn-primary">
              {isAuthenticated ? 'Create card' : 'Get started'}
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}

function Feature({
  n,
  eyebrow,
  title,
  body,
}: {
  n: string;
  eyebrow: string;
  title: string;
  body: string;
}) {
  return (
    <article className="surface surface-hover p-7">
      <div className="flex items-baseline justify-between mb-5">
        <span className="meta">{eyebrow}</span>
        <span className="mono" style={{ color: 'var(--fg-faint)' }}>
          {n}
        </span>
      </div>
      <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      <p className="mt-2.5 text-[14.5px] leading-[1.6]" style={{ color: 'var(--fg-muted)' }}>
        {body}
      </p>
    </article>
  );
}

function Step({ n, title, body }: { n: string; title: string; body: string }) {
  return (
    <div className="p-8 lg:p-10" style={{ background: 'var(--bg)' }}>
      <div className="flex items-baseline gap-4">
        <span className="mono" style={{ color: 'var(--fg-faint)' }}>
          {n}
        </span>
        <h3 className="text-lg font-semibold tracking-tight">{title}</h3>
      </div>
      <p className="mt-3 text-[14.5px]" style={{ color: 'var(--fg-muted)' }}>
        {body}
      </p>
    </div>
  );
}
