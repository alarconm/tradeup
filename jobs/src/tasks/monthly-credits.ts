/**
 * Monthly Credits Distribution Tasks
 *
 * Durable, scalable implementation of monthly credit distribution
 * using Trigger.dev for reliable background job processing.
 *
 * Architecture:
 * 1. Scheduled task runs on 1st of each month
 * 2. Fans out to per-tenant tasks for isolation
 * 3. Each tenant processes members in batches with checkpointing
 * 4. Individual credit issuance is idempotent
 *
 * @see https://trigger.dev/docs/guides/background-jobs
 */

import { task, schedules, logger, schemaTask } from "@trigger.dev/sdk/v3";
import { z } from "zod";
import { callTradeUpAPI, type Tenant, type Member } from "../config/database.js";

// ============================================================================
// SCHEMAS
// ============================================================================

const TenantPayloadSchema = z.object({
  tenantId: z.number(),
});

const MemberCreditPayloadSchema = z.object({
  memberId: z.number(),
  tenantId: z.number(),
  monthKey: z.string(),
});

const BatchPayloadSchema = z.object({
  tenantId: z.number(),
  cursor: z.number().nullable(),
  monthKey: z.string(),
  batchSize: z.number().default(100),
});

const ManualTriggerSchema = z.object({
  tenantId: z.number(),
  dryRun: z.boolean().default(false),
});

// ============================================================================
// SCHEDULED TRIGGER - Runs 1st of each month at 6 AM UTC
// ============================================================================

export const monthlyCreditsSchedule = schedules.task({
  id: "monthly-credits-schedule",
  cron: "0 6 1 * *",

  run: async () => {
    const monthKey = new Date().toISOString().slice(0, 7);
    logger.info("Starting monthly credit distribution", { monthKey });

    const tenants = await callTradeUpAPI<Tenant[]>("/api/tenants/active");
    logger.info(`Found ${tenants.length} active tenants to process`);

    const results = await Promise.allSettled(
      tenants.map((tenant) =>
        processTenantMonthlyCredits.trigger({ tenantId: tenant.id })
      )
    );

    const succeeded = results.filter((r) => r.status === "fulfilled").length;
    const failed = results.filter((r) => r.status === "rejected").length;

    logger.info("Monthly credits schedule complete", {
      totalTenants: tenants.length,
      succeeded,
      failed,
    });

    return { totalTenants: tenants.length, succeeded, failed };
  },
});

// ============================================================================
// PER-TENANT PROCESSING
// ============================================================================

export const processTenantMonthlyCredits = schemaTask({
  id: "process-tenant-monthly-credits",
  schema: TenantPayloadSchema,
  retry: {
    maxAttempts: 3,
    factor: 2,
    minTimeoutInMs: 5000,
    maxTimeoutInMs: 60000,
  },

  run: async ({ tenantId }) => {
    const monthKey = new Date().toISOString().slice(0, 7);
    logger.info(`Processing monthly credits for tenant ${tenantId}`, { monthKey });

    let cursor: number | null = null;
    let totalProcessed = 0;
    let totalCredited = 0;
    let totalSkipped = 0;
    let totalErrors = 0;

    while (true) {
      const batchResult = await processMonthlyCreditsBatch.triggerAndWait({
        tenantId,
        cursor,
        monthKey,
        batchSize: 100,
      });

      if (!batchResult.ok) {
        logger.error("Batch processing failed", { tenantId, cursor });
        throw new Error(`Batch failed for tenant ${tenantId}`);
      }

      const { processed, credited, skipped, errors, nextCursor, hasMore } =
        batchResult.output;

      totalProcessed += processed;
      totalCredited += credited;
      totalSkipped += skipped;
      totalErrors += errors;
      cursor = nextCursor;

      logger.info("Batch complete", {
        tenantId,
        batchProcessed: processed,
        totalProcessed,
        hasMore,
      });

      if (!hasMore) break;
    }

    const result = {
      tenantId,
      monthKey,
      totalProcessed,
      totalCredited,
      totalSkipped,
      totalErrors,
    };

    logger.info("Tenant monthly credits complete", result);
    return result;
  },
});

// ============================================================================
// BATCH PROCESSING
// ============================================================================

export const processMonthlyCreditsBatch = schemaTask({
  id: "process-monthly-credits-batch",
  schema: BatchPayloadSchema,
  retry: {
    maxAttempts: 2,
    factor: 2,
    minTimeoutInMs: 2000,
  },

  run: async ({ tenantId, cursor, monthKey, batchSize }) => {
    const response = await callTradeUpAPI<{
      members: Member[];
      nextCursor: number | null;
      hasMore: boolean;
    }>("/api/scheduled-tasks/monthly-credits/eligible-batch", {
      method: "POST",
      body: { tenantId, cursor, batchSize, monthKey },
      tenantId,
    });

    const { members, nextCursor, hasMore } = response;

    let credited = 0;
    let skipped = 0;
    let errors = 0;

    for (const member of members) {
      try {
        const result = await issueMemberMonthlyCredit.triggerAndWait({
          memberId: member.id,
          tenantId,
          monthKey,
        });

        if (result.ok) {
          if (result.output.credited) {
            credited++;
          } else {
            skipped++;
          }
        } else {
          errors++;
        }
      } catch (error) {
        logger.error("Failed to process member", {
          memberId: member.id,
          error: String(error),
        });
        errors++;
      }
    }

    return {
      processed: members.length,
      credited,
      skipped,
      errors,
      nextCursor,
      hasMore,
    };
  },
});

// ============================================================================
// INDIVIDUAL CREDIT ISSUANCE
// ============================================================================

export const issueMemberMonthlyCredit = schemaTask({
  id: "issue-member-monthly-credit",
  schema: MemberCreditPayloadSchema,
  retry: {
    maxAttempts: 3,
    factor: 2,
    minTimeoutInMs: 1000,
  },

  run: async ({ memberId, tenantId, monthKey }) => {
    const result = await callTradeUpAPI<{
      credited: boolean;
      amount: number | null;
      reason: string;
    }>("/api/scheduled-tasks/monthly-credits/issue", {
      method: "POST",
      body: { memberId, monthKey },
      tenantId,
    });

    if (result.credited) {
      logger.info("Issued monthly credit", { memberId, amount: result.amount });
    } else {
      logger.debug("Skipped member", { memberId, reason: result.reason });
    }

    return result;
  },
});

// ============================================================================
// MANUAL TRIGGER
// ============================================================================

export const triggerMonthlyCreditsManual = schemaTask({
  id: "trigger-monthly-credits-manual",
  schema: ManualTriggerSchema,

  run: async ({ tenantId, dryRun }) => {
    logger.info("Manual monthly credits trigger", { tenantId, dryRun });

    if (dryRun) {
      const preview = await callTradeUpAPI<{
        processed: number;
        credited: number;
        total_amount: number;
        details: Array<{
          member_id: number;
          member_number: string;
          tier: string;
          amount: number;
        }>;
      }>("/api/scheduled-tasks/monthly-credits/preview", { tenantId });

      return { dryRun: true, ...preview };
    }

    const result = await processTenantMonthlyCredits.triggerAndWait({ tenantId });

    if (!result.ok) {
      throw new Error("Monthly credits processing failed");
    }

    return { dryRun: false, ...result.output };
  },
});
