/**
 * Credit Expiration Tasks
 *
 * Handles automatic expiration of store credits that have passed their
 * expiration date. Runs daily to clean up expired credits.
 *
 * Architecture:
 * 1. Daily scheduled task at midnight UTC
 * 2. Fans out to per-tenant processing
 * 3. Batch processes expired credits with checkpointing
 * 4. Also provides warning notifications for upcoming expirations
 *
 * @see https://trigger.dev/docs/guides/background-jobs
 */

import { task, schedules, logger, schemaTask } from "@trigger.dev/sdk/v3";
import { z } from "zod";
import { callTradeUpAPI, type Tenant } from "../config/database.js";

// ============================================================================
// SCHEMAS
// ============================================================================

const TenantPayload = z.object({
  tenantId: z.number(),
});

const ExpirationBatchPayload = z.object({
  tenantId: z.number(),
  cursor: z.number().nullable(),
  batchSize: z.number().default(100),
});

const ExpirationWarningPayload = z.object({
  tenantId: z.number(),
  daysAhead: z.number().default(7),
});

const ManualExpirationPayload = z.object({
  tenantId: z.number(),
  dryRun: z.boolean().default(false),
});

// ============================================================================
// SCHEDULED TRIGGER - Runs daily at midnight UTC
// ============================================================================

export const creditExpirationSchedule = schedules.task({
  id: "credit-expiration-schedule",
  cron: "0 0 * * *", // Daily at midnight UTC

  run: async (payload, { ctx }) => {
    logger.info("Starting daily credit expiration processing");

    // Get all tenants (even inactive ones may have credits to expire)
    const tenants = await callTradeUpAPI<Tenant[]>("/api/tenants/all");

    logger.info(`Processing credit expiration for ${tenants.length} tenants`);

    // Fan out to per-tenant processing
    const results = await Promise.allSettled(
      tenants.map((tenant) =>
        processTenantCreditExpiration.trigger({
          tenantId: tenant.id,
        })
      )
    );

    const succeeded = results.filter((r) => r.status === "fulfilled").length;
    const failed = results.filter((r) => r.status === "rejected").length;

    logger.info("Credit expiration schedule complete", {
      totalTenants: tenants.length,
      succeeded,
      failed,
    });

    return { totalTenants: tenants.length, succeeded, failed };
  },
});

// ============================================================================
// EXPIRATION WARNING SCHEDULE - Runs daily at 9 AM UTC
// ============================================================================

export const expirationWarningSchedule = schedules.task({
  id: "expiration-warning-schedule",
  cron: "0 9 * * *", // Daily at 9 AM UTC

  run: async (payload, { ctx }) => {
    logger.info("Starting expiration warning notifications");

    const tenants = await callTradeUpAPI<Tenant[]>("/api/tenants/active");

    const results = await Promise.allSettled(
      tenants.map((tenant) =>
        sendExpirationWarnings.trigger({
          tenantId: tenant.id,
          daysAhead: 7, // 7-day warning
        })
      )
    );

    const succeeded = results.filter((r) => r.status === "fulfilled").length;

    logger.info("Expiration warnings complete", {
      totalTenants: tenants.length,
      succeeded,
    });

    return { totalTenants: tenants.length, succeeded };
  },
});

// ============================================================================
// PER-TENANT EXPIRATION PROCESSING
// ============================================================================

export const processTenantCreditExpiration = schemaTask({
  id: "process-tenant-credit-expiration",
  schema: TenantPayload,
  retry: {
    maxAttempts: 3,
    factor: 2,
    minTimeoutInMs: 5000,
    maxTimeoutInMs: 60000,
  },

  run: async ({ tenantId }) => {

    logger.info(`Processing credit expiration for tenant ${tenantId}`);

    let cursor: number | null = null;
    let totalProcessed = 0;
    let totalExpired = 0;
    let totalAmount = 0;
    let totalErrors = 0;

    while (true) {
      const batchResult = await processCreditExpirationBatch.triggerAndWait({
        tenantId,
        cursor,
        batchSize: 100,
      });

      if (!batchResult.ok) {
        logger.error("Batch processing failed", { tenantId, cursor });
        throw new Error(`Expiration batch failed for tenant ${tenantId}`);
      }

      const { processed, expired, expiredAmount, errors, nextCursor, hasMore } =
        batchResult.output;

      totalProcessed += processed;
      totalExpired += expired;
      totalAmount += expiredAmount;
      totalErrors += errors;
      cursor = nextCursor;

      logger.info("Expiration batch complete", {
        tenantId,
        batchProcessed: processed,
        batchExpired: expired,
        hasMore,
      });

      if (!hasMore) {
        break;
      }
    }

    const result = {
      tenantId,
      totalProcessed,
      totalExpired,
      totalAmount,
      totalErrors,
    };

    logger.info("Tenant credit expiration complete", result);

    return result;
  },
});

// ============================================================================
// BATCH EXPIRATION PROCESSING
// ============================================================================

export const processCreditExpirationBatch = schemaTask({
  id: "process-credit-expiration-batch",
  schema: ExpirationBatchPayload,
  retry: {
    maxAttempts: 2,
    factor: 2,
    minTimeoutInMs: 2000,
  },

  run: async ({ tenantId, cursor, batchSize }) => {

    // Call Flask API to process a batch of expired credits
    const response = await callTradeUpAPI<{
      processed: number;
      expired: number;
      expiredAmount: number;
      errors: number;
      nextCursor: number | null;
      hasMore: boolean;
    }>("/api/scheduled-tasks/expiration/process-batch", {
      method: "POST",
      body: { cursor, batchSize },
      tenantId,
    });

    return response;
  },
});

// ============================================================================
// EXPIRATION WARNING NOTIFICATIONS
// ============================================================================

export const sendExpirationWarnings = schemaTask({
  id: "send-expiration-warnings",
  schema: ExpirationWarningPayload,
  retry: {
    maxAttempts: 2,
    minTimeoutInMs: 5000,
  },

  run: async ({ tenantId, daysAhead }) => {

    logger.info(`Sending expiration warnings for tenant ${tenantId}`, { daysAhead });

    // Get members with expiring credits
    const preview = await callTradeUpAPI<{
      members_with_expiring_credits: number;
      total_amount_expiring: number;
      members: Array<{
        member_id: number;
        member_number: string;
        email: string | null;
        total_expiring: number;
        credits: Array<{
          amount: number;
          expires_at: string;
        }>;
      }>;
    }>(`/api/scheduled-tasks/expiration/upcoming?days=${daysAhead}`, {
      tenantId,
    });

    if (preview.members_with_expiring_credits === 0) {
      logger.info("No expiring credits to warn about", { tenantId });
      return { sent: 0, skipped: 0 };
    }

    let sent = 0;
    let skipped = 0;

    // Send warning to each member with an email
    for (const member of preview.members) {
      if (!member.email) {
        skipped++;
        continue;
      }

      try {
        await callTradeUpAPI("/api/notifications/send", {
          method: "POST",
          body: {
            type: "credit_expiration_warning",
            memberId: member.member_id,
            data: {
              totalExpiring: member.total_expiring,
              daysRemaining: daysAhead,
              credits: member.credits,
            },
          },
          tenantId,
        });
        sent++;
      } catch (error) {
        logger.error("Failed to send warning email", {
          memberId: member.member_id,
          error: String(error),
        });
      }
    }

    logger.info("Expiration warnings sent", { tenantId, sent, skipped });

    return { sent, skipped };
  },
});

// ============================================================================
// MANUAL TRIGGER - For admin UI
// ============================================================================

export const triggerCreditExpirationManual = schemaTask({
  id: "trigger-credit-expiration-manual",
  schema: ManualExpirationPayload,

  run: async ({ tenantId, dryRun }) => {

    logger.info("Manual credit expiration trigger", { tenantId, dryRun });

    if (dryRun) {
      // Get preview of what would expire
      const preview = await callTradeUpAPI<{
        processed: number;
        expired_entries: number;
        members_affected: number;
        total_expired: number;
      }>("/api/scheduled-tasks/expiration/preview", {
        tenantId,
      });

      return {
        dryRun: true,
        ...preview,
      };
    }

    // Trigger actual processing
    const result = await processTenantCreditExpiration.triggerAndWait({ tenantId });

    if (!result.ok) {
      throw new Error("Credit expiration processing failed");
    }

    return {
      dryRun: false,
      ...result.output,
    };
  },
});
