/* NovelCraft API Bridge — connects prototype UI to real backend */

// Local toast (don't rely on inline script's showToast timing)
function ncToast(msg) {
  const to = document.getElementById('toast');
  const msgEl = document.getElementById('toastMsg');
  if (msgEl) msgEl.textContent = msg;
  if (to) { to.classList.add('show'); setTimeout(() => to.classList.remove('show'), 2400); }
}

const NC = {
  base: '',
  token: sessionStorage.getItem('nc_token') || '',

  async api(path, opts = {}) {
    const headers = { 'Content-Type': 'application/json', ...opts.headers };
    if (NC.token) headers['Authorization'] = `Bearer ${NC.token}`;
    const res = await fetch(NC.base + path, { ...opts, headers });
    if (!res.ok) throw new Error(await res.text());
    const json = await res.json();
    return json.data ?? json;
  },

  async login(email, password) {
    try {
      const data = await NC.api('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      NC.token = data.access_token;
      sessionStorage.setItem('nc_token', NC.token);
      return data;
    } catch (e) {
      ncToast('登录失败: ' + e.message);
      throw e;
    }
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

// ── Enhanced login (force-override inline enterApp) ──
window.enterApp = async function() {
  const emailInput = document.querySelector('#loginView input[type="email"]');
  const pwInput = document.querySelector('#loginView input[type="password"]');
  const email = emailInput?.value?.trim() || '';
  const password = pwInput?.value || '';
  
  if (!email || !password) {
    ncToast('请输入邮箱和密码');
    return;
  }

  try {
    console.log('NC: logging in as', email);
    await NC.login(email, password);
    document.getElementById('loginView').classList.remove('active');
    document.getElementById('appView').classList.add('active');
    ncToast('登录成功');
    setTimeout(loadWorkspaceData, 100);
  } catch (e) {
    console.error('NC: login error', e);
  }
};

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
  return `${d.getMonth()+1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}`;
}

// ── Add workspace ID for DOM targeting ──
document.addEventListener('DOMContentLoaded', () => {
  const wsPage = document.querySelector('[data-page="workspace"]');
  if (wsPage) wsPage.id = 'workspace-page';
  
  const wsTableBody = wsPage?.querySelector('table tbody');
  if (wsTableBody && !wsTableBody.id) wsTableBody.id = 'workspace-projects-tbody';
});
