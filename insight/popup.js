// InSight Popup Script — 一键把当前网页链接发布为内容文章（复用 url-to-article 技能）

const elements = {
  pageURL: () => document.getElementById('pageURL'),
  pageTitle: () => document.getElementById('pageTitle'),
  sectionSelect: () => document.getElementById('sectionSelect'),
  categorySelect: () => document.getElementById('categorySelect'),
  saveBtn: () => document.getElementById('saveBtn'),
  saveStatus: () => document.getElementById('saveStatus'),
  articleList: () => document.getElementById('articleList'),
  settingsBtn: () => document.getElementById('settingsBtn'),
  settingsPanel: () => document.getElementById('settingsPanel'),
  serverURL: () => document.getElementById('serverURL'),
  serverEmail: () => document.getElementById('serverEmail'),
  serverPassword: () => document.getElementById('serverPassword'),
  rememberPwd: () => document.getElementById('rememberPwd'),
  loginBtn: () => document.getElementById('loginBtn'),
  registerBtn: () => document.getElementById('registerBtn'),
  logoutBtn: () => document.getElementById('logoutBtn'),
  loggedOutView: () => document.getElementById('loggedOutView'),
  loggedInView: () => document.getElementById('loggedInView'),
  userIdentity: () => document.getElementById('userIdentity'),
  settingsStatus: () => document.getElementById('settingsStatus'),
};

let currentUrl = '';
let currentTitle = '';
let isLoggedIn = false;
let sections = [];
let selectedSectionId = null;
let categories = [];

// ─── Init ───

async function init() {
  await loadSettings();
  await loadPageInfo();
  if (isLoggedIn) {
    await loadSections();
    await loadRecent();
  }
  bindEvents();
}

async function sendMessage(type, data = {}) {
  try {
    return await chrome.runtime.sendMessage({ type, ...data });
  } catch (e) {
    return { error: e.message };
  }
}

async function loadSettings() {
  const s = await sendMessage('GET_SETTINGS');
  el('serverURL').value = s.insight_baseURL || '';
  isLoggedIn = Boolean(s.insight_token);
  if (isLoggedIn) {
    el('loggedOutView').style.display = 'none';
    el('loggedInView').style.display = 'block';
    el('userIdentity').textContent = `${s.insight_user?.name || '用户'} · ${s.insight_user?.email || ''}`;
  } else {
    el('loggedOutView').style.display = 'block';
    el('loggedInView').style.display = 'none';
    if (s.insight_credentials) {
      el('serverEmail').value = s.insight_credentials.email || '';
      el('serverPassword').value = s.insight_credentials.password || '';
      el('rememberPwd').checked = true;
    }
  }
}

async function loadPageInfo() {
  const info = await sendMessage('GET_PAGE_INFO');
  currentUrl = info.url || '';
  currentTitle = info.title || '';
  el('pageURL').textContent = currentUrl || '(未检测到页面)';
  el('pageTitle').textContent = currentTitle || '无标题';
}

// ─── Sections & Categories ───

async function loadSections() {
  const result = await sendMessage('GET_SECTIONS');
  sections = result.sections || [];
  const saved = localStorage.getItem('insight_lastSectionId');
  renderSections(saved ? parseInt(saved) : null);
  if (selectedSectionId) {
    await loadCategories(selectedSectionId);
  } else {
    renderCategories([]);
  }
}

function renderSections(preferredId) {
  const select = el('sectionSelect');
  select.innerHTML = '';
  if (!sections.length) {
    select.innerHTML = '<option value="">暂无可发布板块</option>';
    return;
  }
  select.innerHTML = '<option value="">请选择发布板块</option>';
  let found = false;
  sections.forEach(s => {
    select.innerHTML += `<option value="${s.id}">${escapeHtml(s.name)}</option>`;
    if (preferredId && s.id === preferredId) found = true;
  });
  if (preferredId && found) select.value = preferredId;
  selectedSectionId = select.value ? parseInt(select.value) : null;
}

async function loadCategories(sectionId) {
  if (!sectionId) { categories = []; renderCategories([]); return; }
  const result = await sendMessage('GET_SECTION_TREE', { sectionId });
  categories = result.categories || [];
  renderCategories(categories);
}

function renderCategories(cats) {
  const select = el('categorySelect');
  select.innerHTML = '<option value="">不选择分类</option>';
  (cats || []).forEach(c => {
    select.innerHTML += `<option value="${c.id}">${escapeHtml(c.icon || '')} ${escapeHtml(c.name)}</option>`;
    (c.children || []).forEach(ch => {
      select.innerHTML += `<option value="${ch.id}">　　${escapeHtml(ch.icon || '')} ${escapeHtml(ch.name)}</option>`;
    });
  });
}

// ─── Recent published articles ───

async function loadRecent() {
  const result = await sendMessage('GET_RECENT_CONTENT');
  const articles = result.articles || [];
  const list = el('articleList');

  if (articles.length === 0) {
    list.innerHTML = `<div class="empty-state"><div class="empty-icon">📖</div><div class="empty-text">还没有发布文章</div><div style="font-size:10px;color:#ccc;">选择板块后点击「发布」开始</div></div>`;
    return;
  }

  list.innerHTML = articles.map(a => `
    <div class="article-item">
      <div class="article-title">${escapeHtml(a.title || a.url)}</div>
      <div class="article-meta">
        <span>${a.section_name || ''}</span>
        ${a.category_name ? `<span>${escapeHtml(a.category_name)}</span>` : ''}
        <span class="article-status ${a.status === 'ready' ? 'status-ready' : 'status-processing'}">${a.status === 'ready' ? '已发布' : '处理中'}</span>
        <span>${formatTime(a.created_at)}</span>
      </div>
    </div>
  `).join('');
}

// ─── Actions ───

async function saveArticle() {
  const status = el('saveStatus');
  const btn = el('saveBtn');

  if (!currentUrl) {
    status.textContent = '❌ 未检测到当前页面';
    return;
  }
  const sectionId = el('sectionSelect').value ? parseInt(el('sectionSelect').value) : null;
  if (!sectionId) {
    status.textContent = '❌ 请选择发布板块';
    return;
  }
  const subCategoryId = el('categorySelect').value ? parseInt(el('categorySelect').value) : null;

  btn.disabled = true;
  status.textContent = '⏳ 正在提交，交给技能提取并发布...';

  const result = await sendMessage('SHARED_SAVE', {
    url: currentUrl,
    sectionId,
    subCategoryId,
    titleHint: currentTitle
  });

  btn.disabled = false;

  if (result.error) {
    status.textContent = `❌ ${result.error}`;
  } else if (result.status === 'pending') {
    status.textContent = result.message || '✅ 已入队，技能正在后台自动提取并发布';
    localStorage.setItem('insight_lastSectionId', String(sectionId));
    setTimeout(() => { status.textContent = ''; }, 4000);
    await loadRecent();
  } else {
    status.textContent = result.message || '✅ 已发布';
    localStorage.setItem('insight_lastSectionId', String(sectionId));
    setTimeout(() => { status.textContent = ''; }, 3000);
    await loadRecent();
  }
}

async function login() {
  const baseURL = el('serverURL').value.trim();
  const email = el('serverEmail').value.trim();
  const password = el('serverPassword').value;
  const remember = el('rememberPwd').checked;

  if (!baseURL || !email || !password) {
    el('settingsStatus').textContent = '请填写完整信息';
    return;
  }

  el('loginBtn').disabled = true;
  el('settingsStatus').textContent = '登录中...';

  const result = await sendMessage('LOGIN', { baseURL, email, password, remember });

  el('loginBtn').disabled = false;

  if (result.error) {
    el('settingsStatus').textContent = `❌ ${result.error}`;
  } else {
    isLoggedIn = true;
    el('settingsStatus').textContent = '✅ 登录成功';
    await loadSettings();
    await loadSections();
    await loadRecent();
  }
}

async function register() {
  const baseURL = el('serverURL').value.trim();
  const email = el('serverEmail').value.trim();
  const password = el('serverPassword').value;

  if (!baseURL || !email || !password) {
    el('settingsStatus').textContent = '请填写完整信息';
    return;
  }

  el('registerBtn').disabled = true;
  el('settingsStatus').textContent = '注册中...';

  const result = await sendMessage('REGISTER', { baseURL, email, password });

  el('registerBtn').disabled = false;
  el('settingsStatus').textContent = result.error ? `❌ ${result.error}` : `✅ ${result.message}`;
}

async function logout() {
  await sendMessage('LOGOUT');
  isLoggedIn = false;
  sections = [];
  categories = [];
  await loadSettings();
  renderSections(null);
  renderCategories([]);
}

// ─── Helpers ───

function el(id) { return elements[id](); }

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatTime(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = now - d;
    if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}天前`;
    return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  } catch (e) { return iso; }
}

// ─── Event Bindings ───

function bindEvents() {
  el('saveBtn').addEventListener('click', saveArticle);
  el('loginBtn').addEventListener('click', login);
  el('registerBtn').addEventListener('click', register);
  el('logoutBtn').addEventListener('click', logout);

  el('settingsBtn').addEventListener('click', () => {
    el('settingsPanel').classList.toggle('show');
  });

  el('serverPassword').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') login();
  });

  el('sectionSelect').addEventListener('change', (e) => {
    selectedSectionId = e.target.value ? parseInt(e.target.value) : null;
    if (selectedSectionId) localStorage.setItem('insight_lastSectionId', String(selectedSectionId));
    loadCategories(selectedSectionId);
  });
}

document.addEventListener('DOMContentLoaded', init);
