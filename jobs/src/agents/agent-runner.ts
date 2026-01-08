/**
 * Agent Runner - Claude Agent SDK Integration
 *
 * Lightweight agent runner that uses Claude's tool-use capabilities
 * to orchestrate calls to existing ORB APIs for pricing, analysis, etc.
 *
 * Philosophy: ORB has the tools, agents have the brains.
 */

import Anthropic from "@anthropic-ai/sdk";
import { z } from "zod";
import { AI_MODELS, AGENT_PRESETS } from "../config/ai-models.js";
import { logger } from "@trigger.dev/sdk/v3";

// ============================================================================
// TYPES
// ============================================================================

export interface AgentTool {
  definition: Anthropic.Tool;
  execute: (input: unknown) => Promise<unknown>;
}

export interface AgentConfig {
  name: string;
  model?: string;
  systemPrompt: string;
  tools: AgentTool[];
  maxTurns?: number;
  onToolCall?: (name: string, input: unknown, result: unknown) => void;
}

export interface AgentResult<T = unknown> {
  success: boolean;
  result: T | null;
  error?: string;
  toolCalls: Array<{
    name: string;
    input: unknown;
    result: unknown;
  }>;
  totalTokens: number;
}

// ============================================================================
// AGENT RUNNER
// ============================================================================

/**
 * Run an agent with the given configuration
 *
 * Uses Claude's agentic loop pattern:
 * 1. Send message with tools
 * 2. If Claude wants to use a tool, execute it
 * 3. Send tool result back
 * 4. Repeat until Claude gives final answer
 */
export async function runAgent<T>(
  config: AgentConfig,
  userMessage: string,
  anthropicApiKey: string
): Promise<AgentResult<T>> {
  const client = new Anthropic({ apiKey: anthropicApiKey });
  const model = config.model || AI_MODELS.SUBAGENT;
  const maxTurns = config.maxTurns || 10;

  const toolCalls: AgentResult["toolCalls"] = [];
  let totalTokens = 0;

  // Build tool definitions
  const tools = config.tools.map((t) => t.definition);
  const toolExecutors = new Map(
    config.tools.map((t) => [t.definition.name, t.execute])
  );

  // Conversation history
  const messages: Anthropic.MessageParam[] = [
    { role: "user", content: userMessage },
  ];

  try {
    for (let turn = 0; turn < maxTurns; turn++) {
      logger.debug(`Agent ${config.name} turn ${turn + 1}`, { model });

      // Call Claude
      const response = await client.messages.create({
        model,
        max_tokens: 4096,
        system: config.systemPrompt,
        tools,
        messages,
      });

      totalTokens += response.usage.input_tokens + response.usage.output_tokens;

      // Check if we're done
      if (response.stop_reason === "end_turn") {
        // Extract final text response
        const textBlock = response.content.find((c) => c.type === "text");
        if (textBlock && textBlock.type === "text") {
          // Try to parse as JSON if it looks like JSON
          const text = textBlock.text.trim();
          let result: T | null = null;

          try {
            const jsonMatch = text.match(/```json\s*([\s\S]*?)\s*```/) ||
                              text.match(/\{[\s\S]*\}/);
            if (jsonMatch) {
              result = JSON.parse(jsonMatch[1] || jsonMatch[0]) as T;
            } else {
              result = text as unknown as T;
            }
          } catch {
            result = text as unknown as T;
          }

          return {
            success: true,
            result,
            toolCalls,
            totalTokens,
          };
        }

        return {
          success: true,
          result: null,
          toolCalls,
          totalTokens,
        };
      }

      // Handle tool use
      if (response.stop_reason === "tool_use") {
        const assistantContent = response.content;
        messages.push({ role: "assistant", content: assistantContent });

        const toolResults: Anthropic.ToolResultBlockParam[] = [];

        for (const block of assistantContent) {
          if (block.type === "tool_use") {
            const executor = toolExecutors.get(block.name);

            if (!executor) {
              toolResults.push({
                type: "tool_result",
                tool_use_id: block.id,
                content: `Error: Unknown tool '${block.name}'`,
                is_error: true,
              });
              continue;
            }

            try {
              logger.debug(`Executing tool: ${block.name}`, { input: block.input });
              const result = await executor(block.input);

              toolCalls.push({
                name: block.name,
                input: block.input,
                result,
              });

              if (config.onToolCall) {
                config.onToolCall(block.name, block.input, result);
              }

              toolResults.push({
                type: "tool_result",
                tool_use_id: block.id,
                content: JSON.stringify(result),
              });
            } catch (error) {
              logger.error(`Tool ${block.name} failed`, { error: String(error) });
              toolResults.push({
                type: "tool_result",
                tool_use_id: block.id,
                content: `Error: ${String(error)}`,
                is_error: true,
              });
            }
          }
        }

        messages.push({ role: "user", content: toolResults });
      }
    }

    // Max turns exceeded
    return {
      success: false,
      result: null,
      error: `Agent exceeded max turns (${maxTurns})`,
      toolCalls,
      totalTokens,
    };
  } catch (error) {
    logger.error(`Agent ${config.name} failed`, { error: String(error) });
    return {
      success: false,
      result: null,
      error: String(error),
      toolCalls,
      totalTokens,
    };
  }
}

// ============================================================================
// HELPER: Create tool from ORB API endpoint
// ============================================================================

export function createApiTool(
  name: string,
  description: string,
  inputSchema: Anthropic.Tool["input_schema"],
  apiUrl: string,
  endpoint: string,
  apiKey?: string
): AgentTool {
  return {
    definition: {
      name,
      description,
      input_schema: inputSchema,
    },
    execute: async (input) => {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (apiKey) {
        headers["X-API-Key"] = apiKey;
      }

      const response = await fetch(`${apiUrl}${endpoint}`, {
        method: "POST",
        headers,
        body: JSON.stringify(input),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      return response.json();
    },
  };
}
