'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { useAuth, ROLE_LABELS } from '@/contexts/AuthContext';
import { toast } from 'sonner';
import { AuthLayout } from '@/components/AuthLayout';

type Step = 'uuid' | 'role' | 'otp';

const ROLES = [
  {
    value: 'AIDeveloper',
    label: 'AI Developer',
    description: 'Authors and revises model cards.',
  },
  {
    value: 'Reviewer',
    label: 'Reviewer',
    description: 'Reviews submitted cards - endorses, requests changes, or declines.',
  },
  {
    value: 'Publisher',
    label: 'Publisher',
    description: 'Publishes validated cards and manages deprecation.',
  },
  {
    value: 'Reader',
    label: 'Reader',
    description: 'Reads published cards in the registry.',
  },
];

export default function AuthPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login, isAuthenticated } = useAuth();
  const redirectUrl = searchParams.get('redirect') || '/';

  const [step, setStep] = useState<Step>('uuid');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [uuid, setUuid] = useState('');
  const [selectedRole, setSelectedRole] = useState('');
  const [otp, setOtp] = useState('');
  const [receivedOtp, setReceivedOtp] = useState('');

  useEffect(() => {
    if (isAuthenticated) router.push(redirectUrl);
  }, [isAuthenticated, router, redirectUrl]);

  const handleUuidSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!uuid.trim()) {
      setError('Enter your UUID to continue.');
      return;
    }
    setError('');
    setStep('role');
  };

  const handleRoleSelect = async (role: string) => {
    setSelectedRole(role);
    setLoading(true);
    setError('');
    try {
      const response = await api.login(uuid, role);
      setReceivedOtp(response.otp);
      setOtp(response.otp);
      toast.success('Verification code generated');
      setStep('otp');
    } catch (err: any) {
      const errorMsg = err?.message || 'Failed to generate login code';
      setError(errorMsg);
      toast.error('Sign in failed', { description: errorMsg });
    } finally {
      setLoading(false);
    }
  };

  const handleOtpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await api.authenticate(uuid, selectedRole, otp);
      login(uuid, selectedRole, response.token, response.wallet_info);
      toast.success('Signed in', { description: ROLE_LABELS[selectedRole] });
      router.push(redirectUrl);
    } catch (err: any) {
      const msg = err?.message || 'Authentication failed';
      setError(msg.includes('OTP') ? 'Invalid or expired code.' : 'Authentication failed.');
      toast.error('Sign in failed');
    } finally {
      setLoading(false);
    }
  };

  const steps = [
    { id: 'uuid', label: 'Identify' },
    { id: 'role', label: 'Role' },
    { id: 'otp', label: 'Verify' },
  ];

  const currentStepIndex = steps.findIndex((s) => s.id === step);

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Authenticate with your registered UUID and role."
      switchText="Don't have an account?"
      switchLink="/register"
      switchLinkText="Register"
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

      {step === 'uuid' && (
        <form onSubmit={handleUuidSubmit} className="space-y-5">
          <div>
            <label htmlFor="uuid" className="label">
              Your UUID
            </label>
            <input
              id="uuid"
              type="text"
              value={uuid}
              onChange={(e) => {
                setUuid(e.target.value);
                setError('');
              }}
              placeholder="Issued at registration"
              className="input mono"
              autoComplete="off"
            />
          </div>
          {error && <ErrorBox message={error} />}
          <button type="submit" className="btn btn-primary w-full">
            Continue
          </button>
        </form>
      )}

      {step === 'role' && (
        <div className="space-y-5">
          <p className="text-sm" style={{ color: 'var(--fg-muted)' }}>
            Choose the role for this session.
          </p>
          <div className="space-y-2">
            {ROLES.map((role) => (
              <button
                key={role.value}
                onClick={() => handleRoleSelect(role.value)}
                disabled={loading}
                className="w-full text-left surface p-4 transition-colors"
                style={{
                  borderColor: selectedRole === role.value ? 'var(--fg)' : 'var(--border)',
                  background: selectedRole === role.value ? 'var(--bg-subtle)' : 'var(--bg)',
                }}
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-[14.5px] font-medium">{role.label}</span>
                  <span className="meta">{role.value}</span>
                </div>
                <p className="mt-1 text-[13px]" style={{ color: 'var(--fg-subtle)' }}>
                  {role.description}
                </p>
              </button>
            ))}
          </div>
          {loading && <p className="meta">Generating code...</p>}
          {error && <ErrorBox message={error} />}
          <button onClick={() => setStep('uuid')} disabled={loading} className="btn btn-ghost w-full">
            Back
          </button>
        </div>
      )}

      {step === 'otp' && (
        <form onSubmit={handleOtpSubmit} className="space-y-5">
          <div className="surface px-4 py-3 flex items-center justify-between">
            <div>
              <p className="meta">Signing in as</p>
              <p className="text-sm font-medium mt-0.5">{ROLE_LABELS[selectedRole]}</p>
            </div>
            <span className="mono" style={{ color: 'var(--fg-faint)' }}>
              {selectedRole}
            </span>
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

          {error && <ErrorBox message={error} />}

          <button type="submit" disabled={loading} className="btn btn-primary w-full">
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
          <button
            type="button"
            onClick={() => setStep('role')}
            disabled={loading}
            className="btn btn-ghost w-full"
          >
            Back
          </button>
        </form>
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
