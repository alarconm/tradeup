/**
 * Authentication API calls
 */
import api from './client';

export interface Member {
  id: number;
  member_number: string;
  email: string;
  name: string | null;
  phone: string | null;
  status: string;
  tier: Tier | null;
  membership_start_date: string | null;
  created_at: string;
  shopify_customer_id: string | null;
  stats?: {
    total_credit_earned: number;
    total_trade_ins: number;
    total_trade_value: number;
  };
  subscription?: {
    shopify_subscription_contract_id: string | null;
    subscription_status: string;
    tier_assigned_by: string | null;
    tier_assigned_at: string | null;
    tier_expires_at: string | null;
  };
}

export interface Tier {
  id: number;
  name: string;
  monthly_price: number;
  bonus_rate: number;
  benefits: Record<string, unknown>;
  is_active: boolean;
  shopify_selling_plan_id: string | null;
}

export interface AuthResponse {
  member: Member;
  access_token: string;
  refresh_token: string;
  message?: string;
}

export async function signup(data: {
  email: string;
  password: string;
  name?: string;
  phone?: string;
}): Promise<AuthResponse> {
  const response = await api.post<AuthResponse>('/api/auth/signup', data);
  api.setTokens(response.access_token, response.refresh_token);
  return response;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const response = await api.post<AuthResponse>('/api/auth/login', { email, password });
  api.setTokens(response.access_token, response.refresh_token);
  return response;
}

export async function logout(): Promise<void> {
  api.clearTokens();
}

export async function getMe(): Promise<{ member: Member }> {
  return api.get('/api/auth/me');
}

export async function updateProfile(data: {
  name?: string;
  phone?: string;
}): Promise<{ member: Member }> {
  return api.put('/api/auth/me', data);
}

export async function changePassword(
  currentPassword: string,
  newPassword: string
): Promise<{ message: string }> {
  return api.post('/api/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  return api.post('/api/auth/forgot-password', { email });
}

export async function resetPassword(
  token: string,
  newPassword: string
): Promise<{ message: string }> {
  return api.post('/api/auth/reset-password', { token, new_password: newPassword });
}
