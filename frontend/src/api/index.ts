import request from '@/utils/request';

export const authApi = {
  login: (username: string, password: string) =>
    request.post('/api/auth/login', { username, password }),
  register: (data: { username: string; password: string; invite_code: string }) =>
    request.post('/api/auth/register', data),
  refresh: (refreshToken: string) =>
    request.post('/api/auth/refresh', { refresh_token: refreshToken }),
  logout: () => request.post('/api/auth/logout'),
  current: () => request.get('/api/auth/current'),
};

export const userApi = {
  current: () => request.get("/api/auth/current"),
};

export const noteApi = {
  list: (params: any) => request.get('/api/note/list', { params }),
  get: (id: number) => request.get(`/api/note/${id}`),
  create: (data: any) => request.post('/api/note/create', data),
  publish: (id: number) => request.post(`/api/note/${id}/publish`),
  unpublish: (id: number) => request.post(`/api/note/${id}/unpublish`),
  approve: (id: number) => request.post(`/api/note/${id}/approve`),
  reject: (id: number) => request.post(`/api/note/${id}/reject`),
  batch: (ids: number[], op: string, params: any = {}) =>
    request.post('/api/note/batch', { ids, op, params }),
  remove: (id: number) => request.post('/api/note/batch', { ids: [id], op: 'delete' }),
  update: (id: number, data: any) => request.put(`/api/note/${id}`, data),
};

export const channelApi = {
  list: (is_active?: boolean) =>
    request.get('/api/channel/list', { params: { is_active } }),
  botChannels: (bot_id: number, account_id: number) =>
    request.get('/api/channel/bot-channels', { params: { bot_id, account_id } }),
  create: (data: any) => request.post('/api/channel/create', data),
  update: (id: number, data: any) => request.put(`/api/channel/${id}`, data),
  remove: (id: number) => request.delete(`/api/channel/${id}`),
  check: (id: number) => request.post(`/api/channel/${id}/check`),
  pushAll: (id: number) => request.post(`/api/channel/${id}/push_all`),
  clearQueue: (id: number) => request.post(`/api/channel/${id}/clear_queue`),
};

export const messageApi = {
  templates: (keyword = '') =>
    request.get('/api/message/templates', { params: { keyword } }),
  createTemplate: (data: any) => request.post('/api/message/templates', data),
  deleteTemplate: (id: number) => request.delete(`/api/message/templates/${id}`),
  pushTemplate: (id: number) => request.post(`/api/message/templates/${id}/push`),
  plans: () => request.get('/api/message/plans'),
  createPlan: (data: any) => request.post('/api/message/plans', data),
  deletePlan: (id: number) => request.delete(`/api/message/plans/${id}`),
  quickTargets: () => request.get('/api/message/quick_targets'),
  createQuickTarget: (data: any) => request.post('/api/message/quick_targets', data),
  deleteQuickTarget: (id: number) => request.delete(`/api/message/quick_targets/${id}`),
  quickPush: (tpl_id: number, account_id: number) =>
    request.post(`/api/message/templates/${tpl_id}/quick-push`, { account_id }),
  dialogs: (account_id: number, kind: string = 'group') =>
    request.get('/api/message/dialogs', { params: { account_id, kind } }),
  refreshDialogs: (account_id: number) =>
    request.post('/api/message/dialogs/refresh', { account_id }),
};


export const tgApi = {
  accounts: () => request.get('/api/tg/accounts'),
  removeAccount: (id: number) => request.delete(`/api/tg/accounts/${id}`),
  refreshAccount: (id: number) => request.post(`/api/tg/accounts/${id}/refresh`),
  transferAccount: (id: number, target_user_id: number | null) =>
    request.post(`/api/tg/accounts/${id}/transfer`, { target_user_id }),
  loginStart: (phone: string) =>
    request.post('/api/youban-bot/bot/login/start', { phone }),
  loginStatus: (session_key: string) =>
    request.get('/api/youban-bot/bot/login/status', { params: { session_key } }),
  loginVerify: (session_key: string, code: string, password = '') =>
    request.post('/api/youban-bot/bot/login/verify', { session_key, code, password }),
  qrLogin: () => request.post('/api/tg/accounts/qr-login'),
  qrStatus: (qr_token: string, password = '') =>
    request.post('/api/tg/accounts/qr-status', { qr_token, password }),
  importSession: (phone: string, file: File) => {
    const fd = new FormData();
    fd.append('phone', phone);
    fd.append('file', file);
    return request.post('/api/tg/accounts/import-session', fd);
  },
};

export const botApi = {
  tokens: () => request.get('/api/bot/tokens'),
  create: (data: any) => request.post('/api/bot/tokens', data),
  verify: (id: number) => request.post(`/api/bot/tokens/${id}/verify`),
  remove: (id: number) => request.delete(`/api/bot/tokens/${id}`),
  autoCreate: (data: any) => request.post('/api/bot/tokens/auto-create', data),
  setEnabled: (id: number, enabled: boolean) => request.patch(`/api/bot/tokens/${id}`, { enabled }),
  getToken: (id: number) => request.get(`/api/bot/tokens/${id}/token`),
  toggleSubmission: (id: number, enabled: boolean) => request.post(`/api/bot/tokens/${id}/submission`, { enabled }),
  setSubmissionChannels: (id: number, channel_ids: number[]) => request.post(`/api/bot/tokens/${id}/submission-channels`, { channel_ids }),
};





export const mediaApi = {
  uploadMaterial: (file: File, name: string) => {
    const fd = new FormData();
    fd.append('file', file);
    return request.post('/api/media/upload', fd);
  },
  mattingGlobal: () => request.get('/api/media/matting-global'),
  setMattingGlobal: (data: any) => request.post('/api/media/matting-global', data),
};

export const metaApi = {
  tags: () => Promise.resolve({ list: [], total: 0 }), // meta.py 已删除，标签暂不可用
  cityTree: () => Promise.resolve({ list: [] }), // 城市接口已删，返回空
};





export const sysconfigApi = {
  getPublish: () => request.get('/api/sysconfig/publish'),
  setPublish: (data: any) => request.post('/api/sysconfig/publish', data),
  setLoopInterval: (seconds: number) => request.post('/api/sysconfig/loop-interval', { interval_seconds: seconds }),
};
