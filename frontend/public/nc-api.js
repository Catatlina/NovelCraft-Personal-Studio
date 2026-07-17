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

/* ============================================================
 * B0 共享基建 + B1 数据展示屏
 * 在已有 login / fetchProjects / fetchStats / fetchBooks /
 * fetchChapters / loadWorkspaceData 基础上扩展，不破坏登录。
 * ============================================================ */

/* ---------- 小工具 ---------- */
function ncEsc(v) {
  if (v == null) return '';
  return String(v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}
function ncNum(v, d) {
  if (d === undefined) d = 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : d;
}
function statusText(s) {
  const m = { draft: '草稿', writing: '连载', serializing: '连载', published: '已发布', completed: '完结', finished: '完结' };
  return m[s] || s || '—';
}
// 给单行 HTML 根元素补 data-id（优先 item.id / book_id / topic_id / account_id / post_id / source_key / name）
function ncWithDataId(html, item, idx) {
  if (typeof html !== 'string') return html;
  const id = item && (item.id ?? item.book_id ?? item.topic_id ?? item.account_id ?? item.post_id ?? item.source_key ?? item.name ?? idx);
  if (id == null) return html;
  return html.replace(/^(\s*<[a-zA-Z][^>]*)(\s*\/?>)/, '$1 data-id="' + ncEsc(id) + '"$2');
}

// 预算接口（/api/v1/admin/budgets）真实返回【数组】；取 monthly 作用域优先，否则取首个。
// 修复 BUG-2：原 loader 把 d 当对象读 b.limit_cny，在数组上为 undefined→全 0。
function ncFirstBudget(d) {
  const arr = Array.isArray(d) ? d : [d];
  return arr.find((x) => x && x.scope === 'monthly') || arr[0] || {};
}

/* ---------- B0: 当前项目上下文 ---------- */
let _ncProjectId = sessionStorage.getItem('nc_project') || '';
Object.defineProperty(NC, 'currentProjectId', {
  configurable: true,
  get() { return _ncProjectId; },
  set(v) {
    _ncProjectId = v || '';
    if (_ncProjectId) sessionStorage.setItem('nc_project', _ncProjectId);
  },
});
NC.setCurrentProject = function (id) { NC.currentProjectId = id; };

// 登录后确保有当前项目：sessionStorage 无 nc_project 时取 projects[0].id
NC.ensureCurrentProject = async function () {
  const saved = sessionStorage.getItem('nc_project');
  if (saved) { NC.currentProjectId = saved; return saved; }
  try {
    const projects = await NC.fetchProjects();
    if (Array.isArray(projects) && projects.length > 0) NC.currentProjectId = projects[0].id;
  } catch (e) {
    console.warn('[NC] 获取当前项目失败', e);
  }
  return NC.currentProjectId;
};

// 扩展原 login：成功后设置 currentProjectId（保留原有逻辑）
const _ncLoginOrig = NC.login;
NC.login = async function (email, password) {
  const data = await _ncLoginOrig.call(NC, email, password);
  await NC.ensureCurrentProject();
  return data;
};

/* ---------- B0: 通用渲染 helper ---------- */
NC.renderList = function (container, items, rowFn, emptyText) {
  const el = typeof container === 'string' ? document.getElementById(container.replace(/^#/, '')) : container;
  if (!el) return;
  if (!Array.isArray(items) || items.length === 0) {
    el.innerHTML = emptyText != null ? emptyText : '';
    return;
  }
  el.innerHTML = items.map((item, idx) => ncWithDataId(rowFn(item, idx), item, idx)).join('');
};

// 统一三态：pending 显“加载中…”；成功调 renderFn(data)；失败 toast + 保留写死兜底（不覆盖）
NC.withState = async function (container, promiseFn, renderFn, emptyText) {
  const el = typeof container === 'string' ? document.getElementById(container.replace(/^#/, '')) : container;
  if (!el) {
    try {
      const data = await promiseFn();
      if (typeof renderFn === 'function') await renderFn(data);
    } catch (e) {
      ncToast('加载失败: ' + extractErrorMessage(e.message));
    }
    return;
  }
  const fallback = el.innerHTML; // 保留写死兜底
  el.innerHTML = '加载中…';
  try {
    const data = await promiseFn();
    if (typeof renderFn === 'function') await renderFn(data);
    // 修复 BUG-6：renderFn 因空数据早退未写入时，容器仍停在“加载中…”。
    // 此时恢复写死兜底，或写入 emptyText，避免永久卡死。
    if (el.innerHTML === '加载中…') {
      el.innerHTML = (emptyText != null) ? emptyText : fallback;
    }
  } catch (e) {
    ncToast('加载失败: ' + extractErrorMessage(e.message));
    el.innerHTML = fallback; // 失败恢复写死内容
  }
};

// 渲染统计卡片网格：cards = [{label, value, hint?}]
NC.statCards = function (container, cards) {
  const el = typeof container === 'string' ? document.getElementById(container.replace(/^#/, '')) : container;
  if (!el) return;
  if (!Array.isArray(cards) || cards.length === 0) { el.innerHTML = ''; return; }
  el.innerHTML = cards.map((c) =>
    '<div class="stat">' +
      '<div class="stat-top"><span class="stat-label">' + ncEsc(c.label) + '</span></div>' +
      '<div class="stat-val">' + ncEsc(c.value) + '</div>' +
      (c.hint != null ? '<div class="stat-trend">' + ncEsc(c.hint) + '</div>' : '') +
    '</div>'
  ).join('');
};

// 无当前项目时提示并跳 workspace；否则返回 true
NC.needProject = function () {
  if (!NC.currentProjectId) {
    ncToast('请先选择一个项目');
    if (typeof goPage === 'function') goPage('workspace');
    return false;
  }
  return true;
};

// 带 project_id 的 GET 请求（用于需项目的端点）
NC.apiGet = async function (path, projectScoped) {
  const q = projectScoped ? (path.indexOf('?') >= 0 ? '&' : '?') + 'project_id=' + encodeURIComponent(NC.currentProjectId) : '';
  return NC.api(path + q);
};

/* ---------- B1: 各屏 loader ---------- */

// 概览
NC.loadOverview = async function () {
  await NC.withState('#overview-stats',
    () => NC.api('/api/v1/analytics/dashboard'),
    (d) => {
      const data = d || {};
      // 修复 BUG-1：真实 /api/v1/analytics/dashboard 返回 { metrics_glossary, totals, ... }，
      // totals = { total_reads, total_likes, total_shares, total_revenue, total_posts }（当前全 0，属正常）。
      // 不再读不存在的 stats/summary/trend/genres/activity 字段。
      const t = data.totals || {};
      const cards = [
        { label: '发布内容', value: ncNum(t.total_posts), hint: '已发布作品数' },
        { label: '总阅读', value: ncNum(t.total_reads), hint: '累计阅读量' },
        { label: '总点赞', value: ncNum(t.total_likes), hint: '累计点赞' },
        { label: '总收入', value: '¥' + ncNum(t.total_revenue), hint: '累计收益' },
      ];
      NC.statCards('#overview-stats', cards);

      const trend = Array.isArray(data.trend) ? data.trend : [];
      const tEl = document.getElementById('overview-trend');
      if (tEl && trend.length) {
        const max = Math.max.apply(null, trend.map((x) => ncNum(x.value ?? x.count ?? x)));
        tEl.innerHTML = trend.map((x, i) => {
          const v = ncNum(x.value ?? x.count ?? x);
          const h = max ? Math.round((v / max) * 100) : 0;
          return '<div class="bar" style="height:' + h + '%"><span>' + ncEsc(x.label ?? (i + 1)) + '</span></div>';
        }).join('');
      }

      const genres = Array.isArray(data.genres) ? data.genres : [];
      const gEl = document.getElementById('overview-genre');
      if (gEl && genres.length) {
        const colors = ['#6366F1', '#22D3EE', '#FB923C', '#34D399', '#F87171'];
        gEl.innerHTML = genres.map((g, i) =>
          '<div class="legend-item"><span class="sw" style="background:' + colors[i % colors.length] + '"></span>' + ncEsc(g.name ?? g.genre) + ' · ' + ncNum(g.percent ?? g.ratio) + '%</div>'
        ).join('');
      }

      const acts = Array.isArray(data.activity) ? data.activity : [];
      const aEl = document.getElementById('overview-activity');
      if (aEl && acts.length) {
        aEl.innerHTML = acts.map((a) =>
          '<div class="activity"><div class="av-sm"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/></svg></div><div><p>' + ncEsc(a.title ?? a.text ?? '') + '</p><time>' + ncEsc(a.time ?? '') + '</time></div></div>'
        ).join('');
      }
    });
};

// 工作台（扩展：系统状态 / 预算 / 设置）
NC.loadWorkspace = async function () {
  await NC.withState('#ws-system-status',
    () => NC.api('/api/v1/admin/env-check'),
    (d) => {
      const items = Array.isArray(d) ? d : (d && d.checks ? d.checks : (d && d.items ? d.items : []));
      const el = document.getElementById('ws-system-status');
      if (!el) return;
      if (items.length) {
        el.innerHTML = items.map((it) => {
          const ok = it.status === 'ok' || it.ok || it.healthy;
          const color = ok ? 'green' : (it.status === 'warn' ? 'orange' : 'red');
          return '<div class="activity"><span class="dot ' + color + '"></span><div><strong style="font-size:13px">' + ncEsc(it.name ?? it.service ?? '服务') + '</strong><span class="cell-sub" style="display:block">' + ncEsc(it.detail ?? it.message ?? '') + '</span></div></div>';
        }).join('');
      }
    });

  if (NC.needProject()) {
    await NC.withState('#ws-stats',
      () => NC.apiGet('/api/v1/admin/budgets', true),
      (d) => {
        const b = ncFirstBudget(d); // 修复 BUG-2：budgets 返回数组
        const limit = ncNum(b.limit_cny ?? b.limit);
        const spent = ncNum(b.spent_cny ?? b.spent);
        const pct = limit ? Math.round((spent / limit) * 100) : 0;
        const el = document.getElementById('ws-stats');
        if (el) el.innerHTML = '<div class="ticket"><h5>本月预算 ' + pct + '%</h5><div class="meta"><span class="badge ' + (pct > 90 ? 'red' : 'orange') + '">' + spent + ' / ' + limit + ' 元</span></div></div>';
      });
  }

  await NC.withState('#ws-todos',
    () => NC.api('/api/v1/admin/settings'),
    (d) => {
      const items = Array.isArray(d) ? d : (d && d.settings ? d.settings : (d && d.items ? d.items : []));
      const el = document.getElementById('ws-todos');
      if (!el) return;
      if (items.length) {
        el.innerHTML = items.slice(0, 5).map((it) =>
          '<div class="ticket"><h5>' + ncEsc(it.key ?? it.name ?? '配置') + '</h5><div class="meta"><span class="badge gray">' + ncEsc(it.value ?? '') + '</span></div></div>'
        ).join('');
      }
    });
};

// 扫榜选书 —— 实时热销榜（按平台快照），需项目。
// 取数路径：sources → 选中 source 最新 snapshot(id) → snapshots/{id}.items(ranking_items)
// 注意：/ranking/snapshots 列表只返回快照元数据；书行在 /ranking/snapshots/{id} 的 items 中。
NC.loadRanking = async function () {
  if (!NC.needProject()) return;

  // 1) 平台下拉（option value = source_key）
  await NC.withState('#ranking-source-select',
    () => NC.apiGet('/api/v1/ranking/sources', true),
    (d) => {
      const sources = Array.isArray(d) ? d : (d && d.sources ? d.sources : []);
      const sel = document.getElementById('ranking-source-select');
      if (!sel) return;
      sel.innerHTML = sources.map((s) =>
        '<option value="' + ncEsc(s.source_key ?? s.key) + '" ' + (s.enabled ? '' : 'disabled') + '>' + ncEsc(s.display_name ?? s.name) + '</option>'
      ).join('');
      // 记忆已选 source；否则默认第一个
      if (NC._rankingSource && sources.some((s) => (s.source_key ?? s.key) === NC._rankingSource)) {
        sel.value = NC._rankingSource;
      } else if (sources.length) {
        NC._rankingSource = sSourceKey(sources[0]);
      }
      sel.onchange = () => { NC._rankingSource = sel.value; NC.loadRankingTable(); };
    });

  // 2)+3) 拉当前 source 最新快照书榜
  await NC.loadRankingTable();
};

// 取 source_key 的小工具
function sSourceKey(s) { return s && (s.source_key ?? s.key); }

// 渲染当前选中 source 的快照书榜（#ranking-tbody）
NC.loadRankingTable = async function () {
  if (!NC.needProject()) return;
  const sourceKey = NC._rankingSource;
  if (!sourceKey) return;
  await NC.withState('#ranking-tbody',
    async () => {
      // 2) 该 source 的最新快照 id（captured_at 最大者）
      const snaps = await NC.apiGet('/api/v1/ranking/snapshots', true);
      const list = Array.isArray(snaps) ? snaps : (snaps && snaps.items ? snaps.items : []);
      const mine = list.filter((s) => (s.source_key ?? s.key) === sourceKey);
      mine.sort((a, b) => String(b.captured_at || '').localeCompare(String(a.captured_at || '')));
      const latest = mine[0];
      if (!latest || !latest.id) return [];
      // 3) 快照书行
      const detail = await NC.api('/api/v1/ranking/snapshots/' + encodeURIComponent(latest.id));
      const items = (detail && detail.items) ? detail.items : (Array.isArray(detail) ? detail : []);
      return items;
    },
    (items) => {
      const tbody = document.getElementById('ranking-tbody');
      if (!tbody) return;
      if (items && items.length) {
        tbody.innerHTML = items.map((r) => {
          const rankNo = ncNum(r.rank_no ?? 0) || 1;
          return '<tr data-id="' + ncEsc(r.id ?? '') + '">' +
            '<td><span class="rank ' + (rankNo <= 3 ? 'top' : '') + '">' + rankNo + '</span></td>' +
            '<td><b>' + ncEsc(r.title ?? '—') + '</b></td>' +
            '<td>' + ncEsc(r.author ?? '—') + '</td>' +
            '<td>' + ncEsc(r.category ?? '—') + '</td>' +
            '<td>—</td>' + // 热度：metrics 字段名待 QA 真机确认，暂显「—」
            '<td>—</td>' + // 周涨：同上
            '<td><button class="btn-sm btn-ghost" onclick="showToast(\'已加入书库\')">+ 收藏</button></td>' +
            '</tr>';
        }).join('');
      } else {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-3)">暂无榜单数据</td></tr>';
      }
    });
};

// 刷新：触发该 source 重新扫描，再拉书榜（bookmark 本期占位不调，避免 422）
NC.refreshRanking = async function () {
  if (!NC.needProject()) return;
  const sourceKey = NC._rankingSource;
  if (!sourceKey) { NC.loadRanking(); return; }
  try {
    await NC.api('/api/v1/ranking/sources/' + encodeURIComponent(sourceKey) + '/scan?project_id=' + encodeURIComponent(NC.currentProjectId), { method: 'POST' });
    ncToast('已开始重新扫描 ' + sourceKey);
  } catch (e) {
    ncToast('扫描失败: ' + extractErrorMessage(e.message));
  }
  await NC.loadRankingTable();
};

// 书库管理（需项目）
NC.loadLibrary = async function () {
  if (!NC.needProject()) return;
  await NC.withState('#library-grid',
    () => NC.apiGet('/api/v1/ranking/library/books?limit=50', true),
    (d) => {
      const books = Array.isArray(d) ? d : (d && d.items ? d.items : (d && d.books ? d.books : []));
      const grid = document.getElementById('library-grid');
      if (!grid) return;
      if (books.length) {
        grid.innerHTML = books.map((b) =>
          '<div class="book" data-book-id="' + ncEsc(b.id ?? '') + '" onclick="goPage(\'editor\')">' +
            '<div class="book-cover" style="background:linear-gradient(135deg,#6366F1,#22D3EE)">' + ncEsc((b.title || '?').slice(0, 1)) + '</div>' +
            '<div class="book-info"><h4>' + ncEsc(b.title ?? '未命名') + '</h4><p>' + ncEsc(b.genre ?? '—') + ' · ' + ncNum(b.chapter_count) + ' 章 · ' + ncEsc(statusText(b.status)) + '</p></div>' +
          '</div>'
        ).join('');
      } else {
        grid.innerHTML = '<div style="color:var(--text-3);padding:24px">书库为空</div>';
      }
    });
};

// 热点追踪
NC.loadHotspot = async function () {
  await NC.withState('#hotspot-flow',
    () => NC.api('/api/v1/hotspots'),
    (d) => {
      const hs = (d && d.hotspots) ? d.hotspots : (Array.isArray(d) ? d : []);
      const el = document.getElementById('hotspot-flow');
      if (el && hs.length) {
        el.innerHTML = hs.slice(0, 8).map((h, i) =>
          '<div class="activity"><span class="dot ' + ['orange', 'cyan', 'green', 'gray'][i % 4] + '"></span><div><p><b>' + ncEsc(h.title ?? h.topic ?? '') + '</b> ' + ncEsc(h.metric ?? '') + '</p><time>' + ncEsc(h.source ?? '') + ' · ' + ncEsc(h.time ?? '') + '</time></div></div>'
        ).join('');
      }
    });

  await NC.withState('#hotspot-suggest',
    () => NC.api('/api/v1/hotspots/overview'),
    (d) => {
      // 修复 BUG-4：真实 /hotspots/overview 无 suggestions 字段，改用
      // recommended_angles[{title,source,angle,hotness}] 或 predicted_viral[{title,source,hotness,reason}]。
      const sug = (d && (d.recommended_angles || d.predicted_viral))
        ? (d.recommended_angles || d.predicted_viral)
        : (Array.isArray(d) ? d : []);
      const el = document.getElementById('hotspot-suggest');
      if (el && sug.length) {
        el.innerHTML = sug.slice(0, 6).map((s) =>
          '<div class="ticket" style="margin-bottom:12px"><h5>' + ncEsc(s.title ?? '') + '</h5><div class="meta"><span class="badge cyan">' + ncEsc(s.source ?? '建议') + '</span><span>' + ncEsc(s.angle ?? s.reason ?? '') + '</span></div></div>'
        ).join('');
      }
    });
};

// 多平台分发
NC.loadDistribution = async function () {
  await NC.withState('#distribution-grid',
    () => Promise.all([NC.api('/api/v1/platform-connections'), NC.api('/api/v1/publish/accounts')]),
    (res) => {
      const list = Array.isArray(res[0]) ? res[0] : (res[0] && res[0].items ? res[0].items : []);
      const grid = document.getElementById('distribution-grid');
      if (!grid) return;
      if (list.length) {
        grid.innerHTML = list.map((c) => {
          const configured = c.configured || c.status === 'connected';
          return '<div class="pcard" data-account-id="' + ncEsc(c.account_id ?? c.id ?? c.platform ?? '') + '">' +
            '<div class="pic" style="background:rgba(34,211,238,.12);color:var(--cyan)">' + ncEsc((c.platform || '?').slice(0, 1)) + '</div>' +
            '<h4>' + ncEsc(c.platform || c.name || '平台') + '</h4>' +
            '<p>' + ncEsc(c.account_name || c.display_name || '未命名账号') + '</p>' +
            '<div class="foot"><span class="badge ' + (configured ? 'green' : 'gray') + '"><span class="dot ' + (configured ? 'green' : 'gray') + '"></span>' + (configured ? '已连接' : '未连接') + '</span><button class="btn-sm btn-ghost" onclick="showToast(\'已发布\')">发布</button></div>' +
            '</div>';
        }).join('');
      } else {
        grid.innerHTML = '<div style="color:var(--text-3);padding:24px">暂未连接分发平台</div>';
      }
    });
};

// 发布看板
NC.loadPublish = async function () {
  await NC.withState('#publish-board',
    () => Promise.all([
      NC.api('/api/v1/publish/history'),
      NC.api('/api/v1/publish/stats'),
      NC.api('/api/v1/publish/roi'),
      NC.api('/api/v1/analytics/roi'),
      NC.api('/api/v1/publish/topic-suggestions'),
    ]),
    (res) => {
      const posts = Array.isArray(res[0]) ? res[0] : (res[0] && res[0].items ? res[0].items : []);
      const board = document.getElementById('publish-board');
      if (!board) return;
      const isPub = (p) => p.status === 'published' || p.state === 'published';
      const isErr = (p) => p.status === 'error' || p.status === 'limited' || p.state === 'error';
      const drafts = posts.filter((p) => !isPub(p) && !isErr(p));
      const published = posts.filter(isPub);
      const abnormal = posts.filter(isErr);
      const col = (title, items) =>
        '<div class="col"><div class="col-head">' + title + ' <span class="cnt">' + items.length + '</span></div>' +
        (items.length ? items.map((p) =>
          '<div class="ticket"><h5>' + ncEsc(p.title ?? p.post_title ?? '未命名') + '</h5><div class="meta"><span>' + ncEsc(p.platform ?? '—') + '</span><span class="badge ' + (isPub(p) ? 'green' : (isErr(p) ? 'red' : 'gray')) + '">' + ncEsc(p.metric ?? p.status ?? '') + '</span></div></div>'
        ).join('') : '<div class="ticket"><div class="meta"><span class="badge gray">暂无</span></div></div>') +
        '</div>';
      board.innerHTML = col('草稿', drafts) + col('已发布', published) + col('数据异常', abnormal);
    });
};

// 成本追踪（需项目）
NC.loadCost = async function () {
  if (!NC.needProject()) return;
  await NC.withState('#cost-stats',
    () => NC.apiGet('/api/v1/admin/budgets', true),
    (d) => {
      const b = ncFirstBudget(d); // 修复 BUG-2：budgets 返回数组
      const limit = ncNum(b.limit_cny ?? b.limit);
      const spent = ncNum(b.spent_cny ?? b.spent);
      const calls = ncNum(b.call_count ?? b.calls);
      const avg = calls ? (spent / calls).toFixed(2) : '0.00';
      const pct = limit ? Math.round((spent / limit) * 100) : 0;
      NC.statCards('#cost-stats', [
        { label: '本月花费', value: '¥' + spent, hint: '预算 ¥' + limit },
        { label: '调用次数', value: calls, hint: pct + '% 预算' },
        { label: '平均单价', value: '¥' + avg, hint: '' },
        { label: '预算使用率', value: pct + '%', hint: pct > 90 ? '超阈值' : '预算内' },
      ]);
    });

  await NC.withState('#cost-bars',
    () => NC.api('/api/v1/analytics/roi'),
    (d) => {
      // 修复 BUG-5：/publish/roi 与 /analytics/roi 均无 models 字段；
      // 改用 /analytics/roi 聚合字段渲染成本概览。
      const data = d || {};
      const metrics = [
        { label: '总成本(元)', value: ncNum(data.total_cost_cny) },
        { label: '内容数', value: ncNum(data.content_count) },
        { label: '总字数', value: ncNum(data.total_words) },
        { label: '千字成本(元)', value: ncNum(data.cost_per_1k_words) },
      ];
      const el = document.getElementById('cost-bars');
      if (el) {
        const max = Math.max.apply(null, metrics.map((m) => m.value)) || 1;
        el.innerHTML = metrics.map((m) => {
          const h = Math.round((m.value / max) * 100);
          return '<div class="bar" style="height:' + h + '%"><span>' + ncEsc(m.label) + ' ' + m.value + '</span></div>';
        }).join('');
      }
      const lg = document.getElementById('cost-legend');
      if (lg) {
        const colors = ['#6366F1', '#22D3EE', '#FB923C', '#34D399', '#F87171'];
        lg.innerHTML = metrics.map((m, i) =>
          '<div class="legend-item"><span class="sw" style="background:' + colors[i % colors.length] + '"></span>' + ncEsc(m.label) + '：' + m.value + '</div>'
        ).join('');
      }
    });
};

// Prompt 管理（只读列表）
NC.loadPrompts = async function () {
  await NC.withState('#prompts-list',
    () => NC.api('/api/v1/admin/prompts'),
    (d) => {
      const list = Array.isArray(d) ? d : (d && d.prompts ? d.prompts : (d && d.items ? d.items : []));
      NC.renderList('#prompts-list', list, (p) =>
        '<div class="ticket" style="cursor:pointer" onclick="showToast(\'已载入模板\')">' +
          '<h5>' + ncEsc(p.name ?? '未命名模板') + '</h5>' +
          '<div class="meta"><span class="badge purple">' + ncEsc(p.category ?? '创作') + '</span><span>使用 ' + ncNum(p.usage_count ?? p.used) + ' 次</span></div>' +
        '</div>',
        '<div style="color:var(--text-3);padding:24px">暂无 Prompt 模板</div>');
    });
};

// 工作流编排（需项目）
NC.loadWorkflow = async function () {
  if (!NC.needProject()) return;
  await NC.withState('#workflow-dag',
    () => NC.apiGet('/api/v1/admin/workflows', true),
    (d) => {
      const list = Array.isArray(d) ? d : (d && d.workflows ? d.workflows : (d && d.items ? d.items : []));
      const dag = document.getElementById('workflow-dag');
      if (!dag) return;
      if (!list.length) { dag.innerHTML = '<div class="node"><h5>暂无工作流</h5><p>前往工作流编排创建</p></div>'; return; }
      const wf = list[0] || {};
      const nodes = (wf.definition && wf.definition.nodes) ? wf.definition.nodes : (Array.isArray(wf.nodes) ? wf.nodes : []);
      if (nodes.length) {
        dag.innerHTML = nodes.map((n, i) =>
          '<div class="node ' + (i === 0 ? 'run' : '') + '"><h5>' + ncEsc(n.label ?? n.name ?? n.title ?? '节点') + '</h5><p>' + ncEsc(n.description ?? n.type ?? '') + '</p></div>' + (i < nodes.length - 1 ? '<div class="arrow">→</div>' : '')
        ).join('');
      } else {
        dag.innerHTML = '<div class="node"><h5>' + ncEsc(wf.name ?? '工作流') + '</h5><p>' + (wf.is_preset ? '预设' : '自定义') + '</p></div>';
      }
    });
};

// 设置（供应商 / 预算 / 通用 + 账户）
NC.loadSettings = async function () {
  await NC.withState('#settings-provider-tbody',
    () => NC.api('/api/v1/admin/providers'),
    (d) => {
      const list = Array.isArray(d) ? d : (d && d.providers ? d.providers : (d && d.items ? d.items : []));
      NC.renderList('#settings-provider-tbody', list, (p) => {
        const ok = p.key_configured || p.configured || p.status === 'online';
        const isDefault = p.default_model || p.is_default;
        return '<tr data-id="' + ncEsc(p.name ?? '') + '">' +
          '<td>' + ncEsc(p.name ?? '—') + '</td>' +
          '<td>' + ncEsc(p.default_model ?? p.model ?? '—') + '</td>' +
          '<td><span class="badge ' + (ok ? 'green' : 'gray') + '"><span class="dot ' + (ok ? 'green' : 'gray') + '"></span>' + (ok ? '在线' : '未配置') + '</span></td>' +
          '<td><span class="badge ' + (isDefault ? 'purple' : 'gray') + '">' + (isDefault ? '默认' : '备用') + '</span></td>' +
          '</tr>';
      });
    });

  if (NC.needProject()) {
    await NC.withState('#settings-budget-fields',
      () => NC.apiGet('/api/v1/admin/budgets', true),
      (d) => {
        const b = ncFirstBudget(d); // 修复 BUG-2：budgets 返回数组
        const limit = ncNum(b.limit_cny ?? b.limit);
        const spent = ncNum(b.spent_cny ?? b.spent);
        const pct = limit ? Math.round((spent / limit) * 100) : 0;
        const el = document.getElementById('settings-budget-fields');
        if (el) el.innerHTML = '<div class="hint">本月预算：' + limit + ' 元 · 已用 ' + spent + ' 元（' + pct + '%）</div>';
      });
  }

  const me = await NC.api('/api/v1/auth/me').catch(() => null);
  await NC.withState('#settings-general-fields',
    () => NC.api('/api/v1/admin/settings'),
    (d) => {
      const items = Array.isArray(d) ? d : (d && d.settings ? d.settings : (d && d.items ? d.items : []));
      const el = document.getElementById('settings-general-fields');
      if (!el) return;
      const email = me && (me.email ?? (me.user && me.user.email));
      let html = email ? '<div class="hint">当前账户：' + ncEsc(email) + '</div>' : '';
      if (items.length) {
        html += items.slice(0, 6).map((it) =>
          '<div class="hint">' + ncEsc(it.key ?? it.name ?? '配置') + '：' + ncEsc(it.value ?? '') + '</div>'
        ).join('');
      }
      el.innerHTML = html;
    });
};

/* ---------- B1: goPage 分发 ---------- */
NC.loadPageData = async function (p) {
  const map = {
    overview: NC.loadOverview,
    workspace: NC.loadWorkspace,
    ranking: NC.loadRanking,
    library: NC.loadLibrary,
    hotspot: NC.loadHotspot,
    distribution: NC.loadDistribution,
    publish: NC.loadPublish,
    cost: NC.loadCost,
    prompts: NC.loadPrompts,
    workflow: NC.loadWorkflow,
    settings: NC.loadSettings,
  };
  const loader = map[p];
  if (typeof loader !== 'function') return; // 未接屏（inspiration/editor 等）不处理
  try { await loader.call(NC); }
  catch (e) { console.error('[NC] loadPageData 失败:', p, e); }
};
