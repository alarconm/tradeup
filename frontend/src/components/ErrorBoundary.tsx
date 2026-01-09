/**
 * React Error Boundary Component
 *
 * Catches JavaScript errors anywhere in child component tree,
 * logs the error, and displays a fallback UI.
 */
import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import {
  Page,
  Layout,
  Card,
  Text,
  BlockStack,
  Button,
  Banner,
  Box,
} from '@shopify/polaris';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo });

    // Log error to console in development
    console.error('[TradeUp Error Boundary]', error, errorInfo);

    // Send error to Sentry
    try {
      import('../utils/sentry').then(({ captureException }) => {
        captureException(error, {
          componentStack: errorInfo.componentStack,
        });
      });
    } catch {
      // Sentry not available, ignore
    }
  }

  handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  handleReload = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    const { hasError, error } = this.state;
    const { children, fallback } = this.props;

    if (hasError) {
      // Custom fallback provided
      if (fallback) {
        return fallback;
      }

      // Default fallback UI using Polaris
      return (
        <Page title="Something went wrong">
          <Layout>
            <Layout.Section>
              <Banner tone="critical">
                <p>
                  We encountered an unexpected error. Our team has been notified.
                </p>
              </Banner>
            </Layout.Section>

            <Layout.Section>
              <Card>
                <BlockStack gap="400">
                  <Text as="h2" variant="headingMd">
                    Error Details
                  </Text>

                  <Box
                    background="bg-surface-secondary"
                    padding="400"
                    borderRadius="200"
                  >
                    <Text as="p" variant="bodyMd" fontWeight="bold">
                      {error?.name || 'Error'}
                    </Text>
                    <Text as="p" variant="bodySm" tone="subdued">
                      {error?.message || 'An unknown error occurred'}
                    </Text>
                    {this.state.errorInfo?.componentStack && (
                      <Box paddingBlockStart="200">
                        <Text as="p" variant="bodySm" fontWeight="semibold">
                          Component Stack:
                        </Text>
                        <Box
                          background="bg-surface"
                          padding="200"
                          borderRadius="100"
                        >
                          <pre style={{ fontSize: '10px', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }}>
                            {this.state.errorInfo.componentStack.split('\n').slice(0, 5).join('\n')}
                          </pre>
                        </Box>
                      </Box>
                    )}
                  </Box>

                  <BlockStack gap="200">
                    <Button onClick={this.handleReset}>Try Again</Button>
                    <Button variant="plain" onClick={this.handleReload}>
                      Reload Page
                    </Button>
                  </BlockStack>
                </BlockStack>
              </Card>
            </Layout.Section>

            <Layout.Section>
              <Card>
                <BlockStack gap="200">
                  <Text as="h3" variant="headingSm">
                    Need Help?
                  </Text>
                  <Text as="p" variant="bodySm" tone="subdued">
                    If this problem persists, please contact support at{' '}
                    <a href="mailto:support@cardflowlabs.com">
                      support@cardflowlabs.com
                    </a>
                  </Text>
                </BlockStack>
              </Card>
            </Layout.Section>
          </Layout>
        </Page>
      );
    }

    return children;
  }
}

/**
 * Simple error boundary for non-critical components.
 * Shows inline error message instead of full-page fallback.
 */
export class InlineErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('[TradeUp Inline Error]', error, errorInfo);
  }

  render(): ReactNode {
    const { hasError, error } = this.state;
    const { children, fallback } = this.props;

    if (hasError) {
      if (fallback) return fallback;

      return (
        <Box padding="400">
          <Banner tone="warning">
            <p>This section failed to load: {error?.message}</p>
          </Banner>
        </Box>
      );
    }

    return children;
  }
}
