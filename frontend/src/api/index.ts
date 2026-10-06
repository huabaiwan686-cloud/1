import request from '@/utils/request';

export const authApi = {
  login: (username: string, password: string) =>
    request.post('/api/auth/login', { username, password }),
  register: (username: string, password: string) =>
    request.post('/api/auth/register', { username, password }),
  refresh: (refreshToken: string) =>
    request.post('/api/auth/refresh', { refresh_token: refreshToken }),
  logout: () => request.post('/api/auth/logout'),
  menu: () => request.get('/api/menu/all'),
  current: () => request.get('/api/account/current'),
};

export const userApi = {
  list: () => request.get('/api/account/list'),
};

export const noteApi = {
  list: (params: any) => request.get('/api/note/list', { params }),
  get: (id: number) => request.get(`/api/note/${id}`),
  create: (data: any) => request.post('/api/note/create', data),
  publish: (id: number) => request.post(`/api/note/${id}/publish`),
  approve: (id: number) => request.post(`/api/note/${id}/approve`),
  reject: (id: number) => request.post(`/api/note/${id}/reject`),
  batch: (ids: number[], op: string, params: any = {}) =>
    request.post('/api/note/batch', { ids, op, params }),
};

export const collectApi = {
  rules: () => request.get('/api/collect/rules'),
  createRule: (data: any) => request.post('/api/collect/rules', data),
  updateRule: (id: number, data: any) => request.put(`/api/collect/rules/${id}`, data),
  deleteRule: (id: number) => request.delete(`/api/collect/rules/${id}`),
  channels: (source_type = '') =>
    request.get('/api/collect/channels', { params: { source_type } }),
  createChannel: (data: any) => request.post('/api/collect/channels', data),
  deleteChannel: (id: number) => request.delete(`/api/collect/channels/${id}`),
};

export const channelApi = {
  list: (is_active?: boolean) =>
    request.get('/api/channel/list', { params: { is_active } }),
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
  dialogs: (account_id: number) =>
    request.get('/api/message/dialogs', { params: { account_id } }),
  refreshDialogs: (account_id: number) =>
    request.post('/api/message/dialogs/refresh', { account_id }),
};

export const listenApi = {
  plans: (keyword = '') =>
    request.get('/api/listen/plans', { params: { keyword } }),
  create: (data: any) => request.post('/api/listen/plans', data),
  remove: (id: number) => request.delete(`/api/listen/plans/${id}`),
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
};

export const botApi = {
  tokens: () => request.get('/api/bot/tokens'),
  create: (data: any) => request.post('/api/bot/tokens', data),
  verify: (id: number) => request.post(`/api/bot/tokens/${id}/verify`),
  remove: (id: number) => request.delete(`/api/bot/tokens/${id}`),
  autoCreate: (data: any) => request.post('/api/bot/tokens/auto-create', data),
  managedStatus: () => request.get('/api/bot/tokens/managed/status'),
  managedSetup: (token: string) => request.post('/api/bot/tokens/managed/setup', { token }),
  managedCreate: (data: any) => request.post('/api/bot/tokens/managed/create', data),
  managedPending: () => request.get('/api/bot/tokens/managed/pending'),
  bindStart: (bot_token_id: number) =>
    request.post('/api/youban-bot/bot/bind/start', { bot_token_id }),
  bindStatus: (session_key: string) =>
    request.get('/api/youban-bot/bot/bind/status', { params: { session_key } }),
};

export const socialApi = {
  twoWayBots: () => request.get('/api/social/two_way_bots'),
  createTwoWay: (data: any) => request.post('/api/social/two_way_bots', data),
  friends: (direction = '') =>
    request.get('/api/social/friends', { params: { direction } }),
  applyFriend: (username: string) =>
    request.post('/api/social/friends/apply', { username }),
  bindings: () => request.get('/api/social/bindings'),
  createBinding: (bind_code: string) =>
    request.post('/api/social/bindings', null, { params: { bind_code } }),
  cooperations: () => request.get('/api/social/cooperations'),
  importCoops: (usernames: string[]) =>
    request.post('/api/social/cooperations/import', usernames),
  reviewCoop: (id: number, approve = true) =>
    request.post(`/api/social/cooperations/${id}/review`, null, { params: { approve } }),
  saveCoopConfig: (data: any) => request.post('/api/social/cooperation_config', data),
};

export const vipApi = {
  plans: () => request.get('/api/vip/plans'),
  subscription: () => request.get('/api/vip/subscription'),
  orders: () => request.get('/api/vip/orders'),
  createOrder: () => request.post('/api/vip/orders'),
  payInfo: () => request.get('/api/vip/pay/info'),
  payWatch: () => request.post('/api/vip/pay/watch'),
  quota: () => request.get('/api/vip/quota'),
};

export const inviteApi = {
  info: () => request.get('/api/invite/info'),
  list: () => request.get('/api/invite/list'),
  generate: () => request.post('/api/invite/generate'),
};

export const mediaApi = {
  materials: () => request.get('/api/media/materials'),
  uploadMaterial: (file: File, name: string) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('name', name);
    return request.post('/api/media/materials', fd);
  },
  deleteMaterial: (id: number) => request.delete(`/api/media/materials/${id}`),
  mattingGlobal: () => request.get('/api/media/matting-global'),
  setMattingGlobal: (data: any) => request.post('/api/media/matting-global', data),
  process: (file: File, mode: string, background_id?: number) => {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('mode', mode);
    if (background_id) fd.append('background_id', String(background_id));
    return request.post('/api/media/process', fd);
  },
  jobs: () => request.get('/api/media/jobs'),
};

export const metaApi = {
  tags: () => request.get('/api/tag/list'),
  createTag: (name: string) =>
    request.post('/api/tag/create', null, { params: { name } }),
  cityTree: () => request.get('/api/city/tree'),
  taskLogs: (params: any) => request.get('/api/task/logs', { params }),
};

export const announceApi = {
  active: () => request.get('/api/announce/active'),
  list: () => request.get('/api/announce/list'),
  create: (data: any) => request.post('/api/announce/create', data),
  update: (id: number, data: any) => request.put(`/api/announce/${id}`, data),
  remove: (id: number) => request.delete(`/api/announce/${id}`),
};

export const collectorApi = {
  myNotes: (params: any) => request.get('/api/collector/notes', { params }),
  myRecords: (params: any) => request.get('/api/collector/records', { params }),
};
