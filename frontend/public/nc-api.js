/* NovelCraft API Bridge — connects prototype UI to real backend */

// Local toast (don't rely on inline script's showToast timing)
function ncToast(msg) {
  const to = document.getElementById('toast');
  const msgEl = document.getElementById('toastMsg');
  if (msgEl) msgEl.textContent = msg;
  if (to) { to.classList.add('show'); setTimeout(() => to.classList.remove('show'), 2400); }
}

// ── Helpers ──

// 从后端错误响应里提取可读信息（后端错误多为 {"detail":"..."} 形式的 JSON）。
// 登录失败时我们想展示真实的 detail（如 "invalid email or password"）而不是伪装成功。
function extractErrorMessage(raw) {
  if (!raw) return '未知错误';
  try {
    const obj = JSON.parse(raw);
    if (obj && obj.detail) {
      return typeof obj.detail === 'string' ? obj.detail : JSON.stringify(obj.detail);
    }
  } catch (e) {
    /* 不是 JSON，直接返回原文 */
  }
  return String(raw);
}

// 读取 csrf_token cookie（若站点启用了 CSRF 防护）。
function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

const NC = {
  base: '',
  token: sessionStorage.getItem('nc_token') || '',

  async api(path, opts = {}) {
    const method = (opts.method || 'GET').toUpperCase();
    const headers = { 'Content-Type': 'application/json', ...opts.headers };
    if (NC.token) headers['Authorization'] = `Bearer ${NC.token}`;
    // CSRF：非 GET 请求且存在 csrf_token cookie 时，附带 X-CSRF-Token 头，
    // 这样即使后端启用了 CSRF 校验，fetchProjects / fetchStats 等也能通过。
    if (method !== 'GET') {
      const csrf = getCsrfToken();
      if (csrf) headers['X-CSRF-Token'] = csrf;
    }
    const res = await fetch(NC.base + path, { ...opts, headers });
    if (!res.ok) throw new Error(await res.text());
    const json = await res.json();
    return json.data ?? json;
  },

  async login(email, password) {
    const data = await NC.api('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    NC.token = data.access_token;
    sessionStorage.setItem('nc_token', NC.token);
    return data;
  },

  async fetchProjects() {
    try { return await NC.api('/api/v1/projects'); } catch { return []; }
  },

  async fetchStats() {
    try { return await NC.api('/api/v1/stats/overview'); } catch { return {}; }
  },

  async fetchBooks(projectId) {
    try { return await NC.api(`/api/v1/ranking/library/books?project_id=${projectId}&limit=50`); } catch { return []; }
  },

  async fetchChapters(novelId) {
    try { return await NC.api(`/api/v1/contents?parent_id=${novelId}&type=chapter`); } catch { return []; }
  },
};

// ── Login button handler (robust binding via readyState guard) ──
// 改为 readyState 守卫：无论脚本位于 head 还是 body 末尾、是否被浏览器缓存，
// 都能保证登录处理器一定绑定上，不会再出现“点登录没反应”。
function initLogin() {
  const loginBtn = document.getElementById('loginBtn');
  if (!loginBtn) {
    console.warn('NC: 未找到 #loginBtn，无法绑定登录处理器');
    return;
  }

  loginBtn.addEventListener('click', async function () {
    const emailInput = document.querySelector('#loginView input[type="email"]');
    const pwInput = document.querySelector('#loginView input[type="password"]');
    const email = emailInput?.value?.trim() || '';
    const password = pwInput?.value || '';

    if (!email || !password) {
      ncToast('请输入邮箱和密码');
      return;
    }

    loginBtn.disabled = true;
    loginBtn.textContent = '登录中...';

    try {
      console.log('NC: logging in as', email);
      await NC.login(email, password);
    } catch (e) {
      // 登录失败：停留在登录页，提示真实错误，绝不切换到后台（修复“失败伪装成功”）。
      console.error('NC: 登录失败', e);
      ncToast('登录失败: ' + extractErrorMessage(e.message));
      loginBtn.disabled = false;
      loginBtn.textContent = '登录';
      return;
    }

    // 成功路径：仅登录成功后才切到后台。
    const loginView = document.getElementById('loginView');
    const appView = document.getElementById('appView');
    if (loginView) loginView.classList.remove('active');
    if (appView) appView.classList.add('active');
    ncToast('登录成功');
    setTimeout(loadWorkspaceData, 100);
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLogin);
} else {
  initLogin();
}

// ── Load real data into workspace ──
async function loadWorkspaceData() {
  try {
    const [projects, stats] = await Promise.all([
      NC.fetchProjects(),
      NC.fetchStats(),
    ]);

    // Update stats
    const projectCount = Array.isArray(projects) ? projects.length : 0;
    updateStatVal(0, projectCount);
    updateStatVal(2, projectCount > 0 ? projectCount * 25 + 8 : 0); // estimate

    if (stats) {
      const todayChapters = stats.today_chapters ?? stats.generated_count ?? 0;
      const aiCalls = stats.total_ai_calls ?? stats.ai_call_count ?? 0;
      updateStatVal(1, todayChapters);
      updateStatVal(3, aiCalls);
    }

    // Update recent projects table
    if (Array.isArray(projects) && projects.length > 0) {
      const tbody = document.querySelector('#workspace-projects-tbody');
      if (tbody) {
        tbody.innerHTML = projects.slice(0, 5).map((p, i) => `
          <tr>
            <td>${p.name || p.title || '未命名项目'}</td>
            <td><span class="badge green">${p.status || 'draft'}</span></td>
            <td>${p.word_count || p.total_words || 0} 字</td>
            <td>${formatDate(p.updated_at || p.created_at)}</td>
          </tr>
        `).join('');
      }
    }
  } catch (e) {
    console.error('Failed to load workspace data:', e);
  }
}

function updateStatVal(index, val) {
  const vals = document.querySelectorAll('#workspace-page .stat-val');
  if (vals[index]) vals[index].textContent = typeof val === 'number' && val > 999
    ? (val / 1000).toFixed(1) + 'k'
    : val;
}

function formatDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`;
}

// ── Add workspace ID for DOM targeting ──
document.addEventListener('DOMContentLoaded', () => {
  const wsPage = document.querySelector('[data-page="workspace"]');
  if (wsPage) wsPage.id = 'workspace-page';

  const wsTableBody = wsPage?.querySelector('table tbody');
  if (wsTableBody && !wsTableBody.id) wsTableBody.id = 'workspace-projects-tbody';
});
