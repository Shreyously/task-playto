import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import api from '../api/axios';

const Navbar = () => {
  const [merchantName, setMerchantName] = useState('');
  const navigate = useNavigate();
  const merchantId = localStorage.getItem('merchant_id');

  useEffect(() => {
    if (merchantId) {
      api.get('/api/v1/merchants/me')
        .then(res => setMerchantName(res.data.name))
        .catch(() => setMerchantName('Unknown Merchant'));
    }
  }, [merchantId]);

  const handleLogout = () => {
    localStorage.removeItem('merchant_id');
    navigate('/');
  };

  if (!merchantId) return null;

  return (
    <nav className="bg-gray-900 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-8">
            <span className="text-xl font-bold text-indigo-400">Playto Payout</span>
            <div className="flex space-x-4">
              <Link to="/dashboard" className="hover:text-indigo-300 px-3 py-2 rounded-md text-sm font-medium">Dashboard</Link>
              <Link to="/payouts/new" className="hover:text-indigo-300 px-3 py-2 rounded-md text-sm font-medium">New Payout</Link>
              <Link to="/payouts" className="hover:text-indigo-300 px-3 py-2 rounded-md text-sm font-medium">History</Link>
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-300">{merchantName}</span>
            <button 
              onClick={handleLogout}
              className="text-xs bg-gray-800 hover:bg-gray-700 text-gray-300 px-2 py-1 rounded border border-gray-600 transition"
            >
              Switch Merchant
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
