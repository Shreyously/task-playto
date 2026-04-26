import React, { useState, useEffect } from 'react';
import api from '../api/axios';

const PayoutHistory = () => {
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPayout, setSelectedPayout] = useState(null);

  const fetchPayouts = async () => {
    try {
      const res = await api.get('/api/v1/payouts');
      setPayouts(res.data);
    } catch (err) {
      console.error('Failed to fetch payouts', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPayouts();
    const interval = setInterval(fetchPayouts, 5000);
    return () => clearInterval(interval); // Cleanup on unmount
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'PENDING': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'PROCESSING': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'COMPLETED': return 'bg-green-100 text-green-800 border-green-200';
      case 'FAILED': return 'bg-red-100 text-red-800 border-red-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  if (loading && payouts.length === 0) return (
    <div className="flex justify-center items-center h-64">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">Payout History</h2>
      
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
                <th className="px-6 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {payouts.map((payout) => (
                <React.Fragment key={payout.id}>
                  <tr className="hover:bg-gray-50 transition cursor-pointer" onClick={() => setSelectedPayout(selectedPayout === payout.id ? null : payout.id)}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-gray-500">
                      {payout.id.substring(0, 8)}...
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {new Date(payout.created_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-right font-medium text-gray-900">
                      ₹{(payout.amount_paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-center">
                      <span className={`px-3 py-1 inline-flex text-xs leading-5 font-bold rounded-full border ${getStatusColor(payout.status)}`}>
                        {payout.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button className="text-indigo-600 hover:text-indigo-900">
                        {selectedPayout === payout.id ? 'Hide Logs' : 'View Logs'}
                      </button>
                    </td>
                  </tr>
                  {selectedPayout === payout.id && (
                    <tr className="bg-gray-50">
                      <td colSpan="5" className="px-12 py-6">
                        <div className="bg-white rounded-xl border border-gray-200 p-6">
                          <h4 className="text-sm font-bold text-gray-900 mb-4 flex items-center">
                            <span className="w-2 h-2 bg-indigo-500 rounded-full mr-2"></span>
                            Audit Trail
                          </h4>
                          <div className="space-y-4">
                            {payout.audit_logs.map((log, index) => (
                              <div key={log.id} className="relative pl-6 pb-4 border-l-2 border-gray-100 last:border-0 last:pb-0">
                                <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-gray-200 border-2 border-white"></div>
                                <div className="flex justify-between items-start mb-1">
                                  <div className="text-sm font-medium text-gray-900">
                                    {log.from_status || 'INIT'} → <span className="text-indigo-600">{log.to_status}</span>
                                  </div>
                                  <div className="text-xs text-gray-400">
                                    {new Date(log.created_at).toLocaleString()}
                                  </div>
                                </div>
                                <div className="text-sm text-gray-600 italic">"{log.reason}"</div>
                              </div>
                            ))}
                            {payout.audit_logs.length === 0 && <p className="text-sm text-gray-500">No logs found.</p>}
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
              {payouts.length === 0 && (
                <tr>
                  <td colSpan="5" className="px-6 py-8 text-center text-gray-500 italic">No payout history found</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default PayoutHistory;
