/**
 * Loyalty Program Orchestrator
 *
 * Opus 4.5 powered coordinator that orchestrates multiple agents
 * to accomplish complex, multi-step loyalty program goals.
 *
 * Examples:
 * - "Reduce churn for Gold tier by 20%"
 * - "Design a Q1 retention campaign"
 * - "Analyze why Silver members aren't upgrading"
 * - "Create a win-back program for lapsed members"
 *
 * The orchestrator breaks down goals, delegates to specialist agents,
 * and synthesizes results into actionable plans.
 */

import { z } from "zod";
import { logger } from "@trigger.dev/sdk/v3";
import { runAgent, type AgentTool } from "./agent-runner.js";
import { AI_MODELS } from "../config/ai-models.js";
import { runInsightsAgent, type InsightsRequest } from "./insights-agent.js";
import { runEngagementAgent, type EngagementRequest } from "./engagement-agent.js";
import { callTradeUpAPI } from "../config/database.js";

// ============================================================================
// SCHEMAS
// ============================================================================

export const OrchestratorRequestSchema = z.object({
  tenantId: z.number(),
  goal: z.string(), // Natural language goal
  constraints: z.object({
    budget: z.number().optional(), // Max credit spend
    timeline: z.string().optional(), // e.g., "Q1 2026", "next 30 days"
    targetSegment: z.string().optional(), // e.g., "Gold tier", "inactive members"
  }).optional(),
  context: z.string().optional(), // Additional context
});

export const OrchestratorPlanSchema = z.object({
  goal: z.string(),
  understanding: z.string(), // Orchestrator's interpretation of the goal

  // Strategic analysis
  analysis: z.object({
    currentState: z.string(),
    targetState: z.string(),
    gaps: z.array(z.string()),
    opportunities: z.array(z.string()),
    risks: z.array(z.string()),
  }),

  // Tactical plan
  plan: z.object({
    phases: z.array(z.object({
      name: z.string(),
      duration: z.string(),
      objectives: z.array(z.string()),
      actions: z.array(z.object({
        action: z.string(),
        owner: z.enum(["automated", "admin", "marketing"]),
        priority: z.enum(["critical", "high", "medium", "low"]),
        estimatedImpact: z.string(),
      })),
      successCriteria: z.array(z.string()),
    })),
    totalDuration: z.string(),
    estimatedInvestment: z.number().optional(),
    expectedROI: z.string(),
  }),

  // Agent insights used
  agentInsights: z.array(z.object({
    agent: z.string(),
    keyFindings: z.array(z.string()),
    recommendations: z.array(z.string()),
  })),

  // Immediate next steps
  nextSteps: z.array(z.object({
    step: z.string(),
    timeline: z.string(),
    resources: z.string(),
  })),

  // Success metrics
  kpis: z.array(z.object({
    metric: z.string(),
    current: z.string(),
    target: z.string(),
    measurementFrequency: z.string(),
  })),

  // Executive summary
  executiveSummary: z.string(),
});

export type OrchestratorRequest = z.infer<typeof OrchestratorRequestSchema>;
export type OrchestratorPlan = z.infer<typeof OrchestratorPlanSchema>;

// ============================================================================
// ORCHESTRATOR CONFIGURATION
// ============================================================================

const ORCHESTRATOR_SYSTEM_PROMPT = `You are the Chief Strategy Officer AI for TradeUp, a store credit and loyalty platform.

YOUR ROLE:
- Take high-level business goals and create comprehensive execution plans
- Coordinate specialist agents (Insights, Engagement) to gather data
- Synthesize findings into actionable strategies
- Balance quick wins with long-term growth

STRATEGIC FRAMEWORK:

1. UNDERSTAND THE GOAL
   - Clarify metrics (what does success look like?)
   - Identify constraints (budget, timeline, resources)
   - Understand the "why" behind the request

2. ANALYZE CURRENT STATE
   - Use Insights Agent for member behavior data
   - Identify gaps between current and target state
   - Find root causes of problems

3. DESIGN THE STRATEGY
   - Break into phases (quick wins → sustained growth)
   - Prioritize by impact and effort
   - Consider dependencies and sequencing

4. CREATE ENGAGEMENT TACTICS
   - Use Engagement Agent for campaign design
   - Match tactics to member segments
   - Plan multi-touch sequences

5. DEFINE SUCCESS
   - Set specific, measurable KPIs
   - Establish baselines and targets
   - Plan measurement cadence

WORKING WITH AGENTS:
- Insights Agent: Answers "what's happening?" and "why?"
- Engagement Agent: Answers "how do we reach them?" and "what should we offer?"

You orchestrate these agents to build comprehensive plans.

OUTPUT:
Provide plans in the OrchestratorPlan schema format.
Be strategic but actionable.
Always include an executive summary for stakeholders.`;

// ============================================================================
// ORCHESTRATOR TOOLS (Agent Coordination)
// ============================================================================

function createOrchestratorTools(
  tenantId: number,
  anthropicApiKey: string
): AgentTool[] {
  return [
    // Run Insights Agent
    {
      definition: {
        name: "run_insights_analysis",
        description: `Run the Insights Agent to analyze member behavior.
Use for: understanding current state, identifying patterns, finding opportunities.

Scope options:
- "tenant": Analyze entire member base
- "segment": Analyze specific segment (provide filters)
- "member": Analyze individual member`,
        input_schema: {
          type: "object" as const,
          properties: {
            scope: {
              type: "string",
              enum: ["member", "segment", "tenant"],
              description: "Analysis scope",
            },
            memberId: { type: "number", description: "For member scope" },
            segmentFilter: {
              type: "object",
              description: "For segment scope: tier, status, etc.",
            },
            questions: {
              type: "array",
              items: { type: "string" },
              description: "Specific questions to answer",
            },
          },
          required: ["scope"],
        },
      },
      execute: async (input: unknown) => {
        const { scope, memberId, segmentFilter, questions } = input as {
          scope: "member" | "segment" | "tenant";
          memberId?: number;
          segmentFilter?: Record<string, unknown>;
          questions?: string[];
        };

        logger.info("Orchestrator calling Insights Agent", { scope });

        const request: InsightsRequest = {
          tenantId,
          scope,
          memberId,
          segmentFilter,
          questions,
        };

        const result = await runInsightsAgent(request, { anthropicApiKey });
        return result;
      },
    },

    // Run Engagement Agent
    {
      definition: {
        name: "run_engagement_planning",
        description: `Run the Engagement Agent for campaign planning and churn prevention.

Modes:
- "identify_at_risk": Find members likely to churn
- "plan_campaign": Design a multi-channel campaign
- "rescue_expiring": Create plan to save expiring credits
- "optimize_outreach": Best way to reach specific member
- "personalize_offer": Create personalized offers`,
        input_schema: {
          type: "object" as const,
          properties: {
            mode: {
              type: "string",
              enum: ["identify_at_risk", "plan_campaign", "rescue_expiring", "optimize_outreach", "personalize_offer"],
              description: "Engagement mode",
            },
            memberId: { type: "number", description: "For member-specific modes" },
            campaignGoal: { type: "string", description: "For plan_campaign mode" },
            expirationDays: { type: "number", description: "For rescue_expiring mode" },
          },
          required: ["mode"],
        },
      },
      execute: async (input: unknown) => {
        const { mode, memberId, campaignGoal, expirationDays } = input as {
          mode: "identify_at_risk" | "plan_campaign" | "rescue_expiring" | "optimize_outreach" | "personalize_offer";
          memberId?: number;
          campaignGoal?: string;
          expirationDays?: number;
        };

        logger.info("Orchestrator calling Engagement Agent", { mode });

        const request: EngagementRequest = {
          tenantId,
          mode,
          memberId,
          campaignGoal,
          expirationDays,
        };

        const result = await runEngagementAgent(request, { anthropicApiKey });
        return result;
      },
    },

    // Get Tenant Overview
    {
      definition: {
        name: "get_tenant_overview",
        description: `Get high-level tenant metrics and health.
Use at the start to understand the current state.`,
        input_schema: {
          type: "object" as const,
          properties: {},
          required: [],
        },
      },
      execute: async () => {
        return callTradeUpAPI<{
          totalMembers: number;
          activeMembers: number;
          membersByTier: Record<string, number>;
          totalCreditsOutstanding: number;
          monthlyCreditsIssued: number;
          monthlyCreditsRedeemed: number;
          redemptionRate: number;
          churnRate: number;
          averageMemberLifetime: number;
          topPerformingPromotion: string;
          healthScore: number;
        }>(`/api/tenants/overview`, { tenantId });
      },
    },

    // Get Historical Trends
    {
      definition: {
        name: "get_historical_trends",
        description: `Get historical data to understand trends.
Use to see if metrics are improving or declining.`,
        input_schema: {
          type: "object" as const,
          properties: {
            metrics: {
              type: "array",
              items: { type: "string" },
              description: "Metrics to trend: churn_rate, redemption_rate, new_members, etc.",
            },
            period: {
              type: "string",
              enum: ["30d", "90d", "180d", "365d"],
              description: "Lookback period",
            },
          },
          required: ["metrics"],
        },
      },
      execute: async (input: unknown) => {
        const { metrics, period = "90d" } = input as {
          metrics: string[];
          period?: string;
        };

        return callTradeUpAPI<{
          trends: Record<string, Array<{ date: string; value: number }>>;
          summary: Record<string, { start: number; end: number; change: number }>;
        }>(`/api/tenants/trends`, {
          method: "POST",
          body: { metrics, period },
          tenantId,
        });
      },
    },
  ];
}

// ============================================================================
// ORCHESTRATOR EXECUTOR
// ============================================================================

export interface OrchestratorConfig {
  anthropicApiKey: string;
}

/**
 * Run the orchestrator to create a strategic plan
 */
export async function runOrchestrator(
  request: OrchestratorRequest,
  config: OrchestratorConfig
): Promise<OrchestratorPlan> {
  const startTime = Date.now();

  logger.info("Starting orchestrator", {
    tenantId: request.tenantId,
    goal: request.goal,
    constraints: request.constraints,
  });

  const tools = createOrchestratorTools(request.tenantId, config.anthropicApiKey);

  const constraintsSection = request.constraints
    ? `\nConstraints:
- Budget: ${request.constraints.budget ? `$${request.constraints.budget}` : "Not specified"}
- Timeline: ${request.constraints.timeline || "Not specified"}
- Target segment: ${request.constraints.targetSegment || "All members"}`
    : "";

  const contextSection = request.context
    ? `\n\nAdditional context: ${request.context}`
    : "";

  const userMessage = `Goal: ${request.goal}
${constraintsSection}${contextSection}

Instructions:
1. First, get_tenant_overview to understand the current state
2. Use run_insights_analysis to dig into relevant data
3. Use run_engagement_planning to design tactical approaches
4. Optionally get_historical_trends if you need to understand trajectory
5. Synthesize everything into a comprehensive strategic plan

Be thorough but efficient. Focus on actionable recommendations.
Respond with a JSON object matching the OrchestratorPlan schema.`;

  const result = await runAgent<OrchestratorPlan>(
    {
      name: "orchestrator",
      model: AI_MODELS.ORCHESTRATOR, // Opus 4.5 for maximum capability
      systemPrompt: ORCHESTRATOR_SYSTEM_PROMPT,
      tools,
      maxTurns: 20, // Allow more turns for complex coordination
      onToolCall: (name, input, toolResult) => {
        logger.info("Orchestrator delegating to agent", {
          tool: name,
          duration: Date.now() - startTime,
        });
      },
    },
    userMessage,
    config.anthropicApiKey
  );

  if (!result.success || !result.result) {
    logger.error("Orchestrator failed", { error: result.error });
    throw new Error(`Orchestrator failed: ${result.error}`);
  }

  try {
    const validated = OrchestratorPlanSchema.parse(result.result);

    logger.info("Orchestrator complete", {
      tenantId: request.tenantId,
      goal: request.goal,
      phases: validated.plan.phases.length,
      kpis: validated.kpis.length,
      processingTime: Date.now() - startTime,
      totalTokens: result.totalTokens,
    });

    return validated;
  } catch (error) {
    logger.error("Invalid orchestrator response", { error: String(error) });
    throw new Error("Invalid orchestrator response");
  }
}
