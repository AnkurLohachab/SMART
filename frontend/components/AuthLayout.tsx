'use client';

import { ReactNode } from 'react';
import Link from 'next/link';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
  switchText?: string;
  switchLink?: string;
  switchLinkText?: string;
}

export function AuthLayout({
  children,
  title,
  subtitle,
  switchText,
  switchLink,
  switchLinkText,
}: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex">
      <aside
        className="hidden lg:flex lg:w-5/12 flex-col justify-between p-12 border-r"
        style={{ borderColor: 'var(--border)', background: 'var(--bg-subtle)' }}
      >
        <Link href="/" className="text-[15px] font-semibold tracking-tight">
          SMART
        </Link>

        <div className="max-w-md">
          <p className="meta mb-4">SMART</p>
          <h1 className="text-3xl xl:text-4xl font-semibold tracking-tight leading-[1.1]">
            Documentation, governance, and audit for clinical AI.
          </h1>
          <p className="mt-5 text-[15px] leading-[1.6]" style={{ color: 'var(--fg-muted)' }}>
            Authenticate with your registered UUID and role to continue.
          </p>
        </div>

        <p className="meta">© {new Date().getFullYear()} · MIT licensed</p>
      </aside>

      <main className="flex-1 flex flex-col">
        <div className="px-6 py-5">
          <Link href="/" className="text-[13px] link-muted">
            Back to home
          </Link>
        </div>

        <div className="flex-1 flex items-center justify-center px-6 pb-12">
          <div className="w-full max-w-md">
            <div className="lg:hidden mb-8 text-center">
              <Link href="/" className="text-[15px] font-semibold tracking-tight">
                SMART
              </Link>
            </div>

            <div className="mb-8">
              <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
              {subtitle && (
                <p className="mt-2 text-[14.5px]" style={{ color: 'var(--fg-muted)' }}>
                  {subtitle}
                </p>
              )}
            </div>

            <div className="surface p-7">{children}</div>

            {switchText && switchLink && switchLinkText && (
              <p className="mt-5 text-center text-[13.5px]" style={{ color: 'var(--fg-subtle)' }}>
                {switchText}{' '}
                <Link href={switchLink} className="link">
                  {switchLinkText}
                </Link>
              </p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
