/**
 * AI Model Configuration for TradeUp
 *
 * Using SOTA Claude models as of January 2026:
 * - Opus 4.5: Most capable, supports 'effort' parameter
 * - Sonnet 4.5: Best for agentic tasks, optimal speed/capability balance
 *
 * @see https://platform.claude.com/docs/en/about-claude/models/overview
 */

export const AI_MODELS = {
  /**
   * Claude Opus 4.5 - Maximum capability
   * Use for: Orchestrator agents, complex reasoning, high-stakes decisions
   * Unique: Supports 'effort' parameter for token control
   */
  ORCHESTRATOR: "claude-opus-4-5-20251101",

  /**
   * Claude Sonnet 4.5 - Optimal for agentic tasks
   * Use for: Subagents, tool use, coding, most AI operations
   * Recommended by Anthropic for agentic workloads
   */
  SUBAGENT: "claude-sonnet-4-5-20250929",

  /**
   * Alias versions (auto-update within ~1 week of new releases)
   * Use in development, pin specific versions in production
   */
  ALIASES: {
    OPUS: "claude-opus-4-5",
    SONNET: "claude-sonnet-4-5",
  },
} as const;

/**
 * Effort levels for Opus 4.5 (exclusive feature)
 * Controls how many tokens Claude uses when responding
 */
export const EFFORT_LEVELS = {
  LOW: "low",      // Quick responses, less reasoning
  MEDIUM: "medium", // Balanced
  HIGH: "high",    // Deep reasoning, thorough analysis
} as const;

/**
 * Agent configuration presets
 */
export const AGENT_PRESETS = {
  /** High-capability orchestrator for coordinating multiple agents */
  orchestrator: {
    model: AI_MODELS.ORCHESTRATOR,
    effort: EFFORT_LEVELS.HIGH,
    maxTokens: 8192,
  },

  /** Standard subagent for most tasks */
  subagent: {
    model: AI_MODELS.SUBAGENT,
    maxTokens: 4096,
  },

  /** Fast subagent for simple, high-volume tasks */
  lightweight: {
    model: AI_MODELS.SUBAGENT,
    maxTokens: 1024,
  },
} as const;

export type AIModel = typeof AI_MODELS[keyof typeof AI_MODELS];
export type EffortLevel = typeof EFFORT_LEVELS[keyof typeof EFFORT_LEVELS];
