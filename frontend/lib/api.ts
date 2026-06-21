const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface RegisterResponse {
  message: string;
  otp: string;
  uuid: string;
}

export interface VerifyResponse {
  message: string;
  roles: string[];
  custom_accounts: string[];
}

export interface LoginResponse {
  message: string;
  otp: string;
}

export interface WalletInfo {
  eoa_address: string | null;
  smart_account: string | null;
  role: string;
}

export interface AuthenticateResponse {
  message: string;
  token: string;
  wallet_info: WalletInfo | null;
}

export interface UserInfo {
  uuid: string;
  eoa_address: string | null;
  role: string | null;
}

export const api = {
  async register(uuid?: string): Promise<RegisterResponse> {
    const response = await fetch(`${API_BASE_URL}/api/register`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ uuid }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }

    return response.json();
  },

  async verify(uuid: string, otp: string): Promise<VerifyResponse> {
    const response = await fetch(`${API_BASE_URL}/api/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ uuid, otp }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Verification failed');
    }

    return response.json();
  },

  async login(uuid: string, role: string): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ uuid, role }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    return response.json();
  },

  async authenticate(uuid: string, role: string, otp: string): Promise<AuthenticateResponse> {
    const response = await fetch(`${API_BASE_URL}/api/authenticate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ uuid, role, otp }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Authentication failed');
    }

    return response.json();
  },

  async getUserInfo(uuid: string, token: string): Promise<UserInfo> {
    const response = await fetch(`${API_BASE_URL}/api/user/${uuid}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get user info');
    }

    return response.json();
  },
};
