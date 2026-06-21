'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';

export function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const pathname = usePathname();
  const { isAuthenticated, isLoading, uuid, role, logout, getRoleLabel } = useAuth();
  const userMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMobileOpen(false);
    setUserMenuOpen(false);
  }, [pathname]);

  const dashboardPath =
    role === 'AIDeveloper'
      ? '/dashboard/developer'
      : role === 'Reviewer' || role === 'Authenticator'
        ? '/dashboard/authenticator'
        : role === 'Publisher'
          ? '/dashboard/publisher'
          : role === 'Admin'
            ? '/dashboard/admin'
            : '/dashboard/developer';

  const canCreate = role === 'AIDeveloper' || role === 'Admin';
  const workflowLabel =
    role === 'AIDeveloper'
      ? 'Tasks'
      : role === 'Reviewer' || role === 'Authenticator' || role === 'Publisher'
        ? 'Review'
        : 'Workflow';

  const navItems: Array<{
    href: string;
    label: string;
    protected?: boolean;
    developerOnly?: boolean;
  }> = [
    { href: '/gallery', label: 'Registry' },
    { href: dashboardPath, label: 'Dashboard', protected: true },
    { href: '/create', label: 'Create', protected: true, developerOnly: true },
    { href: '/workflow', label: workflowLabel, protected: true },
  ];

  const isActive = (href: string) =>
    pathname === href || (href.includes('/dashboard/') && pathname?.startsWith('/dashboard/'));

  const visibleItems = navItems.filter((item) => {
    if (item.protected && !isAuthenticated) return false;
    if (item.developerOnly && !canCreate) return false;
    return true;
  });

  return (
    <header
      className="sticky top-0 z-40 backdrop-blur-md border-b"
      style={{ borderColor: 'var(--border)', background: 'rgba(255,255,255,0.85)' }}
    >
      <nav className="container-app">
        <div className="flex h-16 items-center justify-between">
          <div className="flex items-center gap-12">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="text-[15px] font-semibold tracking-tight">SMART</span>
              <span className="meta hidden sm:inline" style={{ letterSpacing: '0.06em' }}>
                SMART
              </span>
            </Link>

            <div className="hidden md:flex items-center gap-1">
              {visibleItems.map((item) => {
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="px-3 py-1.5 text-[13.5px] rounded-md transition-colors"
                    style={{
                      color: active ? 'var(--fg)' : 'var(--fg-subtle)',
                      background: active ? 'var(--bg-subtle)' : 'transparent',
                      fontWeight: active ? 500 : 400,
                    }}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isLoading ? (
              <div
                className="h-8 w-28 rounded-md"
                style={{ background: 'var(--bg-muted)' }}
              />
            ) : isAuthenticated ? (
              <div className="relative" ref={userMenuRef}>
                <button
                  onClick={() => setUserMenuOpen((v) => !v)}
                  className="btn btn-secondary btn-sm"
                >
                  {getRoleLabel()}
                  <span aria-hidden style={{ color: 'var(--fg-faint)' }}>
                    ›
                  </span>
                </button>
                {userMenuOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setUserMenuOpen(false)}
                    />
                    <div
                      className="absolute right-0 mt-2 w-72 z-20 surface overflow-hidden"
                      style={{
                        boxShadow: 'var(--shadow-lg)',
                        borderColor: 'var(--border-strong)',
                      }}
                    >
                      <div
                        className="px-4 py-3 border-b"
                        style={{ borderColor: 'var(--border)' }}
                      >
                        <p className="meta">Signed in as</p>
                        <p className="text-sm font-medium mt-1.5">{getRoleLabel()}</p>
                        <p className="mono mt-1 truncate" style={{ color: 'var(--fg-faint)' }}>
                          {uuid}
                        </p>
                      </div>
                      <Link
                        href="/profile"
                        className="block px-4 py-2.5 text-sm transition-colors"
                        style={{ color: 'var(--fg-muted)' }}
                      >
                        Profile
                      </Link>
                      <Link
                        href="/profile/identity"
                        className="block px-4 py-2.5 text-sm transition-colors"
                        style={{ color: 'var(--fg-muted)' }}
                      >
                        Identity & claims
                      </Link>
                      <div className="border-t" style={{ borderColor: 'var(--border)' }} />
                      <button
                        onClick={logout}
                        className="block w-full text-left px-4 py-2.5 text-sm transition-colors"
                        style={{ color: 'var(--danger)' }}
                      >
                        Sign out
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link href="/auth" className="btn btn-ghost btn-sm hidden sm:inline-flex">
                  Sign in
                </Link>
                <Link href="/register" className="btn btn-primary btn-sm">
                  Get started
                </Link>
              </div>
            )}

            <button
              onClick={() => setMobileOpen((v) => !v)}
              className="md:hidden btn btn-ghost btn-sm"
              aria-label="Menu"
            >
              {mobileOpen ? 'Close' : 'Menu'}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div className="md:hidden py-3 border-t" style={{ borderColor: 'var(--border)' }}>
            <div className="flex flex-col">
              {visibleItems.map((item) => {
                const active = isActive(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="px-3 py-2.5 text-sm rounded-md"
                    style={{
                      color: active ? 'var(--fg)' : 'var(--fg-muted)',
                      background: active ? 'var(--bg-subtle)' : 'transparent',
                      fontWeight: active ? 500 : 400,
                    }}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </div>
        )}
      </nav>
    </header>
  );
}
