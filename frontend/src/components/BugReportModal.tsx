/**
 * Bug Report Modal Component
 * Allows merchants to submit bug reports and feature requests from within the app.
 */
import { useState, useCallback } from 'react';
import {
  Modal,
  FormLayout,
  TextField,
  Select,
  Button,
  Banner,
  TextContainer,
} from '@shopify/polaris';
import { api } from '../admin/api';
import { useToast } from '../contexts/ToastContext';

interface BugReportModalProps {
  open: boolean;
  onClose: () => void;
}

const CATEGORIES = [
  { label: 'Bug Report', value: 'bug' },
  { label: 'Feature Request', value: 'feature_request' },
  { label: 'Question', value: 'question' },
  { label: 'Other', value: 'other' },
];

const SEVERITIES = [
  { label: 'Low - Minor issue, workaround available', value: 'low' },
  { label: 'Medium - Affects workflow but manageable', value: 'medium' },
  { label: 'High - Significant impact on operations', value: 'high' },
  { label: 'Critical - Cannot use the app', value: 'critical' },
];

export function BugReportModal({ open, onClose }: BugReportModalProps) {
  const { showSuccess, showError } = useToast();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('bug');
  const [severity, setSeverity] = useState('medium');
  const [stepsToReproduce, setStepsToReproduce] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [reportId, setReportId] = useState('');

  const resetForm = useCallback(() => {
    setTitle('');
    setDescription('');
    setCategory('bug');
    setSeverity('medium');
    setStepsToReproduce('');
    setSubmitted(false);
    setReportId('');
  }, []);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [onClose, resetForm]);

  const handleSubmit = useCallback(async () => {
    if (!title.trim()) {
      showError('Please enter a title');
      return;
    }
    if (!description.trim()) {
      showError('Please enter a description');
      return;
    }

    setSubmitting(true);

    try {
      // Collect browser info
      const browserInfo = {
        userAgent: navigator.userAgent,
        language: navigator.language,
        platform: navigator.platform,
        screenSize: `${window.screen.width}x${window.screen.height}`,
        viewportSize: `${window.innerWidth}x${window.innerHeight}`,
        url: window.location.href,
        timestamp: new Date().toISOString(),
      };

      const response = await api.post('/settings/bug-report', {
        title: title.trim(),
        description: description.trim(),
        category,
        severity,
        steps_to_reproduce: stepsToReproduce.trim(),
        browser_info: browserInfo,
      });

      if (response.data.success) {
        setReportId(response.data.report_id);
        setSubmitted(true);
        showSuccess('Bug report submitted successfully!');
      } else {
        showError(response.data.error || 'Failed to submit report');
      }
    } catch (error) {
      console.error('Error submitting bug report:', error);
      showError('Failed to submit bug report. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }, [title, description, category, severity, stepsToReproduce, showSuccess, showError]);

  const renderForm = () => (
    <FormLayout>
      <Select
        label="Category"
        options={CATEGORIES}
        value={category}
        onChange={setCategory}
      />

      <TextField
        label="Title"
        value={title}
        onChange={setTitle}
        placeholder="Brief description of the issue"
        autoComplete="off"
        maxLength={200}
      />

      <TextField
        label="Description"
        value={description}
        onChange={setDescription}
        multiline={4}
        placeholder="Please describe the issue in detail..."
        autoComplete="off"
        maxLength={2000}
      />

      {category === 'bug' && (
        <>
          <Select
            label="Severity"
            options={SEVERITIES}
            value={severity}
            onChange={setSeverity}
            helpText="How significantly does this affect your workflow?"
          />

          <TextField
            label="Steps to Reproduce (Optional)"
            value={stepsToReproduce}
            onChange={setStepsToReproduce}
            multiline={3}
            placeholder="1. Go to...&#10;2. Click on...&#10;3. Observe..."
            autoComplete="off"
            maxLength={1000}
          />
        </>
      )}
    </FormLayout>
  );

  const renderSuccess = () => (
    <TextContainer>
      <Banner tone="success">
        <p>Thank you for your feedback!</p>
      </Banner>
      <p style={{ marginTop: '16px' }}>
        Your report has been submitted with reference ID: <strong>{reportId}</strong>
      </p>
      <p style={{ marginTop: '8px' }}>
        Our team will review your submission and get back to you if needed.
        You can contact us at{' '}
        <a href="mailto:mike@orbsportscards.com">mike@orbsportscards.com</a>{' '}
        if you have any urgent issues.
      </p>
    </TextContainer>
  );

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title={submitted ? 'Report Submitted' : 'Submit Feedback'}
      primaryAction={
        submitted
          ? {
              content: 'Close',
              onAction: handleClose,
            }
          : {
              content: 'Submit Report',
              onAction: handleSubmit,
              loading: submitting,
              disabled: !title.trim() || !description.trim(),
            }
      }
      secondaryActions={
        submitted
          ? [
              {
                content: 'Submit Another',
                onAction: resetForm,
              },
            ]
          : [
              {
                content: 'Cancel',
                onAction: handleClose,
              },
            ]
      }
    >
      <Modal.Section>{submitted ? renderSuccess() : renderForm()}</Modal.Section>
    </Modal>
  );
}

export default BugReportModal;
