/**
 * Member Insights Agent
 *
 * AI agent that analyzes member behavior and provides actionable insights:
 * - Purchase patterns and preferences
 * - Credit usage behavior
 * - Tier progression recommendations
 * - Lifetime value predictions
 * - Segment identification
 *
 * Used by tenant admins to understand their member base.
 */

import { z } from "zod";
import { logger } from "@trigger.dev/sdk/v3";
import { runAgent, type AgentTool } from "./agent-runner.js";
import { AI_MODELS } from "../config/ai-models.js";
import { callTradeUpAPI } from "../config/database.js";

// ============================================================================
// SCHEMAS
// ============================================================================

export const InsightsRequestSchema = z.object({
  tenantId: z.number(),
  scope: z.enum(["member", "segment", "tenant"]),
  memberId: z.number().optional(), // Required if scope is "member"
  segmentFilter: z.object({
    tier: z.string().optional(),
    joinedAfter: z.string().optional(),
    joinedBefore: z.string().optional(),
    minLifetimeValue: z.number().optional(),
    status: z.enum(["active", "inactive", "at_risk"]).optional(),
  }).optional(),
  questions: z.array(z.string()).optional(), // Specific questions to answer
});

export const MemberInsightSchema = z.object({
  memberId: z.number().optional(),
  segmentSize: z.number().optional(),

  // Behavior Analysis
  purchasePatterns: z.object({
    averageOrderValue: z.number(),
    purchaseFrequency: z.string(), // "weekly", "monthly", etc.
    preferredCategories: z.array(z.string()),
    peakPurchaseDays: z.array(z.string()),
    seasonalTrends: z.string(),
  }),

  // Credit Behavior
  creditUsage: z.object({
    totalEarned: z.number(),
    totalRedeemed: z.number(),
    redemptionRate: z.number(), // percentage
    averageTimeToRedeem: z.number(), // days
    expirationRisk: z.number(), // percentage at risk of expiring
  }),

  // Tier Analysis
  tierAnalysis: z.object({
    currentTier: z.string().optional(),
    tierTenure: z.number().optional(), // days at current tier
    progressToNextTier: z.number().optional(), // percentage
    recommendedActions: z.array(z.string()),
  }),

  // Value Metrics
  valueMetrics: z.object({
    lifetimeValue: z.number(),
    predictedNextYearValue: z.number(),
    valueSegment: z.enum(["high", "medium", "low", "at_risk"]),
    growthPotential: z.enum(["high", "medium", "low"]),
  }),

  // Actionable Insights
  insights: z.array(z.object({
    type: z.enum(["opportunity", "risk", "trend", "recommendation"]),
    priority: z.enum(["high", "medium", "low"]),
    title: z.string(),
    description: z.string(),
    suggestedAction: z.string().optional(),
  })),

  // Natural Language Summary
  summary: z.string(),
});

export type InsightsRequest = z.infer<typeof InsightsRequestSchema>;
export type MemberInsight = z.infer<typeof MemberInsightSchema>;

// ============================================================================
// AGENT CONFIGURATION
// ============================================================================

const INSIGHTS_SYSTEM_PROMPT = `You are a loyalty program analyst for TradeUp, a store credit and rewards platform.

YOUR ROLE:
- Analyze member behavior data to find actionable insights
- Identify opportunities to increase engagement and lifetime value
- Spot at-risk members before they churn
- Recommend tier progression strategies
- Provide clear, actionable recommendations

ANALYSIS FRAMEWORK:

1. PURCHASE PATTERNS
   - Frequency, recency, monetary value (RFM)
   - Category preferences
   - Seasonal trends
   - Day/time patterns

2. CREDIT BEHAVIOR
   - Earning vs redemption balance
   - Time to redeem (faster = more engaged)
   - Expiration risk
   - Bonus utilization

3. TIER PROGRESSION
   - Current tier tenure
   - Progress to next tier
   - Benefits utilization
   - Upgrade/downgrade risk

4. VALUE SEGMENTATION
   - High value: Top 20% by LTV
   - Medium value: Middle 60%
   - Low value: Bottom 20%
   - At-risk: Declining engagement

5. INSIGHT TYPES
   - Opportunity: Growth potential
   - Risk: Churn or value decline signals
   - Trend: Behavioral patterns
   - Recommendation: Specific actions to take

OUTPUT:
Provide insights in the MemberInsight schema format.
Always include a natural language summary that a non-technical user can understand.
Prioritize actionable recommendations over abstract observations.`;

// ============================================================================
// TOOLS
// ============================================================================

function createInsightsTools(tenantId: number): AgentTool[] {
  return [
    // Member Purchase History
    {
      definition: {
        name: "get_purchase_history",
        description: `Get member's purchase history and patterns.
Returns: orders, average value, frequency, categories, trends.`,
        input_schema: {
          type: "object" as const,
          properties: {
            memberId: { type: "number", description: "Member ID (optional for segment)" },
            segmentFilter: { type: "object", description: "Filter for segment analysis" },
            lookbackDays: { type: "number", description: "Days to analyze (default 365)" },
          },
          required: [],
        },
      },
      execute: async (input: unknown) => {
        const { memberId, segmentFilter, lookbackDays = 365 } = input as {
          memberId?: number;
          segmentFilter?: Record<string, unknown>;
          lookbackDays?: number;
        };

        const endpoint = memberId
          ? `/api/insights/member/${memberId}/purchases?days=${lookbackDays}`
          : `/api/insights/segment/purchases?days=${lookbackDays}`;

        return callTradeUpAPI<{
          totalOrders: number;
          totalRevenue: number;
          averageOrderValue: number;
          ordersByMonth: Record<string, number>;
          topCategories: Array<{ name: string; count: number; revenue: number }>;
          dayOfWeekDistribution: number[];
          recentOrders: Array<{ date: string; amount: number; items: number }>;
        }>(endpoint, {
          method: "POST",
          body: { segmentFilter },
          tenantId,
        });
      },
    },

    // Credit Activity
    {
      definition: {
        name: "get_credit_activity",
        description: `Get store credit earning and redemption patterns.
Returns: earned, redeemed, balance, redemption rate, expiration risk.`,
        input_schema: {
          type: "object" as const,
          properties: {
            memberId: { type: "number", description: "Member ID (optional)" },
            segmentFilter: { type: "object", description: "Filter for segment" },
          },
          required: [],
        },
      },
      execute: async (input: unknown) => {
        const { memberId, segmentFilter } = input as {
          memberId?: number;
          segmentFilter?: Record<string, unknown>;
        };

        const endpoint = memberId
          ? `/api/insights/member/${memberId}/credits`
          : `/api/insights/segment/credits`;

        return callTradeUpAPI<{
          totalEarned: number;
          totalRedeemed: number;
          currentBalance: number;
          redemptionRate: number;
          averageDaysToRedeem: number;
          expiringNext30Days: number;
          creditsBySource: Record<string, number>;
          monthlyTrend: Array<{ month: string; earned: number; redeemed: number }>;
        }>(endpoint, {
          method: "POST",
          body: { segmentFilter },
          tenantId,
        });
      },
    },

    // Tier Information
    {
      definition: {
        name: "get_tier_analysis",
        description: `Get tier distribution and progression data.
Returns: current tier, tenure, progress to next, benefits usage.`,
        input_schema: {
          type: "object" as const,
          properties: {
            memberId: { type: "number", description: "Member ID (optional)" },
            segmentFilter: { type: "object", description: "Filter for segment" },
          },
          required: [],
        },
      },
      execute: async (input: unknown) => {
        const { memberId, segmentFilter } = input as {
          memberId?: number;
          segmentFilter?: Record<string, unknown>;
        };

        const endpoint = memberId
          ? `/api/insights/member/${memberId}/tier`
          : `/api/insights/segment/tiers`;

        return callTradeUpAPI<{
          // For individual member
          currentTier?: string;
          tierSince?: string;
          spendToNextTier?: number;
          nextTierName?: string;
          benefitsUtilization?: Record<string, number>;

          // For segment
          tierDistribution?: Record<string, number>;
          averageTierTenure?: number;
          upgradeRate?: number;
          downgradeRate?: number;
        }>(endpoint, {
          method: "POST",
          body: { segmentFilter },
          tenantId,
        });
      },
    },

    // Engagement Metrics
    {
      definition: {
        name: "get_engagement_metrics",
        description: `Get engagement and activity metrics.
Returns: last activity, visit frequency, email opens, churn risk.`,
        input_schema: {
          type: "object" as const,
          properties: {
            memberId: { type: "number", description: "Member ID (optional)" },
            segmentFilter: { type: "object", description: "Filter for segment" },
          },
          required: [],
        },
      },
      execute: async (input: unknown) => {
        const { memberId, segmentFilter } = input as {
          memberId?: number;
          segmentFilter?: Record<string, unknown>;
        };

        const endpoint = memberId
          ? `/api/insights/member/${memberId}/engagement`
          : `/api/insights/segment/engagement`;

        return callTradeUpAPI<{
          lastActivityDate: string;
          daysSinceLastActivity: number;
          activityFrequency: string;
          emailOpenRate: number;
          pushNotificationRate: number;
          churnRiskScore: number;
          engagementTrend: "increasing" | "stable" | "declining";
        }>(endpoint, {
          method: "POST",
          body: { segmentFilter },
          tenantId,
        });
      },
    },

    // Cohort Comparison
    {
      definition: {
        name: "compare_to_cohort",
        description: `Compare member or segment to similar cohorts.
Returns: percentile rankings, peer comparisons.`,
        input_schema: {
          type: "object" as const,
          properties: {
            memberId: { type: "number", description: "Member ID" },
            comparisonType: {
              type: "string",
              enum: ["same_tier", "same_join_month", "same_value_segment"],
              description: "What to compare against",
            },
          },
          required: ["comparisonType"],
        },
      },
      execute: async (input: unknown) => {
        const { memberId, comparisonType } = input as {
          memberId?: number;
          comparisonType: string;
        };

        return callTradeUpAPI<{
          cohortSize: number;
          percentileRank: Record<string, number>; // metric -> percentile
          aboveAverage: string[];
          belowAverage: string[];
          topOpportunities: string[];
        }>(`/api/insights/cohort-comparison`, {
          method: "POST",
          body: { memberId, comparisonType },
          tenantId,
        });
      },
    },
  ];
}

// ============================================================================
// AGENT EXECUTOR
// ============================================================================

export interface InsightsAgentConfig {
  anthropicApiKey: string;
}

/**
 * Run insights analysis on a member or segment
 */
export async function runInsightsAgent(
  request: InsightsRequest,
  config: InsightsAgentConfig
): Promise<MemberInsight> {
  logger.info("Starting insights analysis", {
    tenantId: request.tenantId,
    scope: request.scope,
    memberId: request.memberId,
  });

  const tools = createInsightsTools(request.tenantId);

  const scopeDescription = request.scope === "member"
    ? `individual member (ID: ${request.memberId})`
    : request.scope === "segment"
    ? `segment with filters: ${JSON.stringify(request.segmentFilter)}`
    : "entire tenant member base";

  const questionsSection = request.questions?.length
    ? `\n\nSpecific questions to answer:\n${request.questions.map((q, i) => `${i + 1}. ${q}`).join("\n")}`
    : "";

  const userMessage = `Analyze the ${scopeDescription} and provide comprehensive insights.

Instructions:
1. Get purchase history using get_purchase_history
2. Get credit activity using get_credit_activity
3. Get tier analysis using get_tier_analysis
4. Get engagement metrics using get_engagement_metrics
5. If analyzing a single member, compare to their cohort using compare_to_cohort

Based on this data:
- Identify key behavioral patterns
- Calculate value metrics and segmentation
- Find opportunities for growth
- Spot any risks (churn, expiration, etc.)
- Provide actionable recommendations
${questionsSection}

Respond with a JSON object matching the MemberInsight schema.`;

  const result = await runAgent<MemberInsight>(
    {
      name: "insights-agent",
      model: AI_MODELS.SUBAGENT, // Sonnet 4.5
      systemPrompt: INSIGHTS_SYSTEM_PROMPT,
      tools,
      maxTurns: 12,
      onToolCall: (name, input, toolResult) => {
        logger.debug("Insights agent tool call", { name });
      },
    },
    userMessage,
    config.anthropicApiKey
  );

  if (!result.success || !result.result) {
    logger.error("Insights analysis failed", { error: result.error });
    throw new Error(`Insights analysis failed: ${result.error}`);
  }

  try {
    const validated = MemberInsightSchema.parse(result.result);
    logger.info("Insights analysis complete", {
      tenantId: request.tenantId,
      insightCount: validated.insights.length,
    });
    return validated;
  } catch (error) {
    logger.error("Invalid insights response", { error: String(error) });
    throw new Error("Invalid insights response from agent");
  }
}
