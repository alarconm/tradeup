/**
 * Review Prompt Modal Component
 *
 * Non-intrusive modal to prompt merchants for Shopify App Store reviews.
 * Shows after eligibility criteria are met (30+ days, 10+ trade-ins or 50+ members).
 *
 * Story: RC-004 - Create review prompt UI component
 */
import { useState, useCallback } from 'react';
import {
  Modal,
  TextContainer,
  Text,
  BlockStack,
  InlineStack,
  Button,
  Box,
  Icon,
} from '@shopify/polaris';
import { StarFilledIcon } from '@shopify/polaris-icons';
import { api } from '../admin/api';

// Shopify App Store URL for TradeUp
// Format: https://apps.shopify.com/{app-handle}
const APP_STORE_URL = 'https://apps.shopify.com/tradeup-by-cardflow-labs';

interface ReviewPromptModalProps {
  open: boolean;
  promptId: number | null;
  onClose: () => void;
}

type ResponseType = 'clicked' | 'reminded_later' | 'dismissed';

export function ReviewPromptModal({ open, promptId, onClose }: ReviewPromptModalProps) {
  const [responding, setResponding] = useState(false);

  /**
   * Record the merchant's response to the prompt
   */
  const recordResponse = useCallback(async (response: ResponseType) => {
    if (!promptId) return;

    setResponding(true);
    try {
      await api.post('/review-prompt/response', {
        prompt_id: promptId,
        response,
      });
    } catch (error) {
      // Log error but don't block the user action
      console.error('Failed to record review prompt response:', error);
    } finally {
      setResponding(false);
    }
  }, [promptId]);

  /**
   * Handle "Rate Now" - open App Store and record click
   */
  const handleRateNow = useCallback(async () => {
    await recordResponse('clicked');
    window.open(APP_STORE_URL, '_blank', 'noopener,noreferrer');
    onClose();
  }, [recordResponse, onClose]);

  /**
   * Handle "Remind Me Later" - schedules prompt for 7 days
   */
  const handleRemindLater = useCallback(async () => {
    await recordResponse('reminded_later');
    onClose();
  }, [recordResponse, onClose]);

  /**
   * Handle "Dismiss" - won't show again for 60 days
   */
  const handleDismiss = useCallback(async () => {
    await recordResponse('dismissed');
    onClose();
  }, [recordResponse, onClose]);

  return (
    <Modal
      open={open}
      onClose={handleDismiss}
      title="Enjoying TradeUp?"
      titleHidden={false}
    >
      <Modal.Section>
        <BlockStack gap="400">
          {/* Star icons for visual appeal */}
          <Box paddingBlockStart="200">
            <InlineStack align="center" gap="100">
              {[1, 2, 3, 4, 5].map((star) => (
                <span key={star} style={{ color: '#FFB800' }}>
                  <Icon source={StarFilledIcon} />
                </span>
              ))}
            </InlineStack>
          </Box>

          {/* Friendly message */}
          <TextContainer>
            <Text as="p" variant="bodyMd">
              Thank you for being a valued TradeUp user! Your feedback helps us
              improve and helps other merchants discover our app.
            </Text>
            <Text as="p" variant="bodyMd">
              If you have a moment, we would really appreciate a review on the
              Shopify App Store. It only takes a minute!
            </Text>
          </TextContainer>

          {/* Action buttons */}
          <Box paddingBlockStart="200">
            <BlockStack gap="300">
              <Button
                variant="primary"
                onClick={handleRateNow}
                loading={responding}
                fullWidth
              >
                Rate on App Store
              </Button>
              <InlineStack gap="300" align="center" blockAlign="center">
                <Button
                  variant="plain"
                  onClick={handleRemindLater}
                  disabled={responding}
                >
                  Remind me later
                </Button>
                <Text as="span" variant="bodySm" tone="subdued">
                  |
                </Text>
                <Button
                  variant="plain"
                  onClick={handleDismiss}
                  disabled={responding}
                >
                  No thanks
                </Button>
              </InlineStack>
            </BlockStack>
          </Box>
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}

export default ReviewPromptModal;
