import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Navbar from './components/Navbar';
import MerchantSelector from './pages/MerchantSelector';
import Dashboard from './pages/Dashboard';
import PayoutForm from './pages/PayoutForm';
import PayoutHistory from './pages/PayoutHistory';

// Protected Route wrapper
const ProtectedRoute = ({ children }) => {
  const merchantId = localStorage.getItem('merchant_id');
  if (!merchantId) {
    return <Navigate to="/" replace />;
  }
  return (
    <>
      <Navbar />
      {children}
    </>
  );
};

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        <Routes>
          <Route path="/" element={<MerchantSelector />} />
          <Route 
            path="/dashboard" 
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/payouts/new" 
            element={
              <ProtectedRoute>
                <PayoutForm />
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/payouts" 
            element={
              <ProtectedRoute>
                <PayoutHistory />
              </ProtectedRoute>
            } 
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
