import { Routes, Route, Navigate } from 'react-router-dom'
import { useShopifyBridge } from './hooks/useShopifyBridge'
import { EmbeddedApp } from './embedded'
import Onboarding from './admin/pages/Onboarding'

function App() {
  const { shop, isLoading } = useShopifyBridge()

  // Show loading while detecting shop
  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <p>Loading...</p>
      </div>
    )
  }

  return (
    <Routes>
      {/* Primary: Embedded App Routes (Shopify Admin) */}
      <Route path="/app/*" element={<EmbeddedApp shop={shop} />} />

      {/* Redirect /admin to /app for consolidation */}
      <Route path="/admin" element={<Navigate to="/app/dashboard" replace />} />
      <Route path="/admin/members" element={<Navigate to="/app/members" replace />} />
      <Route path="/admin/members/new" element={<Navigate to="/app/members" replace />} />
      <Route path="/admin/tradeins" element={<Navigate to="/app/trade-ins" replace />} />
      <Route path="/admin/tradeins/new" element={<Navigate to="/app/trade-ins/new" replace />} />
      <Route path="/admin/tradeins/categories" element={<Navigate to="/app/trade-ins/categories" replace />} />
      <Route path="/admin/promotions" element={<Navigate to="/app/promotions" replace />} />
      <Route path="/admin/bulk-credit" element={<Navigate to="/app/bulk-credit" replace />} />
      <Route path="/admin/settings" element={<Navigate to="/app/settings" replace />} />
      <Route path="/admin/*" element={<Navigate to="/app/dashboard" replace />} />

      {/* Onboarding (standalone for OAuth flow) */}
      <Route path="/onboarding" element={<Onboarding />} />

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/app/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/app/dashboard" replace />} />
    </Routes>
  )
}

export default App
