// API 响应类型
export interface ApiResponse<T> {
  data?: T;
  message?: string;
  error?: string;
}

// 用户类型
export interface User {
  id: number;
  email: string;
  name: string;
  role: string;
  status: string;
  created_at: string;
}

// 分类类型
export interface Category {
  id: number;
  section_id: number;
  parent_id?: number;
  name: string;
  slug: string;
  icon: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

// 板块类型（项目沉淀、研究解读）
export interface Section {
  id: number;
  name: string;
  slug: string;
  description: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

// 文章类型
export interface Article {
  id: number;
  user_id: number;
  section_id: number;
  category_id?: number;
  sub_category_id?: number;
  title: string;
  subtitle?: string;
  url?: string;
  content_type: 'url' | 'manual' | 'skill';
  /** richtext / html 的正文在 manual_content；document 表示正文是上传的文档 */
  content_format?: 'richtext' | 'html' | 'document';
  banner_url?: string;
  attachment_url?: string;
  attachment_name?: string;
  doc_kind?: 'pdf' | 'docx' | 'markdown' | 'text' | '';
  original_content: string;
  translated_content: string;
  manual_content: string;
  excerpt: string;
  summary_content: string;
  status: 'pending' | 'translating' | 'ready' | 'failed' | 'draft' | 'published';
  is_read: number;
  is_starred: number;
  word_count: number;
  created_at: string;
  updated_at: string;
  published_at?: string;
  source_domain?: string;
  // 关联字段
  section_name?: string;
  category_name?: string;
  sub_category_name?: string;
  author_name?: string;
}

// Agent 会话类型
export interface AgentSession {
  id: string;
  user_id: number;
  mode: 'link' | 'manual';
  title: string;
  draft_json: string;
  status: 'draft' | 'completed' | 'cancelled';
  created_at: string;
  updated_at: string;
  skills?: Skill[];
}

// Agent 消息类型
export interface AgentMessage {
  id: number;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
}

// Skill 类型
export interface Skill {
  id: number;
  name: string;
  display_name: string;
  version: string;
  description: string;
  skill_type: string;
  manifest_json: string;
  storage_path: string;
  enabled: number;
  created_at: string;
  updated_at: string;
}

// LLM 模型类型
// path_style 决定如何拼接请求地址：
//   openai        -> {base}/chat/completions
//   anthropic     -> {base}/messages
//   model-in-path -> {base}/{model_id}/v1/chat/completions
export type PathStyle = 'openai' | 'anthropic' | 'model-in-path';

export interface LLMModel {
  id: number;
  name: string;
  provider: string;
  model_id: string;
  api_base_url: string;
  path_style: PathStyle;
  max_tokens: number;
  temperature: number;
  is_default: number;
  enabled: number;
  // 后端从不回传明文密钥，只回传是否已配置
  has_api_key: boolean;
  last_tested_at: string;
  last_test_ok: number; // 1 成功 / 0 失败 / -1 未测试
  last_test_message: string;
  created_at: string;
  updated_at: string;
}

// 新建/编辑表单提交的数据（api_key 留空表示不修改）
export interface LLMModelInput {
  name?: string;
  provider?: string;
  model_id?: string;
  api_base_url?: string;
  api_key?: string;
  path_style?: PathStyle;
  max_tokens?: number;
  temperature?: number;
  is_default?: number;
  enabled?: number;
}

// 供应商预设
export interface ProviderPreset {
  provider: string;
  label: string;
  api_base_url: string;
  path_style: PathStyle;
  models: string[];
}

// 连通性测试结果
export interface ModelTestResult {
  ok: boolean;
  latency_ms: number;
  message: string;
  url: string;
  reply?: string;
}

// Agent 文件类型
export interface AgentFile {
  id: number;
  session_id: string;
  filename: string;
  mime_type: string;
  storage_path: string;
  created_at: string;
}

// 文章草稿类型
export interface ArticleDraft {
  title?: string;
  content?: string;
  excerpt?: string;
  summary?: string;
  section_id?: number;
  category_id?: number;
  tags?: string[];
}
