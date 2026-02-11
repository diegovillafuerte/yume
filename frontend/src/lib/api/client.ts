import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    // Check if this is an admin API call (admin routes + simulate routes use admin auth)
    const isAdminCall = config.url?.startsWith('/admin') || config.url?.startsWith('/simulate');
    const tokenKey = isAdminCall ? 'admin_token' : 'auth_token';
    const token = localStorage.getItem(tokenKey);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// Handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        const isAdminRequest = error.config?.url?.startsWith('/admin') || error.config?.url?.startsWith('/simulate');

        if (isAdminRequest) {
          localStorage.removeItem('admin_token');
          window.location.href = '/admin/login';
        } else {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('organization');
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
