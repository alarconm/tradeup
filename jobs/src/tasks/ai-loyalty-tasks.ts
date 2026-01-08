/**
 * AI-Powered Loyalty Tasks
 *
 * Trigger.dev tasks that leverage AI agents for intelligent
 * loyalty program management.
 *
 * Scheduled Tasks:
 * - Weekly churn prevention scan
 * - Daily expiration rescue
 * - Monthly strategic review
 *
 * On-Demand Tasks:
 * - Member insights analysis
 * - Campaign planning
 * - Strategic goal planning
 */

import { schemaTask, schedules, logger } from "@trigger.dev/sdk/v3";
import { z } from "zod";
import { callTradeUpAPI, type Tenant } from "../config/database.js";
import {
  runInsightsAgent,
  runEngagementAgent,
  runOrchestrator,
} from "../agents/index.js";

// ============================================================================
// CONFIGURATION
// ============================================================================

const getAnthropicKey = () => process.env.ANTHROPIC_API_KEY || "";

// ============================================================================
// SCHEDULED: Weekly Churn Prevention Scan
// ============================================================================

export const weeklyChurnPreventionScan = schedules.task({
  id: "weekly-churn-prevention-scan",
  cron: "0 9 * * 1", // Every Monday at 9 AM UTC

  run: async () => {
    logger.info("Starting weekly churn prevention scan");

    const tenants = await callTradeUpAPI<Tenant[]>("/api/tenants/active");
    logger.info(`Scanning ${tenants.length} tenants for churn risk`);

    const results = [];

    for (const tenant of tenants) {
      try {
        const engagement = await runEngagementAgent(
          {
            tenantId: tenant.id,
            mode: "identify_at_risk",
          },
          { anthropicApiKey: getAnthropicKey() }
        );

        const atRiskCount = engagement.atRiskMembers?.length || 0;

        if (atRiskCount > 0) {
          // Store results for admin dashboard
          await callTradeUpAPI("/api/ai/churn-scan-results", {
            method: "POST",
            body: {
              atRiskMembers: engagement.atRiskMembers,
              recommendations: engagement.recommendations,
              summary: engagement.summary,
            },
            tenantId: tenant.id,
          });
        }

        results.push({
          tenantId: tenant.id,
          atRiskCount,
          topRecommendations: engagement.recommendations.slice(0, 3),
        });

        logger.info(`Tenant ${tenant.id} scan complete`, { atRiskCount });
      } catch (error) {
        logger.error(`Churn scan failed for tenant ${tenant.id}`, {
          error: String(error),
        });
        results.push({
          tenantId: tenant.id,
          atRiskCount: 0,
          error: String(error),
        });
      }
    }

    const totalAtRisk = results.reduce((sum, r) => sum + (r.atRiskCount || 0), 0);
    logger.info("Weekly churn scan complete", {
      tenantsScanned: tenants.length,
      totalAtRisk,
    });

    return { tenantsScanned: tenants.length, totalAtRisk, results };
  },
});

// ============================================================================
// SCHEDULED: Daily Credit Expiration Rescue
// ============================================================================

export const dailyExpirationRescue = schedules.task({
  id: "daily-expiration-rescue",
  cron: "0 10 * * *", // Daily at 10 AM UTC

  run: async () => {
    logger.info("Starting daily expiration rescue");

    const tenants = await callTradeUpAPI<Tenant[]>("/api/tenants/active");
    const results = [];

    for (const tenant of tenants) {
      try {
        const rescue = await runEngagementAgent(
          {
            tenantId: tenant.id,
            mode: "rescue_expiring",
            expirationDays: 7, // 7-day warning
          },
          { anthropicApiKey: getAnthropicKey() }
        );

        if (rescue.expirationRescue && rescue.expirationRescue.membersAtRisk > 0) {
          // Queue rescue emails
          await callTradeUpAPI("/api/notifications/queue-rescue-campaign", {
            method: "POST",
            body: {
              strategies: rescue.expirationRescue.rescueStrategies,
              membersAtRisk: rescue.expirationRescue.membersAtRisk,
              totalCreditsAtRisk: rescue.expirationRescue.totalCreditsAtRisk,
            },
            tenantId: tenant.id,
          });

          results.push({
            tenantId: tenant.id,
            membersAtRisk: rescue.expirationRescue.membersAtRisk,
            creditsAtRisk: rescue.expirationRescue.totalCreditsAtRisk,
          });
        }
      } catch (error) {
        logger.error(`Rescue failed for tenant ${tenant.id}`, {
          error: String(error),
        });
      }
    }

    const totalAtRisk = results.reduce((sum, r) => sum + r.membersAtRisk, 0);
    const totalCredits = results.reduce((sum, r) => sum + r.creditsAtRisk, 0);

    logger.info("Daily rescue scan complete", {
      tenantsProcessed: tenants.length,
      totalMembersAtRisk: totalAtRisk,
      totalCreditsAtRisk: totalCredits,
    });

    return { totalMembersAtRisk: totalAtRisk, totalCreditsAtRisk: totalCredits, results };
  },
});

// ============================================================================
// SCHEDULED: Monthly Strategic Review
// ============================================================================

export const monthlyStrategicReview = schedules.task({
  id: "monthly-strategic-review",
  cron: "0 6 1 * *", // 1st of month at 6 AM UTC

  run: async () => {
    logger.info("Starting monthly strategic review");

    const tenants = await callTradeUpAPI<Tenant[]>("/api/tenants/active");

    for (const tenant of tenants) {
      try {
        // Run orchestrator for monthly health check
        const plan = await runOrchestrator(
          {
            tenantId: tenant.id,
            goal: "Analyze last month's loyalty program performance and recommend optimizations for the coming month",
            constraints: {
              timeline: "next 30 days",
            },
          },
          { anthropicApiKey: getAnthropicKey() }
        );

        // Store strategic plan for admin review
        await callTradeUpAPI("/api/ai/monthly-review", {
          method: "POST",
          body: {
            plan,
            month: new Date().toISOString().slice(0, 7),
          },
          tenantId: tenant.id,
        });

        logger.info(`Strategic review complete for tenant ${tenant.id}`, {
          phases: plan.plan.phases.length,
          kpis: plan.kpis.length,
        });
      } catch (error) {
        logger.error(`Strategic review failed for tenant ${tenant.id}`, {
          error: String(error),
        });
      }
    }

    return { tenantsReviewed: tenants.length };
  },
});

// ============================================================================
// ON-DEMAND: Member Insights
// ============================================================================

const MemberInsightsPayload = z.object({
  tenantId: z.number(),
  memberId: z.number(),
  questions: z.array(z.string()).optional(),
});

export const analyzeMemberInsights = schemaTask({
  id: "analyze-member-insights",
  schema: MemberInsightsPayload,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 5000,
  },

  run: async ({ tenantId, memberId, questions }) => {
    logger.info("Analyzing member insights", { tenantId, memberId });

    const insights = await runInsightsAgent(
      {
        tenantId,
        scope: "member",
        memberId,
        questions,
      },
      { anthropicApiKey: getAnthropicKey() }
    );

    // Store insights for dashboard
    await callTradeUpAPI(`/api/members/${memberId}/ai-insights`, {
      method: "POST",
      body: insights,
      tenantId,
    });

    return insights;
  },
});

// ============================================================================
// ON-DEMAND: Segment Analysis
// ============================================================================

const SegmentAnalysisPayload = z.object({
  tenantId: z.number(),
  segmentFilter: z.object({
    tier: z.string().optional(),
    status: z.enum(["active", "inactive", "at_risk"]).optional(),
    minLifetimeValue: z.number().optional(),
    joinedAfter: z.string().optional(),
  }),
  questions: z.array(z.string()).optional(),
});

export const analyzeSegment = schemaTask({
  id: "analyze-segment",
  schema: SegmentAnalysisPayload,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 10000,
  },

  run: async ({ tenantId, segmentFilter, questions }) => {
    logger.info("Analyzing segment", { tenantId, segmentFilter });

    const insights = await runInsightsAgent(
      {
        tenantId,
        scope: "segment",
        segmentFilter,
        questions,
      },
      { anthropicApiKey: getAnthropicKey() }
    );

    return insights;
  },
});

// ============================================================================
// ON-DEMAND: Campaign Planning
// ============================================================================

const CampaignPlanningPayload = z.object({
  tenantId: z.number(),
  campaignGoal: z.string(),
});

export const planCampaign = schemaTask({
  id: "plan-campaign",
  schema: CampaignPlanningPayload,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 10000,
  },

  run: async ({ tenantId, campaignGoal }) => {
    logger.info("Planning campaign", { tenantId, campaignGoal });

    const plan = await runEngagementAgent(
      {
        tenantId,
        mode: "plan_campaign",
        campaignGoal,
      },
      { anthropicApiKey: getAnthropicKey() }
    );

    return plan;
  },
});

// ============================================================================
// ON-DEMAND: Strategic Goal Planning (Orchestrator)
// ============================================================================

const StrategicGoalPayload = z.object({
  tenantId: z.number(),
  goal: z.string(),
  budget: z.number().optional(),
  timeline: z.string().optional(),
  targetSegment: z.string().optional(),
  context: z.string().optional(),
});

export const planStrategicGoal = schemaTask({
  id: "plan-strategic-goal",
  schema: StrategicGoalPayload,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 30000, // Orchestrator takes longer
  },

  run: async ({ tenantId, goal, budget, timeline, targetSegment, context }) => {
    logger.info("Planning strategic goal", { tenantId, goal });

    const plan = await runOrchestrator(
      {
        tenantId,
        goal,
        constraints: { budget, timeline, targetSegment },
        context,
      },
      { anthropicApiKey: getAnthropicKey() }
    );

    // Store strategic plan
    await callTradeUpAPI("/api/ai/strategic-plans", {
      method: "POST",
      body: {
        goal,
        plan,
        createdAt: new Date().toISOString(),
      },
      tenantId,
    });

    return plan;
  },
});
