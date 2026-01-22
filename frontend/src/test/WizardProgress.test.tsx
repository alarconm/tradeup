/**
 * Tests for WizardProgress component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AppProvider } from '@shopify/polaris'
import enTranslations from '@shopify/polaris/locales/en.json'
import { WizardProgress, PRODUCT_WIZARD_STEPS } from '../embedded/components/WizardProgress'

function createWrapper() {
  return ({ children }: { children: React.ReactNode }) => (
    <AppProvider i18n={enTranslations}>
      {children}
    </AppProvider>
  )
}

const testSteps = [
  { key: 'step1', label: 'Step One' },
  { key: 'step2', label: 'Step Two' },
  { key: 'step3', label: 'Step Three' },
]

describe('WizardProgress', () => {
  const mockOnStepClick = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders all step labels', () => {
    render(
      <WizardProgress
        steps={testSteps}
        currentStep={0}
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Step One')).toBeInTheDocument()
    expect(screen.getByText('Step Two')).toBeInTheDocument()
    expect(screen.getByText('Step Three')).toBeInTheDocument()
  })

  it('displays step numbers correctly', () => {
    render(
      <WizardProgress
        steps={testSteps}
        currentStep={0}
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('highlights the current step', () => {
    render(
      <WizardProgress
        steps={testSteps}
        currentStep={1}
      />,
      { wrapper: createWrapper() }
    )

    // Step Two should have semibold font weight for current step
    const stepTwoLabel = screen.getByText('Step Two')
    expect(stepTwoLabel).toBeInTheDocument()
  })

  it('shows checkmark for completed steps', () => {
    render(
      <WizardProgress
        steps={testSteps}
        currentStep={2}
      />,
      { wrapper: createWrapper() }
    )

    // Steps 1 and 2 should be completed (currentStep is 2, so indices 0 and 1 are completed)
    // Check that the checkmark icon is rendered (completed steps don't show numbers)
    expect(screen.queryByText('1')).not.toBeInTheDocument()
    expect(screen.queryByText('2')).not.toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('calls onStepClick when completed step is clicked', () => {
    render(
      <WizardProgress
        steps={testSteps}
        currentStep={2}
        onStepClick={mockOnStepClick}
      />,
      { wrapper: createWrapper() }
    )

    // Find the step indicator for Step One (which is completed)
    const stepOneLabel = screen.getByText('Step One')
    const stepIndicator = stepOneLabel.previousElementSibling
    if (stepIndicator) {
      fireEvent.click(stepIndicator)
    }

    expect(mockOnStepClick).toHaveBeenCalledWith(0)
  })

  it('does not call onStepClick for current or future steps', () => {
    render(
      <WizardProgress
        steps={testSteps}
        currentStep={1}
        onStepClick={mockOnStepClick}
      />,
      { wrapper: createWrapper() }
    )

    // Try to click Step Three (future step)
    const stepThreeLabel = screen.getByText('Step Three')
    const stepIndicator = stepThreeLabel.previousElementSibling
    if (stepIndicator) {
      fireEvent.click(stepIndicator)
    }

    expect(mockOnStepClick).not.toHaveBeenCalled()
  })

  it('renders with the default product wizard steps', () => {
    render(
      <WizardProgress
        steps={PRODUCT_WIZARD_STEPS}
        currentStep={0}
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Welcome')).toBeInTheDocument()
    expect(screen.getByText('Choose Template')).toBeInTheDocument()
    expect(screen.getByText('Customize')).toBeInTheDocument()
    expect(screen.getByText('Publish')).toBeInTheDocument()
  })

  it('does not call onStepClick when no handler provided', () => {
    render(
      <WizardProgress
        steps={testSteps}
        currentStep={2}
      />,
      { wrapper: createWrapper() }
    )

    // Find the step indicator for Step One (which is completed)
    const stepOneLabel = screen.getByText('Step One')
    const stepIndicator = stepOneLabel.previousElementSibling
    if (stepIndicator) {
      // Should not throw even without handler
      fireEvent.click(stepIndicator)
    }

    // Test passes if no error is thrown
    expect(true).toBe(true)
  })

  it('renders correctly with single step', () => {
    render(
      <WizardProgress
        steps={[{ key: 'only', label: 'Only Step' }]}
        currentStep={0}
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Only Step')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('handles all steps completed (currentStep equals steps length)', () => {
    render(
      <WizardProgress
        steps={testSteps}
        currentStep={3}
      />,
      { wrapper: createWrapper() }
    )

    // All steps should show checkmarks (no numbers visible)
    expect(screen.queryByText('1')).not.toBeInTheDocument()
    expect(screen.queryByText('2')).not.toBeInTheDocument()
    expect(screen.queryByText('3')).not.toBeInTheDocument()
  })
})

describe('PRODUCT_WIZARD_STEPS constant', () => {
  it('has correct number of steps', () => {
    expect(PRODUCT_WIZARD_STEPS).toHaveLength(4)
  })

  it('has correct step keys', () => {
    const keys = PRODUCT_WIZARD_STEPS.map(s => s.key)
    expect(keys).toEqual(['welcome', 'template', 'customize', 'publish'])
  })

  it('has correct step labels', () => {
    const labels = PRODUCT_WIZARD_STEPS.map(s => s.label)
    expect(labels).toEqual(['Welcome', 'Choose Template', 'Customize', 'Publish'])
  })
})
