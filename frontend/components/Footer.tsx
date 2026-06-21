'use client';

import Link from 'next/link';

export function Footer() {
  return (
    <footer className="border-t mt-24" style={{ borderColor: 'var(--border)' }}>
      <div className="container-app py-10">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
          <div className="md:col-span-5">
            <p className="text-sm font-semibold tracking-tight">SMART</p>
            <p
              className="mt-2 text-[13.5px] leading-[1.6] max-w-md"
              style={{ color: 'var(--fg-subtle)' }}
            >
              Documentation, governance, and audit for clinical AI. Open source under the MIT license.
            </p>
          </div>

          <nav className="md:col-span-3">
            <p className="meta mb-3">Explore</p>
            <ul className="space-y-2 text-[13.5px]">
              <li>
                <Link href="/gallery" className="link-muted">
                  Registry
                </Link>
              </li>
              <li>
                <Link href="/workflow" className="link-muted">
                  Workflow
                </Link>
              </li>
              <li>
                <Link href="/create" className="link-muted">
                  Create
                </Link>
              </li>
            </ul>
          </nav>

          <nav className="md:col-span-4">
            <p className="meta mb-3">Resources</p>
            <ul className="space-y-2 text-[13.5px]">
              <li>
                <a
                  href="https://pypi.org/project/smart-model-card/"
                  target="_blank"
                  rel="noreferrer"
                  className="link-muted"
                >
                  smart-model-card on PyPI
                </a>
              </li>
              <li>
                <a
                  href="https://www.ohdsi.org/data-standardization/"
                  target="_blank"
                  rel="noreferrer"
                  className="link-muted"
                >
                  OHDSI / OMOP CDM
                </a>
              </li>
              <li>
                <a href="/" className="link-muted">
                  About the framework
                </a>
              </li>
            </ul>
          </nav>
        </div>

        <div
          className="mt-10 pt-6 border-t flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3"
          style={{ borderColor: 'var(--border)' }}
        >
          <p className="meta">© {new Date().getFullYear()} SMART</p>
          <p className="meta">MIT licensed</p>
        </div>
      </div>
    </footer>
  );
}
