/**
 * API client for TradeUp backend
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';
const TENANT_ID = import.meta.env.VITE_TENANT_ID || '1';

interface ApiError {
  error: string;
  message?: string;
}

class ApiClient {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  constructor() {
    // Load tokens from localStorage
    this.accessToken = localStorage.getItem('access_token');
    this.refreshToken = localStorage.getItem('refresh_token');
  }

  setTokens(accessToken: string, refreshToken: string) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
  }

  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE}${endpoint}`;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Tenant-ID': TENANT_ID,
      ...(options.headers as Record<string, string>),
    };

    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    // Try to refresh token if unauthorized
    if (response.status === 401 && this.refreshToken) {
      const refreshed = await this.refreshAccessToken();
      if (refreshed) {
        // Retry the request with new token
        headers['Authorization'] = `Bearer ${this.accessToken}`;
        const retryResponse = await fetch(url, { ...options, headers });
        if (!retryResponse.ok) {
          const error: ApiError = await retryResponse.json();
          throw new Error(error.error || 'Request failed');
        }
        return retryResponse.json();
      }
    }

    if (!response.ok) {
      const error: ApiError = await response.json();
      throw new Error(error.error || 'Request failed');
    }

    return response.json();
  }

  private async refreshAccessToken(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Tenant-ID': TENANT_ID,
        },
        body: JSON.stringify({ refresh_token: this.refreshToken }),
      });

      if (!response.ok) {
        this.clearTokens();
        return false;
      }

      const data = await response.json();
      this.accessToken = data.access_token;
      localStorage.setItem('access_token', data.access_token);
      return true;
    } catch {
      this.clearTokens();
      return false;
    }
  }

  // HTTP methods
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint);
  }

  async post<T>(endpoint: string, data?: object): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async put<T>(endpoint: string, data?: object): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  isAuthenticated(): boolean {
    return !!this.accessToken;
  }
}

export const api = new ApiClient();
export default api;
