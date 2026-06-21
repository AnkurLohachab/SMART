import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('authToken');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('authToken');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.put<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }

  async patch<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.patch<T>(url, data, config);
    return response.data;
  }
}

export const apiClient = new ApiClient();

export const api = {
  health: () => apiClient.get<{ status: string }>('/health'),

  modelCards: {
    list: () => apiClient.get('/api/model-cards'),
    get: (id: string) => apiClient.get(`/api/model-cards/${id}`),
    create: (data: any) => apiClient.post('/api/model-cards', data),
    update: (id: string, data: any) => apiClient.put(`/api/model-cards/${id}`, data),
    delete: (id: string) => apiClient.delete(`/api/model-cards/${id}`),
  },

  auth: {
    login: (credentials: { username: string; password: string }) =>
      apiClient.post('/api/auth/login', credentials),
    register: (data: { username: string; email: string; password: string }) =>
      apiClient.post('/api/auth/register', data),
    logout: () => apiClient.post('/api/auth/logout'),
    me: () => apiClient.get('/api/auth/me'),
  },

  blockchain: {
    deployments: () => apiClient.get('/api/blockchain/deployments'),
    register: (data: any) => apiClient.post('/api/blockchain/register', data),
  },

};
