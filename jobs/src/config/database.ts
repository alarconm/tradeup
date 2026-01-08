/**
 * Database Configuration for TradeUp Jobs
 *
 * Connects to the same PostgreSQL database as the Flask backend.
 * Uses environment variables for configuration.
 */

import { z } from "zod";

const envSchema = z.object({
  DATABASE_URL: z.string().url(),
  TRADEUP_API_URL: z.string().url().default("http://localhost:5000"),
  TRADEUP_API_KEY: z.string().optional(),
});

export const env = envSchema.parse(process.env);

/**
 * API client for calling the Flask backend
 * Used for operations that need to go through the existing API
 */
export async function callTradeUpAPI<T>(
  endpoint: string,
  options: {
    method?: "GET" | "POST" | "PUT" | "DELETE";
    body?: unknown;
    tenantId?: number;
  } = {}
): Promise<T> {
  const { method = "GET", body, tenantId } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  if (env.TRADEUP_API_KEY) {
    headers["X-API-Key"] = env.TRADEUP_API_KEY;
  }

  if (tenantId) {
    headers["X-Tenant-ID"] = String(tenantId);
  }

  const response = await fetch(`${env.TRADEUP_API_URL}${endpoint}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API Error ${response.status}: ${error}`);
  }

  return response.json() as Promise<T>;
}

/**
 * Types matching the Flask backend models
 */
export interface Tenant {
  id: number;
  shop_domain: string;
  subscription_active: boolean;
}

export interface Member {
  id: number;
  tenant_id: number;
  member_number: string;
  email: string | null;
  first_name: string | null;
  last_name: string | null;
  status: "active" | "inactive" | "suspended";
  tier_id: number | null;
  tier?: MembershipTier;
}

export interface MembershipTier {
  id: number;
  tenant_id: number;
  name: string;
  monthly_credit_amount: number | null;
  credit_expiration_days: number | null;
  is_active: boolean;
}

export interface StoreCreditLedger {
  id: number;
  member_id: number;
  amount: number;
  event_type: string;
  description: string;
  created_at: string;
  expires_at: string | null;
}
