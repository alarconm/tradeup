/**
 * WizardProgress - Horizontal step indicator for multi-step wizards
 *
 * Shows progress through wizard steps with clickable navigation back
 * (but not forward - users must complete steps in order).
 */

import { Box, InlineStack, Text, Icon } from '@shopify/polaris';
import { CheckIcon } from '@shopify/polaris-icons';

interface WizardStep {
  key: string;
  label: string;
}

interface WizardProgressProps {
  steps: WizardStep[];
  currentStep: number;
  onStepClick?: (stepIndex: number) => void;
}

export function WizardProgress({ steps, currentStep, onStepClick }: WizardProgressProps) {
  return (
    <Box paddingBlockEnd="600">
      <InlineStack gap="200" align="center" blockAlign="center">
        {steps.map((step, index) => {
          const isCompleted = index < currentStep;
          const isCurrent = index === currentStep;
          const isClickable = isCompleted && onStepClick;

          return (
            <InlineStack key={step.key} gap="200" align="center" blockAlign="center">
              {/* Step indicator */}
              <div
                onClick={() => isClickable && onStepClick(index)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  backgroundColor: isCompleted
                    ? '#008060'
                    : isCurrent
                      ? '#5c6ac4'
                      : '#e1e3e5',
                  color: (isCompleted || isCurrent) ? 'white' : '#6d7175',
                  fontWeight: 600,
                  fontSize: '14px',
                  cursor: isClickable ? 'pointer' : 'default',
                  transition: 'all 0.2s ease',
                }}
              >
                {isCompleted ? (
                  <Icon source={CheckIcon} />
                ) : (
                  index + 1
                )}
              </div>

              {/* Step label */}
              <Text
                as="span"
                variant="bodyMd"
                fontWeight={isCurrent ? 'semibold' : 'regular'}
                tone={isCurrent ? undefined : 'subdued'}
              >
                {step.label}
              </Text>

              {/* Connector line (except for last step) */}
              {index < steps.length - 1 && (
                <div
                  style={{
                    width: '40px',
                    height: '2px',
                    backgroundColor: isCompleted ? '#008060' : '#e1e3e5',
                    marginLeft: '8px',
                    marginRight: '8px',
                  }}
                />
              )}
            </InlineStack>
          );
        })}
      </InlineStack>
    </Box>
  );
}

// Default wizard steps for the product setup wizard
export const PRODUCT_WIZARD_STEPS: WizardStep[] = [
  { key: 'welcome', label: 'Welcome' },
  { key: 'template', label: 'Choose Template' },
  { key: 'customize', label: 'Customize' },
  { key: 'publish', label: 'Publish' },
];
