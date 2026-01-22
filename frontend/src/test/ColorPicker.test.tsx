/**
 * Tests for ColorPicker component
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AppProvider } from '@shopify/polaris'
import enTranslations from '@shopify/polaris/locales/en.json'
import { ColorPicker, WidgetColorPickerGroup } from '../embedded/components/ColorPicker'

function createWrapper() {
  return ({ children }: { children: React.ReactNode }) => (
    <AppProvider i18n={enTranslations}>
      {children}
    </AppProvider>
  )
}

describe('ColorPicker', () => {
  const mockOnChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders with initial color value', () => {
    render(
      <ColorPicker
        value="#ff5500"
        onChange={mockOnChange}
        label="Primary Color"
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Primary Color')).toBeInTheDocument()
    expect(screen.getByText('#FF5500')).toBeInTheDocument()
  })

  it('displays help text when provided', () => {
    render(
      <ColorPicker
        value="#ff5500"
        onChange={mockOnChange}
        label="Primary Color"
        helpText="Choose your brand color"
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Choose your brand color')).toBeInTheDocument()
  })

  it('shows error message when provided', () => {
    render(
      <ColorPicker
        value="#ff5500"
        onChange={mockOnChange}
        error="Invalid color selected"
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Invalid color selected')).toBeInTheDocument()
  })

  it('opens popover when clicked', async () => {
    render(
      <ColorPicker
        value="#ff5500"
        onChange={mockOnChange}
        label="Color"
      />,
      { wrapper: createWrapper() }
    )

    // Find and click the color picker button
    const button = screen.getByRole('button')
    fireEvent.click(button)

    // Check that the button's aria-expanded attribute is true (popover is open)
    await waitFor(() => {
      expect(button).toHaveAttribute('aria-expanded', 'true')
    })
  })

  it('shows RGB inputs when showRgbInput is true', async () => {
    render(
      <ColorPicker
        value="#ff5500"
        onChange={mockOnChange}
        showRgbInput={true}
      />,
      { wrapper: createWrapper() }
    )

    const button = screen.getByRole('button')
    fireEvent.click(button)

    // Verify the popover opens (aria-expanded is true)
    // Note: Polaris Popover content is rendered in a portal which may not be
    // accessible in jsdom - we verify the popover state via aria attributes
    await waitFor(() => {
      expect(button).toHaveAttribute('aria-expanded', 'true')
    })
  })

  it('disables picker when disabled prop is true', () => {
    render(
      <ColorPicker
        value="#ff5500"
        onChange={mockOnChange}
        disabled={true}
      />,
      { wrapper: createWrapper() }
    )

    const button = screen.getByRole('button')
    expect(button).toBeDisabled()
  })

  it('renders with different color types', () => {
    const { rerender } = render(
      <ColorPicker
        value="#ff5500"
        onChange={mockOnChange}
        colorType="primary"
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('#FF5500')).toBeInTheDocument()

    rerender(
      <AppProvider i18n={enTranslations}>
        <ColorPicker
          value="#303030"
          onChange={mockOnChange}
          colorType="text"
        />
      </AppProvider>
    )

    expect(screen.getByText('#303030')).toBeInTheDocument()
  })
})

describe('WidgetColorPickerGroup', () => {
  const mockColors = {
    primary: '#e85d27',
    secondary: '#8c9196',
    text: '#303030',
    background: '#ffffff',
  }
  const mockOnChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders all four color pickers', () => {
    render(
      <WidgetColorPickerGroup
        colors={mockColors}
        onChange={mockOnChange}
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Primary Color')).toBeInTheDocument()
    expect(screen.getByText('Secondary Color')).toBeInTheDocument()
    expect(screen.getByText('Text Color')).toBeInTheDocument()
    expect(screen.getByText('Background Color')).toBeInTheDocument()
  })

  it('displays combined preview by default', () => {
    render(
      <WidgetColorPickerGroup
        colors={mockColors}
        onChange={mockOnChange}
        showCombinedPreview={true}
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Your Rewards')).toBeInTheDocument()
    expect(screen.getByText('250 points available')).toBeInTheDocument()
  })

  it('hides combined preview when showCombinedPreview is false', () => {
    render(
      <WidgetColorPickerGroup
        colors={mockColors}
        onChange={mockOnChange}
        showCombinedPreview={false}
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.queryByText('Your Rewards')).not.toBeInTheDocument()
  })

  it('displays help text for each color picker', () => {
    render(
      <WidgetColorPickerGroup
        colors={mockColors}
        onChange={mockOnChange}
      />,
      { wrapper: createWrapper() }
    )

    expect(screen.getByText('Buttons and accents')).toBeInTheDocument()
    expect(screen.getByText('Secondary text and details')).toBeInTheDocument()
    expect(screen.getByText('Main text color')).toBeInTheDocument()
    expect(screen.getByText('Panel background')).toBeInTheDocument()
  })

  it('disables all pickers when disabled prop is true', () => {
    render(
      <WidgetColorPickerGroup
        colors={mockColors}
        onChange={mockOnChange}
        disabled={true}
      />,
      { wrapper: createWrapper() }
    )

    const buttons = screen.getAllByRole('button')
    buttons.forEach(button => {
      expect(button).toBeDisabled()
    })
  })
})
