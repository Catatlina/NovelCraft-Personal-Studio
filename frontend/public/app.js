/* NovelCraft prototype UI — extracted from proto.html inline <script>
 * Loaded as /app.js (external file) so it is NOT blocked by the
 * deployed CSP `script-src 'self'` policy (which forbids inline scripts).
 * This file owns navigation, theme, sidebar and settings UI wiring.
 */

function _oldEnterApp() { /* replaced by nc-bridge.js */ }

function goPage(p) {
  document.querySelectorAll('.nav-item[data-page]').forEach(n => n.classList.toggle('active', n.dataset.page === p));
  document.querySelectorAll('.page').forEach(s => s.classList.toggle('active', s.dataset.page === p));
  document.getElementById('content').scrollTop = 0;
  document.getElementById('sidebar').classList.remove('open');
  const map = {
    overview: '概览', workspace: '工作台', inspiration: '灵感创作', ranking: '扫榜选书',
    library: '书库管理', editor: '编辑器', progress: '创作进度', review: '审阅',
    foreshadow: '伏笔看板', hotspot: '热点追踪', content: '内容工作室', distribution: '多平台分发',
    knowledge: '知识库', publish: '发布看板', cost: '成本追踪', prompts: 'Prompt 管理',
    workflow: '工作流编排', version: '版本树', plugins: '插件管理', agents: '智能体',
    settings: '设置'
  };
  const t = document.querySelector('.page.active h1');
  // B1：进入屏后加载真实数据（未接屏的 p 在 loadPageData 内被忽略）
  if (typeof NC !== 'undefined' && typeof NC.loadPageData === 'function') {
    try { NC.loadPageData(p); } catch (e) { console.error('[app] loadPageData', p, e); }
  }
}

document.querySelectorAll('.nav-item[data-page]').forEach(n => n.addEventListener('click', () => goPage(n.dataset.page)));

function toggleGroup(el) { el.closest('.nav-group').classList.toggle('collapsed'); }
function toggleSidebar() { document.getElementById('sidebar').classList.toggle('collapsed'); }
function toggleTheme() {
  const h = document.documentElement;
  h.dataset.theme = h.dataset.theme === 'dark' ? 'light' : 'dark';
  document.querySelector('.theme-row .label').textContent = h.dataset.theme === 'dark' ? '暗色' : '亮色';
}
function setTheme(t) {
  document.documentElement.dataset.theme = t;
  document.querySelectorAll('.seg button').forEach(b => {});
  document.querySelector('.theme-row .label').textContent = t === 'dark' ? '暗色' : '亮色';
  document.querySelectorAll('#set-general .seg button').forEach(b => b.classList.toggle('on', (b.textContent === '暗色' && t === 'dark') || (b.textContent === '亮色' && t === 'light')));
}

let toastTimer;
function showToast(msg) {
  const to = document.getElementById('toast');
  document.getElementById('toastMsg').textContent = msg;
  to.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => to.classList.remove('show'), 2400);
}

function switchTab(el, id) {
  document.querySelectorAll('#settings .tab').forEach(t => t.classList.remove('on'));
  el.classList.add('on');
  ['set-general', 'set-provider', 'set-budget', 'set-team'].forEach(i => document.getElementById(i).style.display = i === id ? 'block' : 'none');
}

/* Register button (onclick="enterApp()") — minimal stub.
 * ncToast is defined in nc-api.js; since app.js loads first we guard defensively
 * so a click never throws a ReferenceError. */
function enterApp() {
  if (typeof ncToast === 'function') {
    ncToast('注册功能开发中');
  } else {
    alert('注册功能开发中');
  }
}
