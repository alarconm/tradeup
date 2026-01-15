/**
 * Support Chat Widget Component
 *
 * Provides in-app support access for merchants.
 * Can integrate with Intercom, Gorgias, or a simple contact form.
 */

import React, { useState, useCallback } from 'react';
import {
  Modal,
  TextField,
  Select,
  Button,
  Banner,
  FormLayout,
  Text,
  BlockStack,
  InlineStack,
  Link,
  Icon,
  Box,
} from '@shopify/polaris';
import { ChatIcon, EmailIcon, QuestionCircleIcon } from '@shopify/polaris-icons';

interface SupportChatWidgetProps {
  shopDomain?: string;
  userEmail?: string;
  plan?: string;
  onClose?: () => void;
}

type SupportCategory = 'general' | 'billing' | 'technical' | 'feature' | 'bug';

interface SupportTicket {
  category: SupportCategory;
  subject: string;
  message: string;
  email: string;
}

const CATEGORY_OPTIONS = [
  { label: 'General Question', value: 'general' },
  { label: 'Billing & Subscription', value: 'billing' },
  { label: 'Technical Issue', value: 'technical' },
  { label: 'Feature Request', value: 'feature' },
  { label: 'Report a Bug', value: 'bug' },
];

const HELP_ARTICLES = [
  {
    title: 'Getting Started with TradeUp',
    url: 'https://help.cardflowlabs.com/getting-started',
    icon: QuestionCircleIcon,
  },
  {
    title: 'Setting Up Tiers & Rewards',
    url: 'https://help.cardflowlabs.com/tiers-rewards',
    icon: QuestionCircleIcon,
  },
  {
    title: 'Processing Trade-Ins',
    url: 'https://help.cardflowlabs.com/trade-ins',
    icon: QuestionCircleIcon,
  },
  {
    title: 'Integrations Guide',
    url: 'https://help.cardflowlabs.com/integrations',
    icon: QuestionCircleIcon,
  },
];

export default function SupportChatWidget({
  shopDomain,
  userEmail,
  plan,
  onClose,
}: SupportChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [ticket, setTicket] = useState<SupportTicket>({
    category: 'general',
    subject: '',
    message: '',
    email: userEmail || '',
  });

  const handleClose = useCallback(() => {
    setIsOpen(false);
    onClose?.();
  }, [onClose]);

  const handleSubmit = useCallback(async () => {
    if (!ticket.subject.trim() || !ticket.message.trim() || !ticket.email.trim()) {
      setError('Please fill in all required fields');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // In production, this would send to your support system
      const response = await fetch('/api/support/ticket', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Shopify-Shop-Domain': shopDomain || '',
        },
        body: JSON.stringify({
          ...ticket,
          shopDomain,
          plan,
          source: 'in_app_widget',
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to submit ticket');
      }

      setSubmitted(true);
    } catch (err) {
      // If API fails, fallback to email
      const mailtoLink = `mailto:support@cardflowlabs.com?subject=${encodeURIComponent(
        `[${ticket.category}] ${ticket.subject}`
      )}&body=${encodeURIComponent(
        `${ticket.message}\n\n---\nShop: ${shopDomain}\nPlan: ${plan}\nEmail: ${ticket.email}`
      )}`;
      window.open(mailtoLink, '_blank');
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  }, [ticket, shopDomain, plan]);

  const renderHelpArticles = () => (
    <BlockStack gap="300">
      <Text as="h3" variant="headingMd">Popular Help Articles</Text>
      {HELP_ARTICLES.map((article, index) => (
        <Link key={index} url={article.url} external removeUnderline>
          <InlineStack gap="200" align="start">
            <Icon source={article.icon} />
            <Text as="span" variant="bodyMd">{article.title}</Text>
          </InlineStack>
        </Link>
      ))}
    </BlockStack>
  );

  const renderContactOptions = () => (
    <BlockStack gap="400">
      <Text as="h3" variant="headingMd">Need More Help?</Text>

      <InlineStack gap="300">
        <Button
          icon={ChatIcon}
          onClick={() => setShowForm(true)}
        >
          Open Support Ticket
        </Button>

        <Button
          icon={EmailIcon}
          url="mailto:support@cardflowlabs.com"
          external
        >
          Email Us
        </Button>
      </InlineStack>

      <Text as="p" variant="bodySm" tone="subdued">
        Our support team typically responds within 24 hours.
        Premium plan users get priority support.
      </Text>
    </BlockStack>
  );

  const renderForm = () => (
    <BlockStack gap="400">
      {error && (
        <Banner tone="critical" onDismiss={() => setError(null)}>
          {error}
        </Banner>
      )}

      <FormLayout>
        <Select
          label="Category"
          options={CATEGORY_OPTIONS}
          value={ticket.category}
          onChange={(value) => setTicket({ ...ticket, category: value as SupportCategory })}
        />

        <TextField
          label="Your Email"
          type="email"
          value={ticket.email}
          onChange={(value) => setTicket({ ...ticket, email: value })}
          autoComplete="email"
        />

        <TextField
          label="Subject"
          value={ticket.subject}
          onChange={(value) => setTicket({ ...ticket, subject: value })}
          placeholder="Brief description of your issue"
          autoComplete="off"
        />

        <TextField
          label="Message"
          value={ticket.message}
          onChange={(value) => setTicket({ ...ticket, message: value })}
          multiline={4}
          placeholder="Please describe your issue in detail..."
          autoComplete="off"
        />
      </FormLayout>

      <InlineStack gap="200">
        <Button variant="primary" onClick={handleSubmit} loading={loading}>
          Submit Ticket
        </Button>
        <Button onClick={() => setShowForm(false)}>
          Back
        </Button>
      </InlineStack>
    </BlockStack>
  );

  const renderSuccess = () => (
    <BlockStack gap="300">
      <Banner tone="success">
        Your support ticket has been submitted successfully!
      </Banner>

      <Text as="p" variant="bodyMd">
        We've received your message and will get back to you within 24 hours.
        You'll receive a confirmation email at {ticket.email}.
      </Text>

      <Button onClick={handleClose}>Close</Button>
    </BlockStack>
  );

  return (
    <Modal
      open={isOpen}
      onClose={handleClose}
      title="TradeUp Support"
      secondaryActions={[{ content: 'Close', onAction: handleClose }]}
    >
      <Modal.Section>
        {submitted ? (
          renderSuccess()
        ) : showForm ? (
          renderForm()
        ) : (
          <BlockStack gap="500">
            {renderHelpArticles()}
            <Box borderBlockStartWidth="025" borderColor="border" paddingBlockStart="400">
              {renderContactOptions()}
            </Box>
          </BlockStack>
        )}
      </Modal.Section>
    </Modal>
  );
}

/**
 * Floating support button that opens the widget
 */
export function SupportButton({
  shopDomain,
  userEmail,
  plan,
}: Omit<SupportChatWidgetProps, 'onClose'>) {
  const [showWidget, setShowWidget] = useState(false);

  return (
    <>
      <div
        style={{
          position: 'fixed',
          bottom: '20px',
          right: '20px',
          zIndex: 1000,
        }}
      >
        <Button
          icon={ChatIcon}
          onClick={() => setShowWidget(true)}
          variant="primary"
        >
          Help
        </Button>
      </div>

      {showWidget && (
        <SupportChatWidget
          shopDomain={shopDomain}
          userEmail={userEmail}
          plan={plan}
          onClose={() => setShowWidget(false)}
        />
      )}
    </>
  );
}
