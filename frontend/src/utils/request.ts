import axios from 'axios';

const _base = import.meta.env.VITE_API_BASE_URL;
const request = axios.create({
  baseURL: _base === undefined ? 'http://localhost:8000' : _base,
  timeout: 30000,
});

// token 注入 + 全站防缓存：GET 请求一律不走浏览器缓存
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  // 防缓存：所有 GET 请求带时间戳，浏览器不再复用旧缓存
  // 根因：浏览器缓存 GET 响应，保存后刷新仍显示旧值
  if (config.method === 'get') {
    config.params = { ...(config.params || {}), _t: Date.now() };
  }
  // 请求头也声明不缓存（双保险）
  config.headers['Cache-Control'] = 'no-cache';
  config.headers['Pragma'] = 'no-cache';
  return config;
});

// 统一响应：{code, msg, data}；code !== 0 抛错；401 尝试刷新 token，刷新失败跳登录
let isRefreshing = false;
let refreshQueue: Array<(token: string) => void> = [];

async function tryRefresh(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refresh_token');
  if (!refreshToken) return null;
  try {
    const resp = await axios.post(
      (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000') + '/api/auth/refresh',
      { refresh_token: refreshToken },
      { timeout: 10000 },
    );
    const { code, data } = resp.data ?? {};
    if (code === 0 && data?.accessToken) {
      localStorage.setItem('access_token', data.accessToken);
      if (data.refreshToken) localStorage.setItem('refresh_token', data.refreshToken);
      return data.accessToken as string;
    }
  } catch { /* 刷新失败，走登出流程 */ }
  return null;
}

function logoutAndRedirect() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
}

request.interceptors.response.use(
  (resp) => {
    const { code, msg, data } = resp.data ?? {};
    if (code !== 0) {
      const err: any = new Error(msg || '请求失败');
      err.code = code;
      throw err;
    }
    // data 为 null 时返回 {msg}，避免前端 r.msg 抛 TypeError
    // （之前 bug：拦截器只返回 data，data=null 时 r.msg 崩，成功报成失败）
    if (data === null || data === undefined) {
      return { msg, data: null } as any;
    }
    // data 存在时，附加 msg 属性（前端可读 r.msg）
    // 优先内层 data.msg（真实诊断），外层 msg 只是信封默认值 "ok"
    if (typeof data === 'object' && !Array.isArray(data)) {
      return { ...data, msg: (data as any).msg || msg };
    }
    return data;
  },
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original?._retry) {
      // 401：先尝试用 refresh_token 换新 access_token
      if (isRefreshing) {
        // 正在刷新中，排队等新 token
        return new Promise((resolve, reject) => {
          refreshQueue.push((token: string) => {
            if (token) {
              original.headers.Authorization = `Bearer ${token}`;
              original._retry = true;
              resolve(request(original));
            } else {
              reject(error);
            }
          });
        });
      }
      isRefreshing = true;
      const newToken = await tryRefresh();
      isRefreshing = false;
      // 唤醒排队请求
      refreshQueue.forEach((cb) => cb(newToken || ''));
      refreshQueue = [];
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        original._retry = true;
        return request(original);
      }
      // 刷新失败：清除 token，跳登录
      logoutAndRedirect();
      const err: any = new Error('登录已过期，请重新登录');
      err.code = 401;
      throw err;
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
