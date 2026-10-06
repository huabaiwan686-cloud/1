import axios from 'axios';

const _base = import.meta.env.VITE_API_BASE_URL;
const request = axios.create({
  baseURL: _base === undefined ? 'http://localhost:8000' : _base,
  timeout: 30000,
});

// token 注入
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 统一响应：{code, msg, data}；code !== 0 抛错；401 跳登录
request.interceptors.response.use(
  (resp) => {
    const { code, msg, data } = resp.data ?? {};
    if (code !== 0) {
      const err: any = new Error(msg || '请求失败');
      err.code = code;
      throw err;
    }
    return data;
  },
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      location.href = '/login';
    }
    // FastAPI HTTPException 返回 {detail}，转成友好错误消息（如 403 VIP 门控）
    const detail = error.response?.data?.detail;
    if (detail && !error.message?.includes(detail)) {
      error.message = typeof detail === 'string' ? detail : '请求失败';
    }
    throw error;
  },
);

export default request;
