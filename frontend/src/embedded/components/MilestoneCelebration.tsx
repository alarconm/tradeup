/**
 * MilestoneCelebration - Celebration modal for achievements
 *
 * Shows a fun celebration when users hit milestones like
 * first member, first trade-in, etc.
 */

import {
  Modal,
  BlockStack,
  Text,
  Button,
  InlineStack,
  Box,
} from '@shopify/polaris';
import { useState, useEffect, useMemo } from 'react';

interface Milestone {
  id: string;
  title: string;
  message: string;
  icon: string;
}

interface MilestoneCelebrationProps {
  milestone: Milestone | null;
  onDismiss: () => void;
}

// Map icon names to emoji
const iconEmojis: Record<string, string> = {
  star: '⭐',
  community: '👥',
  trophy: '🏆',
  exchange: '🔄',
  chart: '📈',
  rocket: '🚀',
  fire: '🔥',
  heart: '❤️',
  medal: '🏅',
  crown: '👑',
};

export function MilestoneCelebration({ milestone, onDismiss }: MilestoneCelebrationProps) {
  const [showConfetti, setShowConfetti] = useState(false);

  useEffect(() => {
    if (milestone) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setShowConfetti(true);
      // Auto-dismiss confetti after animation
      const timer = setTimeout(() => setShowConfetti(false), 3000);
      return () => clearTimeout(timer);
    }
  }, [milestone]);

  if (!milestone) return null;

  const emoji = iconEmojis[milestone.icon] || '🎉';

  return (
    <Modal
      open={!!milestone}
      onClose={onDismiss}
      title=""
      primaryAction={{
        content: 'Awesome!',
        onAction: onDismiss,
      }}
    >
      <Modal.Section>
        <BlockStack gap="400" inlineAlign="center">
          {/* Confetti effect (CSS-based) */}
          {showConfetti && <ConfettiEffect />}

          {/* Large emoji icon */}
          <Box paddingBlock="400">
            <Text as="span" variant="heading3xl">
              {emoji}
            </Text>
          </Box>

          {/* Title */}
          <Text as="h2" variant="headingLg" alignment="center">
            {milestone.title}
          </Text>

          {/* Message */}
          <Text as="p" variant="bodyLg" tone="subdued" alignment="center">
            {milestone.message}
          </Text>

          {/* Celebration text */}
          <Box paddingBlockStart="200">
            <Text as="p" variant="bodySm" tone="success" alignment="center">
              Keep up the great work! 🎉
            </Text>
          </Box>
        </BlockStack>
      </Modal.Section>
    </Modal>
  );
}

// Confetti colors
const confettiColors = [
  '#FF6B6B', // Red
  '#4ECDC4', // Teal
  '#45B7D1', // Blue
  '#96CEB4', // Green
  '#FFEAA7', // Yellow
  '#DDA0DD', // Plum
  '#98D8C8', // Mint
  '#F7DC6F', // Gold
  '#BB8FCE', // Purple
  '#85C1E9', // Light blue
];

// Generate confetti particles data (outside render)
function generateConfettiData(count: number) {
  return Array.from({ length: count }).map(() => ({
    color: confettiColors[Math.floor(Math.random() * confettiColors.length)],
    left: Math.random() * 100,
    isCircle: Math.random() > 0.5,
    duration: 2 + Math.random() * 2,
    delay: Math.random() * 0.5,
  }));
}

// Simple CSS confetti effect
function ConfettiEffect() {
  // Pre-compute random values on mount
  const particles = useMemo(() => generateConfettiData(50), []);

  return (
    <div
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '100%',
        overflow: 'hidden',
        pointerEvents: 'none',
      }}
    >
      {particles.map((particle, i) => (
        <div
          key={i}
          style={{
            position: 'absolute',
            width: '10px',
            height: '10px',
            backgroundColor: particle.color,
            left: `${particle.left}%`,
            top: '-10px',
            borderRadius: particle.isCircle ? '50%' : '0',
            animation: `confetti-fall ${particle.duration}s ease-out forwards`,
            animationDelay: `${particle.delay}s`,
          }}
        />
      ))}
      <style>{`
        @keyframes confetti-fall {
          0% {
            transform: translateY(0) rotate(0deg);
            opacity: 1;
          }
          100% {
            transform: translateY(400px) rotate(720deg);
            opacity: 0;
          }
        }
      `}</style>
    </div>
  );
}

// Hook for managing milestone celebrations
// eslint-disable-next-line react-refresh/only-export-components
export function useMilestoneCelebration() {
  const [currentMilestone, setCurrentMilestone] = useState<Milestone | null>(null);
  const [queue, setQueue] = useState<Milestone[]>([]);

  const showMilestone = (milestone: Milestone) => {
    if (currentMilestone) {
      // Queue it if we're already showing one
      setQueue((prev) => [...prev, milestone]);
    } else {
      setCurrentMilestone(milestone);
    }
  };

  const dismissMilestone = () => {
    setCurrentMilestone(null);
    // Show next in queue if any
    if (queue.length > 0) {
      const [next, ...rest] = queue;
      setQueue(rest);
      setTimeout(() => setCurrentMilestone(next), 300);
    }
  };

  return {
    currentMilestone,
    showMilestone,
    dismissMilestone,
  };
}

// Toast-style notification for less intrusive celebrations
interface MilestoneToastProps {
  milestone: Milestone | null;
  onDismiss: () => void;
}

export function MilestoneToast({ milestone, onDismiss }: MilestoneToastProps) {
  useEffect(() => {
    if (milestone) {
      const timer = setTimeout(onDismiss, 5000);
      return () => clearTimeout(timer);
    }
  }, [milestone, onDismiss]);

  if (!milestone) return null;

  const emoji = iconEmojis[milestone.icon] || '🎉';

  return (
    <div
      style={{
        position: 'fixed',
        bottom: '20px',
        right: '20px',
        backgroundColor: '#1a1a1a',
        color: 'white',
        padding: '16px 24px',
        borderRadius: '12px',
        boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
        zIndex: 9999,
        maxWidth: '400px',
        animation: 'slide-in 0.3s ease-out',
      }}
    >
      <InlineStack gap="300" blockAlign="center">
        <Text as="span" variant="headingLg">{emoji}</Text>
        <BlockStack gap="100">
          <Text as="span" variant="headingSm" fontWeight="bold">
            {milestone.title}
          </Text>
          <Text as="span" variant="bodySm">
            {milestone.message}
          </Text>
        </BlockStack>
        <Button variant="plain" tone="critical" onClick={onDismiss}>
          ×
        </Button>
      </InlineStack>
      <style>{`
        @keyframes slide-in {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}
