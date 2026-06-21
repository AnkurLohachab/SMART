'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';

// "Authenticator" is a legacy alias for "Reviewer", still accepted from cached sessions.
export type UserRole = 'AIDeveloper' | 'Reviewer' | 'Authenticator' | 'Publisher' | 'Reader' | 'Admin' | null;

export const ROLE_LABELS: Record<string, string> = {
  'AIDeveloper': 'AI Developer',
  'Reviewer': 'Reviewer',
  'Authenticator': 'Reviewer',
  'Publisher': 'Publisher',
  'Reader': 'Reader',
  'Admin': 'Administrator',
};

export const ROLE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  'AIDeveloper': { bg: 'bg-blue-100 dark:bg-blue-900/30', text: 'text-blue-700 dark:text-blue-300', border: 'border-blue-200 dark:border-blue-800' },
  'Reviewer': { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-700 dark:text-purple-300', border: 'border-purple-200 dark:border-purple-800' },
  'Authenticator': { bg: 'bg-purple-100 dark:bg-purple-900/30', text: 'text-purple-700 dark:text-purple-300', border: 'border-purple-200 dark:border-purple-800' },
  'Publisher': { bg: 'bg-emerald-100 dark:bg-emerald-900/30', text: 'text-emerald-700 dark:text-emerald-300', border: 'border-emerald-200 dark:border-emerald-800' },
  'Reader': { bg: 'bg-gray-100 dark:bg-gray-800', text: 'text-gray-700 dark:text-gray-300', border: 'border-gray-200 dark:border-gray-700' },
  'Admin': { bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-300', border: 'border-red-200 dark:border-red-800' },
};

const PERMISSIONS: Record<string, string[]> = {
  'AIDeveloper': ['create_model_card', 'submit_for_evaluation', 'revise_model_card', 'view_own_cards', 'view_all_cards'],
  'Reviewer': ['validate_model_card', 'reject_model_card', 'request_revision', 'view_all_cards'],
  'Authenticator': ['validate_model_card', 'reject_model_card', 'request_revision', 'view_all_cards'],
  'Publisher': ['publish_model_card', 'deprecate_model_card', 'view_all_cards'],
  'Reader': ['view_all_cards'],
  'Admin': ['create_model_card', 'submit_for_evaluation', 'revise_model_card', 'validate_model_card', 'reject_model_card', 'request_revision', 'publish_model_card', 'deprecate_model_card', 'view_own_cards', 'view_all_cards', 'manage_users', 'approve_roles'],
};

const PROTECTED_ROUTES = ['/create', '/workflow'];

export function normaliseRole(role: string | null | undefined): UserRole {
  if (!role) return null;
  if (role === 'Authenticator') return 'Reviewer';
  return role as UserRole;
}

interface WalletInfo {
  eoaAddress: string | null;
  smartAccount: string | null;
}

interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  uuid: string | null;
  role: UserRole;
  token: string | null;
  walletInfo: WalletInfo | null;
}

interface AuthContextType extends AuthState {
  login: (uuid: string, role: string, token: string, walletInfo?: { eoa_address: string | null; smart_account: string | null } | null) => void;
  logout: () => void;
  hasPermission: (action: string) => boolean;
  getRoleLabel: () => string;
  getRoleColors: () => { bg: string; text: string; border: string };
  getWalletAddress: () => string | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();

  const [state, setState] = useState<AuthState>({
    isAuthenticated: false,
    isLoading: true,
    uuid: null,
    role: null,
    token: null,
    walletInfo: null,
  });

  useEffect(() => {
    const loadAuthState = () => {
      try {
        const token = localStorage.getItem('authToken');
        const uuid = localStorage.getItem('uuid');
        const role = localStorage.getItem('role') as UserRole;
        const walletInfoStr = localStorage.getItem('walletInfo');
        let walletInfo: WalletInfo | null = null;

        if (walletInfoStr) {
          try {
            walletInfo = JSON.parse(walletInfoStr);
          } catch {
            console.error('[AuthContext] Failed to parse walletInfo');
            walletInfo = null;
          }
        }

        if (token && uuid && role) {
          setState({
            isAuthenticated: true,
            isLoading: false,
            uuid,
            role,
            token,
            walletInfo,
          });
        } else {
          setState(prev => ({ ...prev, isLoading: false }));
        }
      } catch (e) {
        console.error('[AuthContext] Error loading auth state:', e);
        setState(prev => ({ ...prev, isLoading: false }));
      }
    };

    loadAuthState();
  }, []);

  useEffect(() => {
    if (state.isLoading) return;

    const isProtectedRoute = PROTECTED_ROUTES.some(route => pathname?.startsWith(route));

    if (isProtectedRoute && !state.isAuthenticated) {
      router.push(`/auth?redirect=${encodeURIComponent(pathname || '/')}`);
    }
  }, [state.isAuthenticated, state.isLoading, pathname, router]);

  const login = useCallback((uuid: string, role: string, token: string, walletInfoFromApi?: { eoa_address: string | null; smart_account: string | null } | null) => {
    localStorage.setItem('authToken', token);
    localStorage.setItem('uuid', uuid);
    localStorage.setItem('role', role);

    const walletInfo: WalletInfo | null = walletInfoFromApi ? {
      eoaAddress: walletInfoFromApi.eoa_address,
      smartAccount: walletInfoFromApi.smart_account,
    } : null;

    if (walletInfo) {
      localStorage.setItem('walletInfo', JSON.stringify(walletInfo));
    }

    setState({
      isAuthenticated: true,
      isLoading: false,
      uuid,
      role: role as UserRole,
      token,
      walletInfo,
    });
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('uuid');
    localStorage.removeItem('role');
    localStorage.removeItem('walletInfo');

    setState({
      isAuthenticated: false,
      isLoading: false,
      uuid: null,
      role: null,
      token: null,
      walletInfo: null,
    });

    router.push('/');
  }, [router]);

  const hasPermission = useCallback((action: string): boolean => {
    if (!state.role) return false;
    return PERMISSIONS[state.role]?.includes(action) || false;
  }, [state.role]);

  const getRoleLabel = useCallback((): string => {
    if (!state.role) return '';
    return ROLE_LABELS[state.role] || state.role;
  }, [state.role]);

  const getRoleColors = useCallback(() => {
    if (!state.role) return { bg: '', text: '', border: '' };
    return ROLE_COLORS[state.role] || { bg: '', text: '', border: '' };
  }, [state.role]);

  const getWalletAddress = useCallback((): string | null => {
    if (!state.walletInfo) return null;
    return state.walletInfo.smartAccount || state.walletInfo.eoaAddress;
  }, [state.walletInfo]);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        logout,
        hasPermission,
        getRoleLabel,
        getRoleColors,
        getWalletAddress,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
