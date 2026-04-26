import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';

const MerchantSelector = () => {
  const [merchants, setMerchants] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    api.get('/api/v1/merchants')
      .then(res => {
        setMerchants(res.data);
        setLoading(false);
      })
      .catch(err => {
        console.error('Failed to fetch merchants', err);
        setLoading(false);
      });
  }, []);

  const handleSelect = (id) => {
    localStorage.setItem('merchant_id', id);
    navigate('/dashboard');
  };

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-6 text-center">Select Merchant</h1>
        <p className="text-gray-600 mb-8 text-center">Choose a merchant to access the dashboard</p>
        
        {loading ? (
          <div className="flex justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>
        ) : (
          <div className="space-y-4">
            {merchants.map(merchant => (
              <button
                key={merchant.id}
                onClick={() => handleSelect(merchant.id)}
                className="w-full text-left px-6 py-4 rounded-xl border border-gray-200 hover:border-indigo-500 hover:bg-indigo-50 transition-all flex items-center justify-between group"
              >
                <span className="text-lg font-medium text-gray-700 group-hover:text-indigo-700">{merchant.name}</span>
                <span className="text-gray-400 group-hover:text-indigo-400">→</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default MerchantSelector;
