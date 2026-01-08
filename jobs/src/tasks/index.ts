/**
 * TradeUp Background Jobs
 *
 * All tasks are exported here for easy importing and documentation.
 * Trigger.dev automatically discovers tasks from this directory.
 */

// Monthly Credits Distribution
export {
  monthlyCreditsSchedule,
  processTenantMonthlyCredits,
  processMonthlyCreditsBatch,
  issueMemberMonthlyCredit,
  triggerMonthlyCreditsManual,
} from "./monthly-credits.js";

// Credit Expiration
export {
  creditExpirationSchedule,
  expirationWarningSchedule,
  processTenantCreditExpiration,
  processCreditExpirationBatch,
  sendExpirationWarnings,
  triggerCreditExpirationManual,
} from "./credit-expiration.js";

// Shopify Events
export {
  handleOrderCreated,
  handleMembershipPurchase,
  processPurchaseCashback,
  handleCustomerCreated,
  handleCustomerUpdated,
  handleTradeInSubmitted,
  sendWelcomeNotification,
} from "./shopify-events.js";

// AI-Powered Loyalty Tasks
export {
  // Scheduled
  weeklyChurnPreventionScan,
  dailyExpirationRescue,
  monthlyStrategicReview,
  // On-demand
  analyzeMemberInsights,
  analyzeSegment,
  planCampaign,
  planStrategicGoal,
} from "./ai-loyalty-tasks.js";
