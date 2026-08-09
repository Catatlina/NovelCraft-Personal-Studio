/**
 * V7 quality and runtime monitor.
 *
 * V7 is the canonical prose generation chain, but this is an engineering
 * surface rather than another authoring workspace. Keep the default view
 * focused on quality signals, run evidence, cost provenance and prompt access.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  Coins,
  FileCode2,
  Gauge,
  GitBranch,
  LayoutDashboard,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Terminal,
  XCircle,
} from 'lucide-react';
import brainApi, { V7ApiError } from '../api/client';
import type { BrainOverview, EventItem, Run } from '../types';

type MonitorView = 'overview' | 'runs' | 'ledger' | 'prompts';

interface V7DashboardProps {
  novelId: string | null;
  onOpenProgress?: () => void;
  onOpenReview?: () => void;
  onOpenLibrary?: () => void;
}

interface MonitorData {
  overview: BrainOverview;
  runs: Run[];
  cost: Record<string, any> | null;
  ledger: Record<string, any> | null;
  director: Record<string, any> | null;
  pendingDecisions: any[];
  prompts: any[] | null;
  promptRestricted: boolean;
}

const VIEW_ITEMS: Array<{ key: MonitorView; label: string; description: string; icon: typeof Activity }> = [
  { key: 'overview', label: '总览', description: '质量与运行信号', icon: LayoutDashboard },
  { key: 'runs', label: '生成运行', description: '章节执行记录', icon: Activity },
  { key: 'ledger', label: '成本账本', description: 'V6/V7 统一记账', icon: Coins },
  { key: 'prompts', label: 'Prompt provenance', description: '版本与执行溯源', icon: FileCode2 },
];

const STATUS_LABELS: Record<string, string> = {
  completed: '已完成',
  succeeded: '已完成',
  running: '运行中',
  pending: '等待中',
  paused: '已暂停',
  failed: '失败',
  cancelled: '已取消',
  waiting_human: '待人工确认',
};

function isFulfilled<T>(result: PromiseSettledResult<T>): result is PromiseFulfilledResult<T> {
  return result.status === 'fulfilled';
}

function asRecord(value: unknown): Record<string, any> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, any>
    : null;
}

function statusLabel(status?: string | null): string {
  return status ? STATUS_LABELS[status] || status : '暂无记录';
}

function statusClass(status?: string | null): string {
  if (status === 'completed' || status === 'succeeded') return 'success';
  if (status === 'running' || status === 'waiting_human') return 'warning';
  if (status === 'failed') return 'danger';
  return 'neutral';
}

function formatDate(value?: string | null): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatMoney(value: unknown): string {
  const amount = Number(value);
  return Number.isFinite(amount) ? `¥${amount.toFixed(4)}` : '—';
}

function formatNumber(value: unknown): string {
  const amount = Number(value);
  return Number.isFinite(amount) ? amount.toLocaleString('zh-CN') : '—';
}

function errorMessage(reason: unknown): string {
  if (reason instanceof Error && reason.message) return reason.message;
  return '质量监控数据加载失败，请稍后重试';
}

function optionalFailureLabel(reason: unknown): string {
  if (reason instanceof V7ApiError && reason.status === 403) return '部分工程数据需要管理员权限';
  if (reason instanceof V7ApiError && reason.status === 503) return '统一账本暂时不可用';
  return '部分监控数据暂时不可用';
}

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  tone = 'indigo',
}: {
  icon: typeof Activity;
  label: string;
  value: string;
  detail: string;
  tone?: 'indigo' | 'green' | 'amber' | 'gray';
}) {
  return (
    <div className="v7-metric-card">
      <div className={`v7-metric-icon ${tone}`}><Icon size={18} /></div>
      <div className="v7-metric-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </div>
  );
}

function EmptyBlock({ children }: { children: string }) {
  return <div className="v7-empty-block">{children}</div>;
}

function EventList({ events }: { events: EventItem[] }) {
  if (!events.length) return <EmptyBlock>还没有可展示的运行事件</EmptyBlock>;
  return (
    <div className="v7-event-list">
      {events.slice(0, 6).map(event => (
        <div className="v7-event-row" key={event.id}>
          <span className={`v7-event-dot ${event.severity || 'info'}`} />
          <div>
            <strong>{event.name || event.type || '运行事件'}</strong>
            <p>{event.description || '事件已写入运行账本'}</p>
          </div>
          <time>{formatDate(event.time)}</time>
        </div>
      ))}
    </div>
  );
}

function RunList({ runs }: { runs: Run[] }) {
  if (!runs.length) return <EmptyBlock>还没有 V7 生成运行记录</EmptyBlock>;
  return (
    <div className="v7-run-list">
      {runs.slice(0, 8).map(run => (
        <div className="v7-run-row" key={run.id}>
          <span className={`v7-status-dot ${statusClass(run.status)}`} />
          <div className="v7-run-main">
            <strong>{run.run_type?.replace(/_/g, ' ') || 'chapter generation'}</strong>
            <span>第 {run.chapter_number || '—'} 章 · {formatDate(run.started_at)}</span>
          </div>
          <div className="v7-run-stat">
            <strong>{statusLabel(run.status)}</strong>
            <span>{formatMoney(run.total_cost)} · {formatNumber(run.total_tokens)} tokens</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function OverviewView({
  data,
  onOpenProgress,
  onOpenReview,
}: {
  data: MonitorData;
  onOpenProgress?: () => void;
  onOpenReview?: () => void;
}) {
  const latestRun = data.runs[0];
  const totalCost = data.cost?.actual_spend?.total_cost_cny ?? data.ledger?.cost_cny;
  const totalTokens = data.cost?.actual_spend?.total_tokens ?? data.ledger?.tokens;
  const pendingReview = Number(data.overview.states?.pending_review || 0);
  const pendingDecisions = data.pendingDecisions.length;
  const latestVersion = data.overview.latest_version?.version_number;

  return (
    <div className="v7-monitor-stack">
      <div className="v7-chain-callout">
        <div className="v7-chain-icon"><ShieldCheck size={20} /></div>
        <div>
          <strong>V7 是当前唯一正文生成链</strong>
          <p>章节正文、跨章连续性、质量审阅和重生成统一走 V7；V6 只负责兼容事实、章节承载和导出。</p>
        </div>
        <div className="v7-callout-actions">
          {onOpenProgress && <button type="button" className="v7-link-button" onClick={onOpenProgress}>去创作进度 <ArrowUpRight size={14} /></button>}
          {onOpenReview && <button type="button" className="v7-link-button" onClick={onOpenReview}>看质量审阅 <ArrowUpRight size={14} /></button>}
        </div>
      </div>

      <div className="v7-metric-grid">
        <MetricCard
          icon={AlertTriangle}
          label="待处理审阅"
          value={String(pendingReview + pendingDecisions)}
          detail={`${pendingReview} 条状态 · ${pendingDecisions} 个决策`}
          tone={pendingReview + pendingDecisions > 0 ? 'amber' : 'green'}
        />
        <MetricCard
          icon={Activity}
          label="最近运行"
          value={statusLabel(latestRun?.status)}
          detail={latestRun ? `第 ${latestRun.chapter_number || '—'} 章 · ${formatDate(latestRun.started_at)}` : '等待第一次生成'}
          tone={statusClass(latestRun?.status) === 'danger' ? 'amber' : 'indigo'}
        />
        <MetricCard
          icon={Coins}
          label="累计成本"
          value={formatMoney(totalCost)}
          detail={`${formatNumber(totalTokens)} tokens · 统一账本`}
          tone="gray"
        />
        <MetricCard
          icon={GitBranch}
          label="故事版本"
          value={latestVersion ? `v${latestVersion}` : '—'}
          detail={`${data.overview.states?.total || 0} 条故事状态已记录`}
          tone="green"
        />
      </div>

      <div className="v7-monitor-grid">
        <section className="v7-panel">
          <div className="v7-panel-head">
            <div><p className="v7-kicker">最近运行</p><h3>生成执行记录</h3></div>
            <span className="v7-panel-count">{data.runs.length} 条</span>
          </div>
          <RunList runs={data.runs} />
        </section>
        <section className="v7-panel">
          <div className="v7-panel-head">
            <div><p className="v7-kicker">运行事件</p><h3>最近质量信号</h3></div>
            <span className="v7-panel-count">{data.overview.recent_events.length} 条</span>
          </div>
          <EventList events={data.overview.recent_events} />
        </section>
      </div>

      <section className="v7-panel v7-signal-panel">
        <div className="v7-panel-head">
          <div><p className="v7-kicker">当前上下文</p><h3>故事状态摘要</h3></div>
          <span className="v7-panel-count">只读监控</span>
        </div>
        <div className="v7-signal-grid">
          <div><span>故事状态</span><strong>{formatNumber(data.overview.states?.total)}</strong><small>跨章记忆与事实</small></div>
          <div><span>创作目标</span><strong>{formatNumber(data.overview.goals?.total)}</strong><small>{formatNumber(data.overview.goals?.completed)} 个已完成</small></div>
          <div><span>有效约束</span><strong>{formatNumber(data.overview.constraints?.active)}</strong><small>用于生成前后校验</small></div>
          <div><span>运行时</span><strong>{data.director?.status === 'alpha' ? 'V7 Alpha' : '已接入'}</strong><small>统一 Gateway + provenance</small></div>
        </div>
      </section>
    </div>
  );
}

function RunsView({ data }: { data: MonitorData }) {
  return (
    <section className="v7-panel v7-detail-panel">
      <div className="v7-panel-head">
        <div><p className="v7-kicker">生成运行</p><h3>每次章节执行的真实记录</h3></div>
        <span className="v7-panel-count">按最近开始时间</span>
      </div>
      <RunList runs={data.runs} />
      <p className="v7-panel-note"><Terminal size={14} /> 详细步骤、Prompt hash 和模型 usage 保存在 Trace 与统一账本中。</p>
    </section>
  );
}

function LedgerView({ data }: { data: MonitorData }) {
  const actual = data.cost?.actual_spend;
  const gateways = Array.isArray(data.ledger?.gateway_versions) ? data.ledger.gateway_versions : [];
  const budgets = Array.isArray(data.cost?.budgets) ? data.cost.budgets : [];

  return (
    <div className="v7-monitor-stack">
      <div className="v7-ledger-metrics">
        <MetricCard icon={Coins} label="统一成本" value={formatMoney(data.ledger?.cost_cny ?? actual?.total_cost_cny)} detail="ai_execution_ledger" tone="gray" />
        <MetricCard icon={Gauge} label="调用次数" value={formatNumber(data.ledger?.calls ?? 0)} detail={`${formatNumber(data.ledger?.tokens ?? actual?.total_tokens)} tokens`} tone="indigo" />
        <MetricCard icon={GitBranch} label="Gateway 版本" value={String(gateways.length || '—')} detail="V6 / V7 可分项核对" tone="green" />
      </div>
      <section className="v7-panel v7-detail-panel">
        <div className="v7-panel-head">
          <div><p className="v7-kicker">跨版本账本</p><h3>V6 / V7 Provider 成本对账</h3></div>
          <span className="v7-panel-count">{data.ledger ? '已读取' : '未读取'}</span>
        </div>
        {gateways.length ? (
          <div className="v7-table-wrap">
            <table className="v7-table">
              <thead><tr><th>运行时</th><th>调用</th><th>Tokens</th><th>成本</th></tr></thead>
              <tbody>{gateways.map((item: any) => <tr key={item.gateway_version}>
                <td>{item.gateway_version}</td>
                <td>{formatNumber(item.calls)}</td>
                <td>{formatNumber(Number(item.prompt_tokens || 0) + Number(item.completion_tokens || 0))}</td>
                <td>{formatMoney(item.cost_cny)}</td>
              </tr>)}</tbody>
            </table>
          </div>
        ) : (
          <EmptyBlock>暂无跨版本账本记录；首次真实调用后会出现在这里</EmptyBlock>
        )}
        {budgets.length > 0 && <p className="v7-panel-note"><Coins size={14} /> 当前有 {budgets.length} 个预算规则，剩余额度以后台预算门为准。</p>}
      </section>
    </div>
  );
}

function PromptsView({ data }: { data: MonitorData }) {
  if (data.promptRestricted) {
    return (
      <section className="v7-panel v7-access-panel">
        <div className="v7-access-icon"><LockKeyhole size={22} /></div>
        <p className="v7-kicker">Prompt provenance</p>
        <h3>需要管理员权限</h3>
        <p>Prompt 版本和模板是工程审计数据，普通创作权限不会读取它们。生成链仍会正常记录 Prompt hash、版本和 usage。</p>
      </section>
    );
  }

  const prompts = data.prompts || [];
  const names = new Set(prompts.map(prompt => prompt.prompt_name).filter(Boolean));
  const active = prompts.filter(prompt => prompt.is_active).length;
  const defaults = prompts.filter(prompt => prompt.is_default).length;

  return (
    <div className="v7-monitor-stack">
      <div className="v7-ledger-metrics">
        <MetricCard icon={FileCode2} label="Prompt 身份" value={formatNumber(names.size)} detail="按 prompt_name 聚合" tone="indigo" />
        <MetricCard icon={CheckCircle2} label="活跃版本" value={formatNumber(active)} detail="当前可被运行时选用" tone="green" />
        <MetricCard icon={GitBranch} label="默认版本" value={formatNumber(defaults)} detail="已设置默认版本" tone="gray" />
      </div>
      <section className="v7-panel v7-detail-panel">
        <div className="v7-panel-head">
          <div><p className="v7-kicker">版本目录</p><h3>最近注册的 Prompt 版本</h3></div>
          <span className="v7-panel-count">{prompts.length} 个版本</span>
        </div>
        {!prompts.length ? <EmptyBlock>还没有 Prompt provenance 记录</EmptyBlock> : (
          <div className="v7-prompt-list">
            {prompts.slice(0, 12).map(prompt => (
              <div className="v7-prompt-row" key={prompt.id}>
                <div><strong>{prompt.prompt_name || '未命名 Prompt'}</strong><span>{prompt.version_label || `v${prompt.version || '—'}`} · {prompt.model || '默认模型'}</span></div>
                <div className="v7-prompt-badges">
                  {prompt.is_default && <span className="v7-mini-badge green">默认</span>}
                  {prompt.is_active && <span className="v7-mini-badge">活跃</span>}
                  <time>{formatDate(prompt.created_at)}</time>
                </div>
              </div>
            ))}
          </div>
        )}
        <p className="v7-panel-note"><FileCode2 size={14} /> 页面只展示版本索引，不展开模板正文，避免审计页面变成 Prompt 编辑器。</p>
      </section>
    </div>
  );
}

export function V7Dashboard({ novelId, onOpenProgress, onOpenReview, onOpenLibrary }: V7DashboardProps) {
  const [view, setView] = useState<MonitorView>('overview');
  const [loading, setLoading] = useState(Boolean(novelId));
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [data, setData] = useState<MonitorData | null>(null);

  const loadMonitor = useCallback(async () => {
    if (!novelId) {
      setData(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setWarnings([]);

    const results = await Promise.allSettled([
      brainApi.getOverview(novelId),
      brainApi.listRuns(novelId, { limit: 20 }),
      brainApi.getCostSummary(novelId),
      brainApi.getCrossVersionLedger(novelId),
      brainApi.getDirectorStatus(novelId),
      brainApi.getPendingDecisions(novelId),
      brainApi.listPromptVersions({ limit: 100 }, novelId),
    ]);

    const [overviewResult, runsResult, costResult, ledgerResult, directorResult, decisionsResult, promptsResult] = results;
    if (!isFulfilled(overviewResult)) {
      setData(null);
      setError(errorMessage(overviewResult.reason));
      setLoading(false);
      return;
    }

    const nextWarnings: string[] = [];
    const optionalResults = [
      ['生成运行', runsResult],
      ['成本汇总', costResult],
      ['统一账本', ledgerResult],
      ['运行状态', directorResult],
      ['待审阅决策', decisionsResult],
      ['Prompt 版本', promptsResult],
    ] as const;
    optionalResults.forEach(([label, result]) => {
      if (!isFulfilled(result)) nextWarnings.push(`${label}：${optionalFailureLabel(result.reason)}`);
    });

    const decisions = isFulfilled(decisionsResult) && Array.isArray(decisionsResult.value?.decisions)
      ? decisionsResult.value.decisions
      : [];
    const promptRestricted = !isFulfilled(promptsResult)
      && promptsResult.reason instanceof V7ApiError
      && [403, 503].includes(promptsResult.reason.status);

    setData({
      overview: overviewResult.value,
      runs: isFulfilled(runsResult) && Array.isArray(runsResult.value) ? runsResult.value : [],
      cost: isFulfilled(costResult) ? asRecord(costResult.value) : null,
      ledger: isFulfilled(ledgerResult) ? asRecord(ledgerResult.value) : null,
      director: isFulfilled(directorResult) ? asRecord(directorResult.value) : null,
      pendingDecisions: decisions,
      prompts: isFulfilled(promptsResult) && Array.isArray(promptsResult.value?.versions) ? promptsResult.value.versions : null,
      promptRestricted,
    });
    setWarnings(nextWarnings);
    setLoading(false);
  }, [novelId]);

  useEffect(() => { void loadMonitor(); }, [loadMonitor]);

  const viewTitle = useMemo(() => VIEW_ITEMS.find(item => item.key === view)?.label || '总览', [view]);

  return (
    <div className="v7-monitor page-enter">
      <header className="v7-monitor-head">
        <div>
          <p className="v7-kicker">工程监控 · {viewTitle}</p>
          <h2>质量与运行监控</h2>
          <p>只在需要排查生成质量、跨章状态、成本和 Prompt 证据时使用这里。</p>
        </div>
        <div className="v7-monitor-head-actions">
          <span className="v7-chain-badge"><Sparkles size={14} /> V7 唯一正文链</span>
          <button type="button" className="v7-refresh-button" onClick={() => void loadMonitor()} disabled={loading}>
            <RefreshCw size={15} className={loading ? 'v7-spin' : undefined} /> 刷新
          </button>
        </div>
      </header>

      <nav className="v7-view-nav" aria-label="质量监控视图">
        {VIEW_ITEMS.map(item => {
          const Icon = item.icon;
          return (
            <button
              type="button"
              key={item.key}
              className={view === item.key ? 'active' : ''}
              aria-selected={view === item.key}
              role="tab"
              onClick={() => setView(item.key)}
            >
              <Icon size={16} />
              <span><strong>{item.label}</strong><small>{item.description}</small></span>
            </button>
          );
        })}
      </nav>

      {!novelId ? (
        <section className="v7-panel v7-empty-panel">
          <div className="v7-access-icon"><GitBranch size={22} /></div>
          <h3>先选择一本小说</h3>
          <p>质量与运行数据按作品隔离。请先在书库选择作品，再查看 V7 的生成证据。</p>
          {onOpenLibrary && <button type="button" className="v7-primary-button" onClick={onOpenLibrary}>打开书库</button>}
        </section>
      ) : loading && !data ? (
        <section className="v7-panel v7-loading-panel"><span className="spinner" /> 正在读取真实运行数据…</section>
      ) : error ? (
        <section className="v7-panel v7-error-panel">
          <XCircle size={22} />
          <div><h3>监控数据暂时不可用</h3><p>{error}</p></div>
          <button type="button" className="v7-primary-button" onClick={() => void loadMonitor()}>重试</button>
        </section>
      ) : data ? (
        <>
          {warnings.length > 0 && <div className="v7-warning-strip"><AlertTriangle size={15} /><span>{warnings.join('；')}</span></div>}
          {view === 'overview' && <OverviewView data={data} onOpenProgress={onOpenProgress} onOpenReview={onOpenReview} />}
          {view === 'runs' && <RunsView data={data} />}
          {view === 'ledger' && <LedgerView data={data} />}
          {view === 'prompts' && <PromptsView data={data} />}
        </>
      ) : null}
    </div>
  );
}

export default V7Dashboard;
