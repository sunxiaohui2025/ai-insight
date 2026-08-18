// InSight Background Service Worker

function cleanBaseURL(value) {
  return (value || '').trim().replace(/\/+$/, '');
}

async function getSettings() {
  const result = await chrome.storage.local.get(['insight_baseURL', 'insight_token', 'insight_user', 'insight_credentials']);
  return result;
}

async function cloudRequest(path, options = {}, requireAuth = false) {
  const settings = await getSettings();
  const baseURL = cleanBaseURL(settings.insight_baseURL);
  if (!/^https?:\/\//.test(baseURL)) throw new Error('请先设置服务器地址');

  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (requireAuth) {
    if (!settings.insight_token) throw new Error('请先登录');
    headers.Authorization = `Bearer ${settings.insight_token}`;
  }

  const response = await fetch(baseURL + path, { ...options, headers });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.detail || `HTTP ${response.status}`);
  return result;
}

// Handle messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  handleMessage(request).then(sendResponse).catch(err => sendResponse({ error: err.message }));
  return true; // keep channel open for async
});

async function handleMessage(request) {
  switch (request.type) {
    case 'GET_PAGE_INFO': {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tabs[0]) {
        return { title: tabs[0].title || '', url: tabs[0].url || '' };
      }
      return { title: '', url: '' };
    }

    case 'GET_SECTIONS': {
      // 内容板块（公开接口，无需登录）
      try {
        const result = await cloudRequest('/api/v1/content/sections', { method: 'GET' });
        return { sections: result };
      } catch (e) {
        return { error: e.message, sections: [] };
      }
    }

    case 'GET_SECTION_TREE': {
      // 指定板块下的分类树（公开接口）
      try {
        const result = await cloudRequest(`/api/v1/content/sections/${request.sectionId}/categories-tree`, { method: 'GET' });
        return { section: result.section, categories: result.categories };
      } catch (e) {
        return { error: e.message, categories: [] };
      }
    }

    case 'SHARED_SAVE': {
      // 一键发布：把当前链接交给 url-to-article 技能提取并自动发布为内容文章
      try {
        const result = await cloudRequest('/api/v1/insight/articles/shared-save', {
          method: 'POST',
          body: JSON.stringify({
            url: request.url,
            section_id: request.sectionId,
            sub_category_id: request.subCategoryId ?? null,
            title_hint: request.titleHint || ''
          })
        }, true);
        return { success: true, ...result };
      } catch (e) {
        return { error: e.message };
      }
    }

    case 'GET_RECENT_CONTENT': {
      // 最近发布的内容文章
      try {
        const result = await cloudRequest('/api/v1/content/articles?page=1&page_size=5', { method: 'GET' });
        return { articles: result.articles || [] };
      } catch (e) {
        return { error: e.message, articles: [] };
      }
    }

    case 'GET_SETTINGS': {
      return await getSettings();
    }

    case 'SAVE_SETTINGS': {
      await chrome.storage.local.set({
        insight_baseURL: request.baseURL || '',
        insight_credentials: request.remember ? { email: request.email, password: request.password } : undefined
      });
      return { success: true };
    }

    case 'LOGIN': {
      try {
        await chrome.storage.local.set({ insight_baseURL: request.baseURL });
        const result = await cloudRequest('/api/v1/auth/login', {
          method: 'POST',
          body: JSON.stringify({ email: request.email, password: request.password })
        });
        await chrome.storage.local.set({
          insight_token: result.token,
          insight_user: result.user
        });
        if (request.remember) {
          await chrome.storage.local.set({
            insight_credentials: { email: request.email, password: request.password }
          });
        } else {
          await chrome.storage.local.remove('insight_credentials');
        }
        return { success: true, user: result.user };
      } catch (e) {
        return { error: e.message };
      }
    }

    case 'REGISTER': {
      try {
        await chrome.storage.local.set({ insight_baseURL: request.baseURL });
        const result = await cloudRequest('/api/v1/auth/register', {
          method: 'POST',
          body: JSON.stringify({ name: request.name || request.email.split('@')[0], email: request.email, password: request.password })
        });
        return { success: true, message: result.message };
      } catch (e) {
        return { error: e.message };
      }
    }

    case 'LOGOUT': {
      await chrome.storage.local.remove(['insight_token', 'insight_user', 'insight_credentials']);
      return { success: true };
    }

    default:
      return { error: 'Unknown request type' };
  }
}
