/**
 * TradeUp AI Agents
 *
 * Claude-powered agents for intelligent loyalty program management:
 *
 * SUBAGENTS (Sonnet 4.5 - fast, efficient):
 * - Insights Agent: Member behavior analysis, tier recommendations
 * - Engagement Agent: Churn prevention, campaign planning
 *
 * ORCHESTRATOR (Opus 4.5 - maximum capability):
 * - Coordinates multiple agents for complex goals
 * - Creates strategic plans from high-level objectives
 *
 * All agents integrate with Trigger.dev for durable execution.
 */

// Agent Runner (core infrastructure)
export {
  runAgent,
  createApiTool,
  type AgentTool,
  type AgentConfig,
  type AgentResult,
} from "./agent-runner.js";

// Insights Agent (Sonnet 4.5)
export {
  runInsightsAgent,
  type InsightsRequest,
  type MemberInsight,
} from "./insights-agent.js";

// Engagement Agent (Sonnet 4.5)
export {
  runEngagementAgent,
  type EngagementRequest,
  type EngagementPlan,
} from "./engagement-agent.js";

// Orchestrator (Opus 4.5)
export {
  runOrchestrator,
  type OrchestratorRequest,
  type OrchestratorPlan,
} from "./orchestrator.js";
