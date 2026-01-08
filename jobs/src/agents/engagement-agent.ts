/**
 * Engagement Agent
 *
 * AI agent focused on member retention and engagement:
 * - Churn risk prediction
 * - Re-engagement campaign recommendations
 * - Personalized offer suggestions
 * - Optimal outreach timing
 * - Credit expiration rescue
 *
 * Proactively identifies members who need attention.
 */

import { z } from "zod";
import { logger } from "@trigger.dev/sdk/v3";
import { runAgent, type AgentTool } from "./agent-runner.js";
import { AI_MODELS } from "../config/ai-models.js";
import { callTradeUpAPI } from "../config/database.js";

// ============================================================================
// SCHEMAS
// ============================================================================

export const EngagementRequestSchema = z.object({
  tenantId: z.number(),
  mode: z.enum([
    "identify_at_risk",      // Find members at risk of churning
    "plan_campaign",         // Design a re-engagement campaign
    "rescue_expiring",       // Save credits about to expire
    "optimize_outreach",     // Best time/channel for specific member
    "personalize_offer",     // Suggest personalized offers
  ]),
  memberId: z.number().optional(),
  campaignGoal: z.string().optional(),
  expirationDays: z.number().optional(), // For rescue mode
});

export const EngagementPlanSchema = z.object({
  mode: z.string(),

  // At-risk members (for identify_at_risk)
  atRiskMembers: z.array(z.object({
    memberId: z.number(),
    memberNumber: z.string(),
    riskScore: z.number(),
    riskFactors: z.array(z.string()),
    daysSinceLastActivity: z.number(),
    creditBalance: z.number(),
    recommendedAction: z.string(),
  })).optional(),

  // Campaign plan (for plan_campaign)
  campaign: z.object({
    name: z.string(),
    goal: z.string(),
    targetSegment: z.string(),
    estimatedReach: z.number(),
    channels: z.array(z.object({
      channel: z.enum(["email", "sms", "push", "in_app"]),
      priority: z.number(),
      timing: z.string(),
      messageTheme: z.string(),
    })),
    offers: z.array(z.object({
      type: z.enum(["bonus_credits", "multiplier", "exclusive_access", "tier_upgrade"]),
      value: z.string(),
      duration: z.string(),
      estimatedCost: z.number(),
      expectedLift: z.number(),
    })),
    timeline: z.array(z.object({
      day: z.number(),
      action: z.string(),
      channel: z.string(),
    })),
    successMetrics: z.array(z.string()),
  }).optional(),

  // Expiration rescue (for rescue_expiring)
  expirationRescue: z.object({
    membersAtRisk: z.number(),
    totalCreditsAtRisk: z.number(),
    rescueStrategies: z.array(z.object({
      strategy: z.string(),
      targetMembers: z.number(),
      estimatedSaveRate: z.number(),
      messageTemplate: z.string(),
    })),
  }).optional(),

  // Outreach optimization (for optimize_outreach)
  outreachPlan: z.object({
    memberId: z.number(),
    bestChannel: z.string(),
    bestTime: z.string(),
    bestDayOfWeek: z.string(),
    personalizedSubject: z.string(),
    personalizedMessage: z.string(),
    avoidTimes: z.array(z.string()),
  }).optional(),

  // Personalized offers (for personalize_offer)
  personalizedOffers: z.array(z.object({
    offerType: z.string(),
    value: z.string(),
    reasoning: z.string(),
    expectedResponse: z.number(),
    validityDays: z.number(),
  })).optional(),

  // General recommendations
  recommendations: z.array(z.object({
    priority: z.enum(["high", "medium", "low"]),
    action: z.string(),
    expectedImpact: z.string(),
    effort: z.enum(["low", "medium", "high"]),
  })),

  summary: z.string(),
});

export type EngagementRequest = z.infer<typeof EngagementRequestSchema>;
export type EngagementPlan = z.infer<typeof EngagementPlanSchema>;

// ============================================================================
// AGENT CONFIGURATION
// ============================================================================

const ENGAGEMENT_SYSTEM_PROMPT = `You are a customer engagement specialist for TradeUp, a store credit and rewards platform.

YOUR MISSION:
- Prevent member churn before it happens
- Re-engage inactive members effectively
- Maximize credit utilization (redeemed credits = happy customers)
- Design campaigns that drive measurable results

ENGAGEMENT PRINCIPLES:

1. CHURN PREDICTION
   Risk factors (weighted):
   - Days since last activity (high weight)
   - Declining purchase frequency (high weight)
   - Unused credit balance (medium weight)
   - No email engagement (medium weight)
   - Tier downgrade trajectory (medium weight)

   Risk levels:
   - Critical: 30+ days inactive + declining trend
   - High: 14-30 days inactive
   - Medium: 7-14 days inactive with warning signs
   - Low: Active with minor concerns

2. RE-ENGAGEMENT STRATEGIES
   - Urgency: Expiring credits, limited-time offers
   - Value: Bonus credits, multipliers
   - Exclusivity: Early access, member-only deals
   - Recognition: Tier progress updates, milestones

3. CHANNEL SELECTION
   - Email: Best for detailed offers, content
   - SMS: Best for urgency, time-sensitive
   - Push: Best for quick reminders
   - In-app: Best for contextual offers

4. TIMING OPTIMIZATION
   - Consider past engagement patterns
   - Avoid over-contacting (max 2-3 touches per week)
   - Time zone awareness
   - Day of week preferences

5. PERSONALIZATION
   - Reference past purchases
   - Acknowledge tier status
   - Use member name
   - Relevant product categories

OUTPUT:
Provide engagement plans in the EngagementPlan schema format.
Always include clear next steps and expected outcomes.
Be specific with message templates and timing.`;

// ============================================================================
// TOOLS
// ============================================================================

function createEngagementTools(tenantId: number): AgentTool[] {
  return [
    // At-Risk Member Detection
    {
      definition: {
        name: "get_at_risk_members",
        description: `Identify members at risk of churning.
Returns ranked list with risk scores and factors.`,
        input_schema: {
          type: "object" as const,
          properties: {
            minRiskScore: { type: "number", description: "Minimum risk score (0-100)" },
            limit: { type: "number", description: "Max members to return" },
            tier: { type: "string", description: "Filter by tier (optional)" },
          },
          required: [],
        },
      },
      execute: async (input: unknown) => {
        const { minRiskScore = 50, limit = 100, tier } = input as {
          minRiskScore?: number;
          limit?: number;
          tier?: string;
        };

        return callTradeUpAPI<{
          members: Array<{
            memberId: number;
            memberNumber: string;
            email: string;
            tier: string;
            riskScore: number;
            riskFactors: string[];
            daysSinceLastPurchase: number;
            daysSinceLastActivity: number;
            creditBalance: number;
            lifetimeValue: number;
          }>;
          totalAtRisk: number;
        }>(`/api/engagement/at-risk`, {
          method: "POST",
          body: { minRiskScore, limit, tier },
          tenantId,
        });
      },
    },

    // Expiring Credits
    {
      definition: {
        name: "get_expiring_credits",
        description: `Get members with credits expiring soon.
Returns members, amounts, and expiration dates.`,
        input_schema: {
          type: "object" as const,
          properties: {
            daysAhead: { type: "number", description: "Days until expiration (default 30)" },
            minAmount: { type: "number", description: "Minimum credit amount" },
          },
          required: [],
        },
      },
      execute: async (input: unknown) => {
        const { daysAhead = 30, minAmount = 5 } = input as {
          daysAhead?: number;
          minAmount?: number;
        };

        return callTradeUpAPI<{
          members: Array<{
            memberId: number;
            memberNumber: string;
            email: string;
            expiringAmount: number;
            expirationDate: string;
            totalBalance: number;
            lastPurchaseDate: string;
          }>;
          totalMembers: number;
          totalAmountExpiring: number;
        }>(`/api/engagement/expiring-credits`, {
          method: "POST",
          body: { daysAhead, minAmount },
          tenantId,
        });
      },
    },

    // Member Engagement History
    {
      definition: {
        name: "get_engagement_history",
        description: `Get member's past engagement and response patterns.
Returns: past campaigns, open rates, best times, preferences.`,
        input_schema: {
          type: "object" as const,
          properties: {
            memberId: { type: "number", description: "Member ID" },
          },
          required: ["memberId"],
        },
      },
      execute: async (input: unknown) => {
        const { memberId } = input as { memberId: number };

        return callTradeUpAPI<{
          emailStats: { sent: number; opened: number; clicked: number };
          smsStats: { sent: number; clicked: number };
          pushStats: { sent: number; tapped: number };
          bestOpenTimes: string[];
          bestDays: string[];
          preferredChannel: string;
          lastEngagement: string;
          unsubscribed: string[];
        }>(`/api/engagement/member/${memberId}/history`, { tenantId });
      },
    },

    // Past Campaign Performance
    {
      definition: {
        name: "get_campaign_performance",
        description: `Get performance data from past campaigns.
Use to inform new campaign design.`,
        input_schema: {
          type: "object" as const,
          properties: {
            campaignType: {
              type: "string",
              enum: ["re_engagement", "expiration_warning", "tier_upgrade", "general"],
              description: "Type of campaign",
            },
            limit: { type: "number", description: "Number of past campaigns" },
          },
          required: [],
        },
      },
      execute: async (input: unknown) => {
        const { campaignType, limit = 10 } = input as {
          campaignType?: string;
          limit?: number;
        };

        return callTradeUpAPI<{
          campaigns: Array<{
            name: string;
            type: string;
            sentDate: string;
            reached: number;
            opened: number;
            clicked: number;
            converted: number;
            revenue: number;
            bestPerformingVariant: string;
          }>;
          averageOpenRate: number;
          averageConversionRate: number;
          topPerformingOffer: string;
        }>(`/api/engagement/campaigns`, {
          method: "POST",
          body: { campaignType, limit },
          tenantId,
        });
      },
    },

    // Segment Size Estimation
    {
      definition: {
        name: "estimate_segment_size",
        description: `Estimate how many members match a segment definition.
Use when planning campaign reach.`,
        input_schema: {
          type: "object" as const,
          properties: {
            filters: {
              type: "object",
              description: "Segment filters (tier, days_inactive, min_balance, etc.)",
            },
          },
          required: ["filters"],
        },
      },
      execute: async (input: unknown) => {
        const { filters } = input as { filters: Record<string, unknown> };

        return callTradeUpAPI<{
          estimatedSize: number;
          percentOfTotal: number;
          averageValue: number;
          topTiers: Record<string, number>;
        }>(`/api/engagement/segment-size`, {
          method: "POST",
          body: { filters },
          tenantId,
        });
      },
    },
  ];
}

// ============================================================================
// AGENT EXECUTOR
// ============================================================================

export interface EngagementAgentConfig {
  anthropicApiKey: string;
}

/**
 * Run engagement analysis or campaign planning
 */
export async function runEngagementAgent(
  request: EngagementRequest,
  config: EngagementAgentConfig
): Promise<EngagementPlan> {
  logger.info("Starting engagement agent", {
    tenantId: request.tenantId,
    mode: request.mode,
    memberId: request.memberId,
  });

  const tools = createEngagementTools(request.tenantId);

  const modeInstructions: Record<string, string> = {
    identify_at_risk: `
Identify members at risk of churning:
1. Use get_at_risk_members to find high-risk members
2. Analyze the risk factors for patterns
3. Prioritize by lifetime value and recoverability
4. Suggest specific actions for each member`,

    plan_campaign: `
Design a re-engagement campaign:
Goal: ${request.campaignGoal || "Increase engagement"}
1. Use get_campaign_performance to learn from past campaigns
2. Define the target segment
3. Use estimate_segment_size to validate reach
4. Design multi-channel outreach with specific timing
5. Create compelling offers based on what worked before`,

    rescue_expiring: `
Create a credit expiration rescue plan:
Timeframe: ${request.expirationDays || 30} days
1. Use get_expiring_credits to identify at-risk credits
2. Segment by amount and member value
3. Design urgency-based messaging
4. Suggest easy redemption options`,

    optimize_outreach: `
Optimize outreach for member ${request.memberId}:
1. Use get_engagement_history to understand their preferences
2. Determine best channel, time, and day
3. Craft a personalized message
4. Suggest what to avoid`,

    personalize_offer: `
Create personalized offers for member ${request.memberId}:
1. Use get_engagement_history for context
2. Consider their tier and behavior
3. Design 2-3 offer options with different appeals
4. Explain why each offer would resonate`,
  };

  const userMessage = `Mode: ${request.mode}

${modeInstructions[request.mode]}

Provide a comprehensive engagement plan with actionable recommendations.
Respond with a JSON object matching the EngagementPlan schema.`;

  const result = await runAgent<EngagementPlan>(
    {
      name: "engagement-agent",
      model: AI_MODELS.SUBAGENT, // Sonnet 4.5
      systemPrompt: ENGAGEMENT_SYSTEM_PROMPT,
      tools,
      maxTurns: 10,
      onToolCall: (name, input, toolResult) => {
        logger.debug("Engagement agent tool call", { name });
      },
    },
    userMessage,
    config.anthropicApiKey
  );

  if (!result.success || !result.result) {
    logger.error("Engagement agent failed", { error: result.error });
    throw new Error(`Engagement agent failed: ${result.error}`);
  }

  try {
    const validated = EngagementPlanSchema.parse(result.result);
    logger.info("Engagement plan complete", {
      tenantId: request.tenantId,
      mode: request.mode,
      recommendationCount: validated.recommendations.length,
    });
    return validated;
  } catch (error) {
    logger.error("Invalid engagement response", { error: String(error) });
    throw new Error("Invalid engagement response from agent");
  }
}
