/**
 * useReviewPrompt Hook
 *
 * Custom hook for managing review prompt display timing.
 * Implements RC-006 timing logic to show prompts at optimal times.
 *
 * Usage:
 *   const { shouldShowPrompt, checkPrompt, promptId, onClose } = useReviewPrompt();
 *
 *   // On dashboard mount
 *   useEffect(() => {
 *     checkPrompt('dashboard');
 *   }, []);
 *
 *   // After successful action
 *   const handleTradeInApproved = async () => {
 *     await approveTradeIn(id);
 *     checkPrompt('trade_in_approved');
 *   };
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import {
  checkReviewPromptWithTiming,
  recordReviewPromptShown,
  ReviewPromptCheck,
} from '../admin/api'

export type PromptContext =
  | 'dashboard'
  | 'trade_in_approved'
  | 'member_enrolled'
  | 'onboarding'

interface UseReviewPromptOptions {
  /**
   * Whether to automatically check on mount.
   * Default: false
   */
  autoCheck?: boolean
  /**
   * Context for auto-check.
   * Default: 'dashboard'
   */
  autoCheckContext?: PromptContext
  /**
   * Delay in ms before auto-check.
   * Allows the page to fully load before checking.
   * Default: 2000 (2 seconds)
   */
  autoCheckDelay?: number
}

interface UseReviewPromptReturn {
  /**
   * Whether the review prompt should be shown
   */
  shouldShowPrompt: boolean
  /**
   * The prompt ID (set after prompt is shown)
   */
  promptId: number | null
  /**
   * Whether a check is in progress
   */
  isChecking: boolean
  /**
   * Last check result with timing details
   */
  lastCheckResult: ReviewPromptCheck | null
  /**
   * Check if prompt should be shown for the given context
   */
  checkPrompt: (context?: PromptContext, hasError?: boolean) => Promise<void>
  /**
   * Call this when the prompt modal is closed (by any means)
   */
  onPromptClose: () => void
  /**
   * Manually show the prompt (for testing or special cases)
   */
  forceShowPrompt: () => Promise<void>
}

export function useReviewPrompt(
  options: UseReviewPromptOptions = {}
): UseReviewPromptReturn {
  const {
    autoCheck = false,
    autoCheckContext = 'dashboard',
    autoCheckDelay = 2000,
  } = options

  const [shouldShowPrompt, setShouldShowPrompt] = useState(false)
  const [promptId, setPromptId] = useState<number | null>(null)
  const [isChecking, setIsChecking] = useState(false)
  const [lastCheckResult, setLastCheckResult] = useState<ReviewPromptCheck | null>(null)

  // Track if we've already shown the prompt this session
  const hasShownThisSession = useRef(false)

  /**
   * Check if the prompt should be shown for the given context.
   */
  const checkPrompt = useCallback(async (
    context: PromptContext = 'dashboard',
    hasError: boolean = false
  ) => {
    // Don't check if we've already shown the prompt this session
    if (hasShownThisSession.current) {
      return
    }

    setIsChecking(true)
    try {
      const result = await checkReviewPromptWithTiming(context, hasError)
      setLastCheckResult(result)

      if (result.should_show) {
        // Record that we're showing the prompt
        const { prompt_id } = await recordReviewPromptShown()
        setPromptId(prompt_id)
        setShouldShowPrompt(true)
        hasShownThisSession.current = true
      }
    } catch (error) {
      console.error('Failed to check review prompt:', error)
      // Don't show prompt on error
    } finally {
      setIsChecking(false)
    }
  }, [])

  /**
   * Handle prompt close
   */
  const onPromptClose = useCallback(() => {
    setShouldShowPrompt(false)
  }, [])

  /**
   * Force show the prompt (for testing)
   */
  const forceShowPrompt = useCallback(async () => {
    try {
      const { prompt_id } = await recordReviewPromptShown()
      setPromptId(prompt_id)
      setShouldShowPrompt(true)
      hasShownThisSession.current = true
    } catch (error) {
      console.error('Failed to force show review prompt:', error)
    }
  }, [])

  // Auto-check on mount if enabled
  useEffect(() => {
    if (!autoCheck) return

    const timer = setTimeout(() => {
      checkPrompt(autoCheckContext)
    }, autoCheckDelay)

    return () => clearTimeout(timer)
  }, [autoCheck, autoCheckContext, autoCheckDelay, checkPrompt])

  return {
    shouldShowPrompt,
    promptId,
    isChecking,
    lastCheckResult,
    checkPrompt,
    onPromptClose,
    forceShowPrompt,
  }
}

export default useReviewPrompt
