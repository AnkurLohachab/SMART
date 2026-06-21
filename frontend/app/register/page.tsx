'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { AuthLayout } from '@/components/AuthLayout';

type Step = 'register' | 'verify' | 'role-request' | 'complete';

const REQUESTABLE_ROLES = [
  {
    id: 'Reviewer',
    name: 'Reviewer',
    description: 'Review submitted cards - endorse, request changes, or decline.',
    permissions: ['Endorse', 'Request changes', 'Decline'],
  },
  {
    id: 'Publisher',
    name: 'Publisher',
    description: 'List endorsed cards in the public registry; archive when superseded.',
    permissions: ['List in registry', 'Archive'],
  },
];

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>('register');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);

  const [uuid, setUuid] = useState('');
  const [otp, setOtp] = useState('');
  const [receivedOtp, setReceivedOtp] = useState('');
  const [roles, setRoles] = useState<string[]>([]);

  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [roleReason, setRoleReason] = useState('');
  const [roleRequestSubmitted, setRoleRequestSubmitted] = useState(false);

  const copyUuid = async () => {
    await navigator.clipboard.writeText(uuid);
    setCopied(true);
    toast.success('UUID copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await api.register(undefined);
      setUuid(response.uuid);
      setReceivedOtp(response.otp);
      setOtp(response.otp);
      toast.success('Account created');
      setStep('verify');
    } catch (err: any) {
      const msg = err?.message || 'Registration failed';
      setError(msg.includes('already registered') ? 'This account already exists. Try signing in.' : msg);
      toast.error('Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await api.verify(uuid, otp);
      setRoles(response.roles || []);
      toast.success('Verified');
      setStep('role-request');
    } catch (err: any) {
      setError('Invalid or expired code.');
      toast.error('Verification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRoleRequest = async () => {
    if (!selectedRole) {
      setStep('complete');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const response = await fetch('http://localhost:8000/api/admin/role-requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          uuid,
          requested_role: selectedRole,
          reason: roleReason || `Requesting ${selectedRole} role access`,
        }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to submit role request');
      }
      setRoleRequestSubmitted(true);
      toast.success('Role request submitted', {
        description: 'An administrator will review your request.',
      });
      setStep('complete');
    } catch (err: any) {
      setError(err.message || 'Failed to submit role request');
      toast.error('Role request failed');
    } finally {
      setLoading(false);
    }
  };

  const steps = [
    { id: 'register', label: 'Create' },
    { id: 'verify', label: 'Verify' },
    { id: 'role-request', label: 'Roles' },
    { id: 'complete', label: 'Done' },
  ];
  const currentStepIndex = steps.findIndex((s) => s.id === step);

  return (
    <AuthLayout
      title={
        step === 'complete'
          ? "You're all set"
          : step === 'role-request'
            ? 'Request additional roles'
            : 'Create your account'
      }
      subtitle={
        step === 'complete'
          ? 'Your account is ready.'
          : step === 'role-request'
            ? 'Optionally request Reviewer or Publisher access.'
            : 'A UUID will be issued for sign-in.'
      }
      switchText={step === 'register' || step === 'verify' ? 'Already have an account?' : undefined}
      switchLink={step === 'register' || step === 'verify' ? '/auth' : undefined}
      switchLinkText={step === 'register' || step === 'verify' ? 'Sign in' : undefined}
    >
      <ol className="flex items-center gap-2 mb-8">
        {steps.map((s, index) => {
          const done = index < currentStepIndex;
          const active = index === currentStepIndex;
          return (
            <li key={s.id} className="flex items-center gap-2">
              <span
                className="flex items-center justify-center w-6 h-6 rounded-full text-[12px] font-semibold tabular-nums"
                style={{
                  background: active ? 'var(--fg)' : done ? 'var(--bg)' : 'var(--bg-subtle)',
                  color: active ? 'var(--bg)' : done ? 'var(--fg)' : 'var(--fg-faint)',
                  border: `1px solid ${active || done ? 'var(--fg)' : 'var(--border-strong)'}`,
                }}
              >
                {index + 1}
              </span>
              <span
                className="text-[13px]"
                style={{
                  color: active ? 'var(--fg)' : 'var(--fg-subtle)',
                  fontWeight: active ? 500 : 400,
                }}
              >
                {s.label}
              </span>
              {index < steps.length - 1 && (
                <span className="w-8 h-px" style={{ background: 'var(--border-strong)' }} />
              )}
            </li>
          );
        })}
      </ol>

      {step === 'register' && (
        <form onSubmit={handleRegister} className="space-y-5">
          <div className="surface p-4">
            <p className="text-[13.5px] leading-[1.6]" style={{ color: 'var(--fg-muted)' }}>
              Create your account. You'll receive a unique UUID to sign in with.
            </p>
          </div>
          {error && <ErrorBox message={error} />}
          <button type="submit" disabled={loading} className="btn btn-primary w-full">
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>
      )}

      {step === 'verify' && (
        <form onSubmit={handleVerify} className="space-y-5">
          <div className="surface p-4">
            <div className="flex items-center justify-between mb-2">
              <p className="meta">Save your UUID. Required for sign-in.</p>
              <button
                type="button"
                onClick={copyUuid}
                className="text-[12.5px] link-muted"
              >
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <p className="mono text-[13px] break-all select-all">{uuid}</p>
          </div>

          {receivedOtp && (
            <div className="surface p-4">
              <p className="meta mb-2">Demo verification code</p>
              <p className="mono text-2xl tracking-[0.4em] font-semibold">{receivedOtp}</p>
            </div>
          )}

          <div>
            <label htmlFor="otp" className="label">
              Verification code
            </label>
            <input
              id="otp"
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={otp}
              onChange={(e) => {
                setOtp(e.target.value);
                setError('');
              }}
              placeholder="000000"
              className="input mono"
              style={{ textAlign: 'center', letterSpacing: '0.4em', fontSize: 18, height: 48 }}
            />
          </div>

          {loading && <p className="meta">Creating blockchain accounts...</p>}
          {error && <ErrorBox message={error} />}

          <button type="submit" disabled={loading} className="btn btn-primary w-full">
            {loading ? 'Verifying...' : 'Verify and create accounts'}
          </button>
        </form>
      )}

      {step === 'role-request' && (
        <div className="space-y-5">
          <div className="surface p-4">
            <p className="meta mb-1">Default roles assigned</p>
            <p className="text-sm font-medium">Reader · AI Developer</p>
            <p className="mt-2 text-[13px]" style={{ color: 'var(--fg-muted)' }}>
              Optionally request additional roles (subject to admin approval).
            </p>
          </div>

          <div className="space-y-2">
            {REQUESTABLE_ROLES.map((role) => {
              const isSelected = selectedRole === role.id;
              return (
                <button
                  key={role.id}
                  type="button"
                  onClick={() => setSelectedRole(isSelected ? null : role.id)}
                  className="w-full surface p-4 text-left transition-colors"
                  style={{
                    borderColor: isSelected ? 'var(--fg)' : 'var(--border)',
                    background: isSelected ? 'var(--bg-subtle)' : 'var(--bg)',
                  }}
                >
                  <div className="flex items-baseline justify-between">
                    <span className="text-[14.5px] font-medium">{role.name}</span>
                    <span className="meta">{isSelected ? 'Selected' : role.id}</span>
                  </div>
                  <p className="mt-1 text-[13px]" style={{ color: 'var(--fg-subtle)' }}>
                    {role.description}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {role.permissions.map((perm) => (
                      <span key={perm} className="pill pill-muted">
                        {perm}
                      </span>
                    ))}
                  </div>
                </button>
              );
            })}
          </div>

          {selectedRole && (
            <div>
              <label htmlFor="reason" className="label">
                Reason for request (optional)
              </label>
              <textarea
                id="reason"
                value={roleReason}
                onChange={(e) => setRoleReason(e.target.value)}
                placeholder="Briefly explain why you need this role."
                rows={3}
                className="input"
              />
            </div>
          )}

          {error && <ErrorBox message={error} />}

          <div className="flex gap-2">
            <button onClick={() => setStep('complete')} className="btn btn-secondary flex-1">
              Skip
            </button>
            <button
              onClick={handleRoleRequest}
              disabled={loading}
              className="btn btn-primary flex-1"
            >
              {loading ? 'Submitting...' : selectedRole ? 'Submit request' : 'Continue'}
            </button>
          </div>
        </div>
      )}

      {step === 'complete' && (
        <div className="space-y-5">
          <div className="surface p-4">
            <p className="meta mb-2">Your UUID. Keep this safe.</p>
            <p className="mono text-[13px] break-all select-all">{uuid}</p>
          </div>

          {roles.length > 0 && (
            <div className="surface p-4">
              <p className="meta mb-3">Active roles</p>
              <div className="flex flex-wrap gap-2">
                {roles.map((role) => (
                  <span key={role} className="pill pill-info">
                    {role}
                  </span>
                ))}
              </div>
            </div>
          )}

          {roleRequestSubmitted && selectedRole && (
            <div className="surface p-4" style={{ borderColor: 'var(--warn)' }}>
              <p className="meta mb-2" style={{ color: 'var(--warn)' }}>
                Pending request
              </p>
              <p className="text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>
                Your request for the <span className="font-medium" style={{ color: 'var(--fg)' }}>{selectedRole}</span>{' '}
                role is awaiting administrator approval.
              </p>
            </div>
          )}

          <button onClick={() => router.push('/auth')} className="btn btn-primary w-full">
            Continue to sign in
          </button>
        </div>
      )}
    </AuthLayout>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div
      className="px-3 py-2.5 rounded-md text-[13px]"
      style={{
        color: 'var(--danger)',
        background: 'rgba(185,28,28,0.06)',
        border: '1px solid rgba(185,28,28,0.3)',
      }}
    >
      {message}
    </div>
  );
}
