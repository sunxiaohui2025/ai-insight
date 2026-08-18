import axios from 'axios';
import {
  User,
  Article,
  Category,
  Section,
  AgentSession,
  AgentMessage,
  Skill,
  LLMModel,
  LLMModelInput,
  ProviderPreset,
  ModelTestResult,
  ApiResponse,
  AgentFile,
} from '../types';

// 生产环境下后端与前端同源（由后端托管 React build），base 为空 → 走相对路径；
// 本地开发用 .env 里的 REACT_APP_API_BASE_URL 指到后端端口。
export const API_BASE_URL = (process.env.REACT_APP_API_BASE_URL || '').replace(/\/$/, '');

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 请求拦截器：添加 token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：处理错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

/** 把后端返回的 /media/... 相对地址转成可直接访问的绝对地址 */
export const mediaUrl = (path?: string): string => {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL.replace(/\/$/, '')}${path}`;
};

// 后台概览统计数据
export const adminDashboardApi = {
  getStats: () =>
    api.get<{
      total_articles: number;
      total_categories: number;
      total_reads: number;
      new_this_month: number;
    }>('/api/v1/admin/dashboard/stats'),
};

// 认证相关
export const authApi = {
  login: (email: string, password: string) =>
    api.post<{ token: string; user: User }>('/api/v1/auth/login', { email, password }),

  register: (email: string, password: string, name: string) =>
    api.post<ApiResponse<{ message: string }>>('/api/v1/auth/register', { email, password, name }),

  getCurrentUser: () =>
    api.get<User>('/api/v1/me'),
};

// 公开文章 API
// 注意：后端这些接口直接返回数据本体，没有 { data: ... } 包装
export const blogApi = {
  getArticles: (params?: {
    section_id?: number;
    category_id?: number;
    search?: string;
    page?: number;
    limit?: number;
  }) =>
    api.get<{ articles: Article[]; total: number; page: number; page_size: number }>(
      '/api/v1/blog/articles',
      { params }
    ),

  getArticleById: (id: number) =>
    api.get<Article>(`/api/v1/blog/articles/${id}`),

  getCategories: (section_id?: number) =>
    api.get<Category[]>('/api/v1/blog/categories', { params: { section_id } }),

  getSections: () =>
    api.get<Section[]>('/api/v1/blog/sections'),

  getFeatured: (limit?: number) =>
    api.get<Article[]>('/api/v1/blog/featured', { params: { limit } }),

  getLatest: (limit?: number) =>
    api.get<Article[]>('/api/v1/blog/latest', { params: { limit } }),
};

// 后台管理 - 文章管理
export const adminArticleApi = {
  getArticles: (params?: {
    section_id?: number;
    category_id?: number;
    status?: string;
    search?: string;
    page?: number;
    limit?: number;
  }) =>
    api.get<ApiResponse<{ articles: Article[]; total: number }>>('/api/v1/admin/articles', { params }),
  
  createArticle: (data: Partial<Article>) =>
    api.post<ApiResponse<Article>>('/api/v1/admin/articles', data),
  
  updateArticle: (id: number, data: Partial<Article>) =>
    api.put<ApiResponse<Article>>(`/api/v1/admin/articles/${id}`, data),
  
  deleteArticle: (id: number) =>
    api.delete<ApiResponse<void>>(`/api/v1/admin/articles/${id}`),
  
  publishArticle: (id: number) =>
    api.patch<ApiResponse<Article>>(`/api/v1/admin/articles/${id}/publish`),
  
  unpublishArticle: (id: number) =>
    api.patch<ApiResponse<Article>>(`/api/v1/admin/articles/${id}/unpublish`),
};

// 后台管理 - 内容发布（媒体 / 排版 / Banner / 文章）
export interface AdminArticlePayload {
  title: string;
  subtitle?: string;
  section_id: number;
  sub_category_id?: number | null;
  content_html?: string;
  content_format?: string;
  excerpt?: string;
  /** 一页纸解读（HTML），发布到前端后可在正文/一页纸间切换查看 */
  summary_html?: string;
  /** manual | link | document（补充语义；网页链接技能提取的正文是整页 HTML，但语义仍为 link） */
  content_type?: string;
  banner_url?: string;
  attachment_url?: string;
  attachment_name?: string;
  doc_kind?: string;
  source_url?: string; // 网页链接格式时存储原始 URL
  status?: 'draft' | 'ready';
}

export interface UploadedDocument {
  url: string;
  filename: string;
  size: number;
  /** pdf 保留原文件在线阅读，其余格式在服务端已转成 html */
  doc_kind: 'pdf' | 'docx' | 'markdown' | 'text';
  html: string;
  /** PDF 前若干页解析出的纯文本，仅用于生成标题/摘要 */
  preview_text: string;
  preview_pages: number;
  preview_note: string;
}

/** url-to-article Skill 提取结果的正文 / 一页纸 / 候选 banner */
export interface SkillExtractBanner {
  url: string;
  name: string;
  kind: 'article' | 'summary';
}

export interface SkillExtractResult {
  content_html: string;
  summary_html: string;
  url: string;
  title: string;
  detected_language: string;
  translated: boolean;
  image_count: number;
  banners: SkillExtractBanner[];
}

/** url-to-article Skill 执行进度日志的一行 */
export interface SkillExtractLog {
  ts: string;
  level: 'info' | 'success' | 'error';
  msg: string;
}

export const publishApi = {
  uploadImage: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<{ url: string; filename: string; size: number }>(
      '/api/v1/admin/media/image',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    );
  },

  uploadDocument: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<UploadedDocument>('/api/v1/admin/media/document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  generateBanner: (data: { title: string; subtitle?: string; accent?: string; extra_prompt?: string }) =>
    api.post<{
      url: string;
      accent: string;
      accent_name: string;
      source: 'llm' | 'fallback';
      model: string;
      concept: string;
    }>('/api/v1/admin/banner/generate', data),

  /** 用模型管理里配置的大模型，从正文提取标题 / 副标题 / 摘要 */
  extractMetadata: (data: {
    content: string;
    content_format?: string;
    doc_name?: string;
    is_plain_text?: boolean;
    /** 传 PDF 的 /media 地址，让服务端重新解析前若干页 */
    doc_url?: string;
  }) =>
    api.post<{
      title: string;
      subtitle: string;
      excerpt: string;
      source: 'llm' | 'local';
      model: string;
      warnings: string[];
      title_min: number;
      subtitle_min: number;
    }>('/api/v1/admin/content/metadata', data),

  optimizeContent: (content: string, content_format = 'richtext') =>
    api.post<{
      html: string;
      optimized_by: 'llm' | 'local';
      model: string;
      word_count: number;
      excerpt: string;
    }>('/api/v1/admin/content/optimize', { content, content_format }),

  /** 用模型管理里配置的大模型，从正文生成一页纸解读（HTML） */
  generateSummary: (data: {
    content: string;
    content_format?: string;
    title?: string;
    is_plain_text?: boolean;
    doc_url?: string;
  }) =>
    api.post<{
      html: string;
      source: 'llm' | 'fallback';
      model: string;
    }>('/api/v1/admin/content/summary', data),

  /** 从网页链接提取文章内容，自动翻译（如果是英文） */
  extractUrl: (url: string) =>
    api.post<{
      content_html: string;
      source_url: string;
      detected_language: string;
      translated: boolean;
      translation_model: string;
      word_count: number;
      char_count: number;
    }>('/api/v1/admin/content/extract-url', { url }),

  /** 用 url-to-article Agent Skill 异步提取网页（正文 + 一页纸 + banner），返回任务 id */
  skillExtract: (url: string) =>
    api.post<{ job_id: string; status: string }>('/api/v1/admin/content/skill-extract', { url }),

  /** 轮询 URL 提取任务状态；done 时返回正文 / 一页纸 / 候选 banner */
  skillExtractStatus: <T = SkillExtractResult>(jobId: string) =>
    api.get<{
      id: string;
      url: string;
      status: 'running' | 'done' | 'error';
      error: string;
      result: T | null;
      started_at: string;
      logs: SkillExtractLog[];
    }>(`/api/v1/admin/content/skill-extract/${jobId}`),

  createArticle: (data: AdminArticlePayload) =>
    api.post<{ id: number; status: string; message: string }>('/api/v1/admin/content/articles', data),

  getArticle: (id: number) =>
    api.get<any>(`/api/v1/admin/content/articles/${id}`),

  updateArticle: (id: number, data: AdminArticlePayload) =>
    api.put<{ id: number; status: string; message: string }>(
      `/api/v1/admin/content/articles/${id}`,
      data
    ),
};

// 后台管理 - 分类管理
export interface AdminCategory extends Category {
  child_count: number;
  article_count: number;
}

export const adminCategoryApi = {
  /** 后端按板块提供分类树（含一级与二级），直接返回数组而非 { data } 包装 */
  getCategories: (section_id: number) =>
    api.get<AdminCategory[]>(`/api/v1/admin/sections/${section_id}/categories`),

  createCategory: (data: Partial<Category>) =>
    api.post<ApiResponse<Category>>('/api/v1/admin/categories', data),
  
  updateCategory: (id: number, data: Partial<Category>) =>
    api.put<ApiResponse<Category>>(`/api/v1/admin/categories/${id}`, data),
  
  deleteCategory: (id: number) =>
    api.delete<ApiResponse<void>>(`/api/v1/admin/categories/${id}`),
  
  reorderCategories: (orders: { id: number; sort_order: number }[]) =>
    api.put<ApiResponse<void>>('/api/v1/admin/categories/reorder', { orders }),
};

// 后台管理 - 板块管理
export const adminSectionApi = {
  /** 后端直接返回数组，没有 { data } 包装 */
  getSections: () =>
    api.get<(Section & { cat_count: number })[]>('/api/v1/admin/sections'),

  createSection: (data: Partial<Section>) =>
    api.post<ApiResponse<Section>>('/api/v1/admin/sections', data),
  
  updateSection: (id: number, data: Partial<Section>) =>
    api.put<ApiResponse<Section>>(`/api/v1/admin/sections/${id}`, data),
  
  deleteSection: (id: number) =>
    api.delete<ApiResponse<void>>(`/api/v1/admin/sections/${id}`),
};

// 后台管理 - 用户管理
export const adminUserApi = {
  /** 后端 /api/v1/admin/users 直接返回用户数组（非 { data } 包装） */
  getUsers: () =>
    api.get<User[]>('/api/v1/admin/users'),

  updateUserStatus: (id: number, status: string) =>
    api.patch<{ ok: boolean }>(`/api/v1/admin/users/${id}`, { status }),
};

// Agent API
export const agentApi = {
  // 会话管理
  createSession: (mode: 'link' | 'manual', skillIds?: number[]) =>
    api.post<ApiResponse<AgentSession>>('/api/v1/agent/sessions', { mode, skill_ids: skillIds }),
  
  getSessions: () =>
    api.get<ApiResponse<AgentSession[]>>('/api/v1/agent/sessions'),
  
  getSession: (id: string) =>
    api.get<ApiResponse<AgentSession>>(`/api/v1/agent/sessions/${id}`),
  
  deleteSession: (id: string) =>
    api.delete<ApiResponse<void>>(`/api/v1/agent/sessions/${id}`),
  
  // 对话
  sendMessage: (sessionId: string, content: string) =>
    api.post<ApiResponse<{ message: AgentMessage; draft: any }>>(`/api/v1/agent/sessions/${sessionId}/chat`, { content }),
  
  getMessages: (sessionId: string) =>
    api.get<ApiResponse<AgentMessage[]>>(`/api/v1/agent/sessions/${sessionId}/messages`),
  
  // 文件上传
  uploadFile: (sessionId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<ApiResponse<AgentFile>>(`/api/v1/agent/sessions/${sessionId}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  
  // 文章生成
  getArticle: (sessionId: string) =>
    api.get<ApiResponse<any>>(`/api/v1/agent/sessions/${sessionId}/article`),
  
  regenerate: (sessionId: string) =>
    api.post<ApiResponse<any>>(`/api/v1/agent/sessions/${sessionId}/regenerate`),
  
  publish: (sessionId: string, data: any) =>
    api.post<ApiResponse<Article>>(`/api/v1/agent/sessions/${sessionId}/publish`, data),
};

/** 磁盘上的站点执行技能（url-to-article 等），后端从 server/skills 目录读取 */
export interface SiteSkill {
  name: string;
  display_name: string;
  version: string;
  description: string;
  entry: string;
  has_skill_md: boolean;
  instruction_chars: number;
  updated_at: string;
  path: string;
}

// Skills 管理
export const skillApi = {
  // 对话提示词技能（agent_skills 表）
  getSkills: () =>
    api.get<Skill[]>('/api/v1/admin/skills'),

  uploadSkill: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<Skill>('/api/v1/admin/skills', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  deleteSkill: (id: number) =>
    api.delete<{ ok: boolean }>(`/api/v1/admin/skills/${id}`),

  toggleSkill: (id: number, enabled: boolean) =>
    api.patch<{ ok: boolean }>(`/api/v1/admin/skills/${id}`, { enabled }),

  // 站点执行技能（磁盘上 server/skills 目录）
  getSiteSkills: () =>
    api.get<SiteSkill[]>('/api/v1/admin/site-skills'),

  uploadSiteSkill: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<SiteSkill>('/api/v1/admin/site-skills', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  deleteSiteSkill: (name: string) =>
    api.delete<{ ok: boolean }>(`/api/v1/admin/site-skills/${encodeURIComponent(name)}`),
};

// 模型管理（后端直接返回数据本体，无 { data: ... } 包装）
export const modelApi = {
  getPresets: () =>
    api.get<ProviderPreset[]>('/api/v1/admin/models/presets'),

  getModels: () =>
    api.get<LLMModel[]>('/api/v1/admin/models'),

  createModel: (data: LLMModelInput) =>
    api.post<LLMModel>('/api/v1/admin/models', data),

  updateModel: (id: number, data: LLMModelInput) =>
    api.put<LLMModel>(`/api/v1/admin/models/${id}`, data),

  deleteModel: (id: number) =>
    api.delete<{ message: string }>(`/api/v1/admin/models/${id}`),

  setDefault: (id: number) =>
    api.patch<LLMModel>(`/api/v1/admin/models/${id}/default`),

  toggleModel: (id: number) =>
    api.patch<LLMModel>(`/api/v1/admin/models/${id}/toggle`),

  // 测试已保存的模型
  testModel: (id: number) =>
    api.post<ModelTestResult>(`/api/v1/admin/models/${id}/test`),

  // 测试表单里未保存的草稿配置
  testDraft: (data: LLMModelInput & { id?: number }) =>
    api.post<ModelTestResult>('/api/v1/admin/models/test', data),
};

// 数据备份 / 导入（迁移）
export interface DbImportResult {
  ok: boolean;
  imported: Record<string, number>;
  excluded: string[];
  errors: string[];
}

export const dataBackupApi = {
  /** 导出脱敏备份（不含大模型连接配置/API Key），返回 .db 文件 Blob */
  exportDb: async (): Promise<Blob> => {
    const res = await api.get<Blob>('/api/v1/admin/db/export', { responseType: 'blob' });
    return res.data;
  },

  /** 导入 .db 备份并合并进当前库（自动排除大模型连接配置） */
  importDb: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post<DbImportResult>('/api/v1/admin/db/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

export default api;
