import axios from 'axios';

const instance = axios.create({
  baseURL: 'http://localhost:8000',
});

instance.interceptors.request.use((config) => {
  const merchantId = localStorage.getItem('merchant_id');
  if (merchantId) {
    config.headers['X-Merchant-ID'] = merchantId;
  }
  return config;
}, (error) => {
  return Promise.reject(error);
});

export default instance;
