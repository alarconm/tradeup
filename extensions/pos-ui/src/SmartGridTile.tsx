import React, { useState, useEffect } from 'react';
import {
  Tile,
  Text,
  useExtensionApi,
} from '@shopify/ui-extensions-react/point-of-sale';

/**
 * TradeUp Smart Grid Tile for POS Home Screen.
 *
 * Best-in-class tile that shows:
 * - Live member count
 * - Total credit issued today
 * - Opens member lookup on tap
 */
export default function SmartGridTile() {
  const { navigation, session } = useExtensionApi<'pos.home.tile.render'>();
  const [memberCount, setMemberCount] = useState<number | null>(null);
  const [todayCredit, setTodayCredit] = useState<number | null>(null);

  const shopDomain = session.shop?.myshopifyDomain || '';
  const API_BASE = 'https://app.cardflowlabs.com/api';

  // Fetch quick stats on load
  useEffect(() => {
    if (!shopDomain) return;

    const fetchStats = async () => {
      try {
        const response = await fetch(`${API_BASE}/dashboard/stats`, {
          headers: {
            'X-Shopify-Shop-Domain': shopDomain,
            'Content-Type': 'application/json',
          },
        });

        if (response.ok) {
          const data = await response.json();
          setMemberCount(data.total_members || 0);
          setTodayCredit(data.credit_issued_today || 0);
        }
      } catch (err) {
        console.error('Failed to fetch stats:', err);
      }
    };

    fetchStats();
  }, [shopDomain]);

  const handlePress = () => {
    navigation.navigate('pos.home.modal.render');
  };

  // Build subtitle with live stats
  let subtitle = 'Loyalty Members';
  if (memberCount !== null) {
    subtitle = `${memberCount.toLocaleString()} members`;
  }

  return (
    <Tile
      title="TradeUp"
      subtitle={subtitle}
      enabled={true}
      onPress={handlePress}
    >
      <Text>
        {todayCredit !== null && todayCredit > 0
          ? `$${todayCredit.toFixed(0)} credit today`
          : 'Tap to look up members'}
      </Text>
    </Tile>
  );
}
