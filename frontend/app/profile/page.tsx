'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { safeDate } from '@/lib/utils';

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface UserInfo {
  uuid: string;
  username?: string | null;
  email?: string | null;
  eoa_address?: string | null;
  smart_account?: string | null;
  smart_accounts?: { address: string; role: string }[];
  role?: string | null;
  roles?: string[];
  created_at?: number | string | null;
  status?: string | null;
  verified?: boolean | null;
  smart_id?: string | null;
}

interface RoleRequest {
  request_id: string;
  requested_role: string;
  reason?: string | null;
  status: 'pending' | 'approved' | 'rejected';
  admin_notes?: string | null;
  created_at?: any;
  updated_at?: any;
}

const REQUESTABLE_ROLES: { id: 'Reviewer' | 'Publisher'; description: string }[] = [
  {
    id: 'Reviewer',
    description: 'Review submitted cards - endorse, request changes, or decline.',
  },
  {
    id: 'Publisher',
    description: 'Publish validated cards and manage deprecation.',
  },
];

export default function ProfilePage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, uuid, role, token, getWalletAddress, getRoleLabel } = useAuth();
  const [info, setInfo] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [editUsername, setEditUsername] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [roleRequests, setRoleRequests] = useState<RoleRequest[]>([]);
  const [requestingRole, setRequestingRole] = useState<'Reviewer' | 'Publisher' | null>(null);
  const [requestReason, setRequestReason] = useState('');
  const [submittingRoleRequest, setSubmittingRoleRequest] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.push('/auth');
  }, [isAuthenticated, isLoading, router]);

  const reloadRoleRequests = async (forUuid: string) => {
    try {
      const r = await fetch(`${API}/api/role-requests/mine?uuid=${forUuid}`);
      if (r.ok) {
        const d = await r.json();
        setRoleRequests(d.requests || []);
      }
    } catch {}
  };

  useEffect(() => {
    if (!uuid) return;
    (async () => {
      setLoading(true);
      try {
        const r = await fetch(`${API}/api/user/${uuid}`);
        if (r.ok) setInfo(await r.json());
        await reloadRoleRequests(uuid);
      } finally {
        setLoading(false);
      }
    })();
  }, [uuid]);

  const submitRoleRequest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uuid || !requestingRole) return;
    setSubmittingRoleRequest(true);
    try {
      const r = await fetch(`${API}/api/admin/role-requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          uuid,
          requested_role: requestingRole,
          reason: requestReason.trim() || `Requesting ${requestingRole} role access`,
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      toast.success('Role request submitted', {
        description: 'An administrator will review your request.',
      });
      setRequestingRole(null);
      setRequestReason('');
      await reloadRoleRequests(uuid);
    } catch (err: any) {
      toast.error(err.message || 'Failed to submit role request');
    } finally {
      setSubmittingRoleRequest(false);
    }
  };

  const beginEdit = () => {
    setEditUsername(info?.username || '');
    setEditEmail(info?.email || '');
    setEditing(true);
  };

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uuid || !token) return;
    setSavingProfile(true);
    try {
      const r = await fetch(`${API}/api/user/${uuid}/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Auth-Token': token,
        },
        body: JSON.stringify({
          username: editUsername.trim() || null,
          email: editEmail.trim() || null,
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        throw new Error(d.detail || `HTTP ${r.status}`);
      }
      setInfo(await r.json());
      setEditing(false);
      toast.success('Profile updated');
    } catch (err: any) {
      toast.error(err.message || 'Failed to update profile');
    } finally {
      setSavingProfile(false);
    }
  };

  if (isLoading || loading) {
    return (
      <main className="container-app py-16">
        <div className="surface h-32 animate-pulse" />
      </main>
    );
  }

  const wallet = getWalletAddress();

  return (
    <main className="container-app py-10 lg:py-14">
      <div className="mb-10">
        <p className="meta mb-3">Profile</p>
        <h1 className="text-3xl lg:text-4xl font-semibold tracking-tight">Account</h1>
      </div>

      <section className="surface p-6 mb-6">
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-base font-semibold">Account</h2>
          {!editing && (
            <button onClick={beginEdit} className="link-muted text-[12.5px]">
              Edit profile
            </button>
          )}
        </div>
        {editing ? (
          <form onSubmit={saveProfile} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="meta block mb-1.5">Username</label>
              <input
                className="input w-full"
                value={editUsername}
                onChange={(e) => setEditUsername(e.target.value)}
                placeholder="Display name"
                disabled={savingProfile}
              />
            </div>
            <div>
              <label className="meta block mb-1.5">Email</label>
              <input
                className="input w-full"
                type="email"
                value={editEmail}
                onChange={(e) => setEditEmail(e.target.value)}
                placeholder="you@example.com"
                disabled={savingProfile}
              />
            </div>
            <div className="md:col-span-2 flex gap-2">
              <button
                type="button"
                onClick={() => setEditing(false)}
                className="btn btn-secondary"
                disabled={savingProfile}
              >
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={savingProfile}>
                {savingProfile ? 'Saving…' : 'Save'}
              </button>
            </div>
          </form>
        ) : (
          <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3">
            <Field label="Role" value={getRoleLabel()} />
            <Field label="UUID" value={uuid || '-'} mono />
            <Field label="Username" value={info?.username || '-'} />
            <Field label="Email" value={info?.email || '-'} />
            <Field label="Created" value={safeDate(info?.created_at, 'datetime')} />
            <Field label="Roles on file" value={(info?.roles || [role]).filter(Boolean).join(', ')} />
          </dl>
        )}
      </section>

      <section className="surface p-6 mb-6">
        <h2 className="text-base font-semibold mb-4">Roles</h2>
        <p className="meta mb-3">Your active roles</p>
        <div className="flex flex-wrap gap-2 mb-6">
          {(info?.roles || []).length === 0 ? (
            <span className="text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>None</span>
          ) : (
            (info?.roles || []).map((r) => (
              <span key={r} className="pill pill-info">{r}</span>
            ))
          )}
        </div>

        {(() => {
          const userRoles = info?.roles || [];
          const pendingRoles = roleRequests
            .filter((r) => r.status === 'pending')
            .map((r) => r.requested_role);
          const requestable = REQUESTABLE_ROLES.filter(
            (r) => !userRoles.includes(r.id) && !pendingRoles.includes(r.id),
          );
          if (requestable.length === 0 && pendingRoles.length === 0) return null;
          return (
            <div className="pt-5 border-t" style={{ borderColor: 'var(--border)' }}>
              <p className="meta mb-3">Request additional roles</p>
              {requestable.length === 0 ? (
                <p className="text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>
                  No additional roles available to request.
                </p>
              ) : (
                <div className="space-y-2">
                  {requestable.map((r) => {
                    const isOpen = requestingRole === r.id;
                    return (
                      <div key={r.id} className="surface p-4">
                        <div className="flex items-baseline justify-between gap-3 flex-wrap">
                          <div className="min-w-0">
                            <p className="text-[14.5px] font-medium">{r.id}</p>
                            <p className="text-[13px] mt-1" style={{ color: 'var(--fg-subtle)' }}>
                              {r.description}
                            </p>
                          </div>
                          {!isOpen && (
                            <button
                              onClick={() => {
                                setRequestingRole(r.id);
                                setRequestReason('');
                              }}
                              className="btn btn-secondary btn-sm"
                            >
                              Request
                            </button>
                          )}
                        </div>
                        {isOpen && (
                          <form onSubmit={submitRoleRequest} className="mt-4 space-y-3">
                            <div>
                              <label className="meta block mb-1.5">Reason (optional)</label>
                              <textarea
                                className="input w-full"
                                rows={3}
                                value={requestReason}
                                onChange={(e) => setRequestReason(e.target.value)}
                                placeholder="Briefly explain why you need this role."
                                disabled={submittingRoleRequest}
                              />
                            </div>
                            <div className="flex gap-2">
                              <button
                                type="button"
                                onClick={() => setRequestingRole(null)}
                                className="btn btn-secondary"
                                disabled={submittingRoleRequest}
                              >
                                Cancel
                              </button>
                              <button
                                type="submit"
                                className="btn btn-primary"
                                disabled={submittingRoleRequest}
                              >
                                {submittingRoleRequest ? 'Submitting…' : 'Submit request'}
                              </button>
                            </div>
                          </form>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })()}

        {roleRequests.length > 0 && (
          <div className="pt-5 mt-5 border-t" style={{ borderColor: 'var(--border)' }}>
            <p className="meta mb-3">Request history</p>
            <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {roleRequests.map((r) => (
                <li key={r.request_id} className="py-3 flex items-baseline justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <p className="text-[14px] font-medium">{r.requested_role}</p>
                    {r.reason && (
                      <p className="text-[12.5px] mt-1" style={{ color: 'var(--fg-subtle)' }}>
                        {r.reason}
                      </p>
                    )}
                    {r.status === 'rejected' && r.admin_notes && (
                      <p className="text-[12.5px] mt-1" style={{ color: 'var(--fg-muted)' }}>
                        Admin: {r.admin_notes}
                      </p>
                    )}
                    <p className="text-[12px] mt-1" style={{ color: 'var(--fg-faint)' }}>
                      {safeDate(r.created_at, 'datetime')}
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
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="surface p-6">
        <h2 className="text-base font-semibold mb-4">On-chain identity</h2>
        <dl className="grid grid-cols-1 gap-y-3 mb-4">
          <Field label="EOA address" value={info?.eoa_address || '-'} mono />
        </dl>

        <p className="meta mb-2">SMART accounts (one per role)</p>
        {(info?.smart_accounts || []).length === 0 ? (
          <p className="text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>None</p>
        ) : (
          <ul className="divide-y" style={{ borderColor: 'var(--border)' }}>
            {(info?.smart_accounts || []).map((sa) => (
              <li
                key={`${sa.role}-${sa.address}`}
                className="py-2 flex items-baseline justify-between gap-3 flex-wrap"
              >
                <span className="text-[13.5px] font-medium">{sa.role}</span>
                <span className="mono text-[12.5px]" style={{ color: 'var(--fg-muted)' }}>
                  {sa.address}
                </span>
              </li>
            ))}
          </ul>
        )}

        <p className="text-[12.5px] mt-3" style={{ color: 'var(--fg-muted)' }}>
          The EOA is your signing key. Each SMART account is a role-bound contract account that
          submits on-chain actions on your behalf - one per active role.
        </p>
        <div className="mt-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
          <Link href="/profile/identity" className="link">
            Institutional verification
          </Link>
        </div>
      </section>
    </main>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="meta">{label}</dt>
      <dd className={`mt-1 text-[14px] ${mono ? 'mono' : ''}`} style={{ color: 'var(--fg)' }}>
        {value}
      </dd>
    </div>
  );
}
