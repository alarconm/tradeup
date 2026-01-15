import React from 'react';
import {
  Tile,
  Text,
  useExtensionApi,
  Navigator,
} from '@shopify/ui-extensions-react/point-of-sale';

/**
 * TradeUp Smart Grid Tile for POS Home Screen.
 *
 * Displays on the POS home screen grid and opens the member
 * lookup modal when tapped.
 */
export default function SmartGridTile() {
  const { navigation, session } = useExtensionApi<'pos.home.tile.render'>();

  const handlePress = () => {
    // Navigate to the member lookup modal
    navigation.navigate('pos.home.modal.render');
  };

  return (
    <Tile
      title="TradeUp"
      subtitle="Loyalty Members"
      enabled={true}
      onPress={handlePress}
    >
      <Navigator>
        <Text>Tap to look up members</Text>
      </Navigator>
    </Tile>
  );
}
