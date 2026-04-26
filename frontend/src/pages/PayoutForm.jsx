import React, { useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import api from '../api/axios';

const PayoutForm = () => {
  const [amountRupees, setAmountRupees] = useState('');
  const [bankAccountId, setBankAccountId] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    const amountPaise = parseFloat(amountRupees) * 100;

    try {
      const res = await api.post('/api/v1/payouts', 
        {
          amount_paise: amountPaise,
          bank_account_id: bankAccountId
        },
        {
          headers: {
            'Idempotency-Key': uuidv4()
          }
        }
      );
      setMessage({ type: 'success', text: `Payout created successfully! ID: ${res.data.payout_id}` });
      setAmountRupees('');
      setBankAccountId('');
    } catch (err) {
      const errorMsg = err.response?.data?.error || err.message;
      setMessage({ type: 'error', text: `Failed to create payout: ${errorMsg}` });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Request New Payout</h2>
        
        {message && (
          <div className={`mb-6 p-4 rounded-xl text-sm font-medium ${
            message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
          }`}>
            {message.text}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Amount (₹)</label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">₹</span>
              <input
                type="number"
                step="0.01"
                required
                value={amountRupees}
                onChange={(e) => setAmountRupees(e.target.value)}
                placeholder="0.00"
                className="w-full pl-10 pr-4 py-3 rounded-xl border border-gray-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Bank Account ID</label>
            <input
              type="text"
              required
              value={bankAccountId}
              onChange={(e) => setBankAccountId(e.target.value)}
              placeholder="e.g. ACC-123456"
              className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 transition-all"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className={`w-full py-4 rounded-xl text-white font-bold text-lg shadow-lg shadow-indigo-200 transition-all ${
              loading ? 'bg-indigo-400 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-700 active:scale-[0.98]'
            }`}
          >
            {loading ? 'Processing...' : 'Submit Payout Request'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default PayoutForm;
