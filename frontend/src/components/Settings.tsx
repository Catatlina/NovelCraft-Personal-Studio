import { ChangeEvent, useEffect, useState } from "react";
import { BarChart3, Check, ChevronDown, Database, Eye, EyeOff, KeyRound, Lock, Plus, RotateCcw, Save, SlidersHorizontal, Trash2, Upload } from "lucide-react";
import {
  api,
  getApiKey,
  getApiUrl,
  getModel,
  setApiKey,
  setApiUrl,
  setModel,
} from "../lib/api";
import { Badge } from "../components/ui";
import { version as appVersion } from "../../package.json";

type SettingsTab = "ai" | "quality" | "data" | "account";
type Stats = { ai_calls: number; contents: number; db_size: string };
type LexiconPhrase = { phrase: string; enabled: boolean; note: string };
type LexiconCategory = { key: string; label: string; description: string; enabled: boolean; phrases: LexiconPhrase[] };
type AiFlavorLexicon = {
  schema_version: string;
  version: number;
  mode: "advisory";
  hard_gate: false;
  source?: string;
  setting_key?: string;
  editable?: boolean;
  category_count?: number;
  phrase_count?: number;
  enabled_phrase_count?: number;
  usage_note?: string;
  categories: LexiconCategory[];
};

export function Settings({ projectId = "" }: { projectId?: string }) {
  const [tab, setTab] = useState<SettingsTab>("ai");
  const [apiKey, setApiKeyValue] = useState(getApiKey);
  const [apiUrl, setApiUrlValue] = useState(getApiUrl);
  const [model, setModelValue] = useState(getModel);
  const [showKey, setShowKey] = useState(false);
  const [configDirty, setConfigDirty] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsError, setStatsError] = useState("");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState<{ kind: "success" | "error"; text: string } | null>(null);
  const [lexicon, setLexicon] = useState<AiFlavorLexicon | null>(null);
  const [lexiconLoading, setLexiconLoading] = useState(false);
  const [lexiconError, setLexiconError] = useState("");
  const [lexiconDirty, setLexiconDirty] = useState(false);
  const [expandedLexiconCategories, setExpandedLexiconCategories] = useState<Record<string, boolean>>({});
  const [newLexiconPhrase, setNewLexiconPhrase] = useState<Record<string, string>>({});

  useEffect(() => {
    if (tab !== "data") return;
    setStatsError("");
    api<Stats>("/api/v1/stats/overview")
      .then(setStats)
      .catch(caught => setStatsError(caught instanceof Error ? caught.message : String(caught)));
  }, [tab]);

  useEffect(() => {
    if (tab !== "quality") return;
    let cancelled = false;
    setLexiconLoading(true);
    setLexiconError("");
    api<AiFlavorLexicon>("/api/v1/quality/ai-flavor-lexicon")
      .then(result => {
        if (cancelled) return;
        setLexicon(result);
        setLexiconDirty(false);
      })
      .catch(caught => {
        if (!cancelled) setLexiconError(caught instanceof Error ? caught.message : String(caught));
      })
      .finally(() => {
        if (!cancelled) setLexiconLoading(false);
      });
    return () => { cancelled = true; };
  }, [tab]);

  function updateLexiconCategory(key: string, patch: Partial<LexiconCategory>) {
    setLexicon(current => current ? {
      ...current,
      categories: current.categories.map(category => category.key === key ? { ...category, ...patch } : category),
    } : current);
    setLexiconDirty(true);
  }

  function updateLexiconPhrase(categoryKey: string, phraseIndex: number, patch: Partial<LexiconPhrase>) {
    setLexicon(current => current ? {
      ...current,
      categories: current.categories.map(category => category.key !== categoryKey ? category : {
        ...category,
        phrases: category.phrases.map((phrase, index) => index === phraseIndex ? { ...phrase, ...patch } : phrase),
      }),
    } : current);
    setLexiconDirty(true);
  }

  function addLexiconPhrase(categoryKey: string) {
    const phrase = (newLexiconPhrase[categoryKey] || "").trim();
    if (!phrase) return;
    setLexicon(current => current ? {
      ...current,
      categories: current.categories.map(category => category.key !== categoryKey ? category : {
        ...category,
        phrases: [...category.phrases, { phrase, enabled: true, note: "自定义候选信号" }],
      }),
    } : current);
    setNewLexiconPhrase(current => ({ ...current, [categoryKey]: "" }));
    setLexiconDirty(true);
  }

  function removeLexiconPhrase(categoryKey: string, phraseIndex: number) {
    setLexicon(current => current ? {
      ...current,
      categories: current.categories.map(category => category.key !== categoryKey ? category : {
        ...category,
        phrases: category.phrases.filter((_, index) => index !== phraseIndex),
      }),
    } : current);
    setLexiconDirty(true);
  }

  async function saveLexicon() {
    if (!lexicon) return;
    setBusy("lexicon");
    setNotice(null);
    try {
      const saved = await api<AiFlavorLexicon>("/api/v1/quality/ai-flavor-lexicon", {
        method: "PUT",
        body: JSON.stringify({
          schema_version: lexicon.schema_version,
          version: lexicon.version,
          mode: "advisory",
          hard_gate: false,
          categories: lexicon.categories,
        }),
      });
      setLexicon(saved);
      setLexiconDirty(false);
      setNotice({ kind: "success", text: "AI 味词库已保存，后续生成与审阅会读取新配置。" });
    } catch (caught) {
      setNotice({ kind: "error", text: `词库保存失败：${caught instanceof Error ? caught.message : String(caught)}` });
    } finally {
      setBusy("");
    }
  }

  async function resetLexicon() {
    setBusy("lexicon-reset");
    setNotice(null);
    try {
      const restored = await api<AiFlavorLexicon>("/api/v1/quality/ai-flavor-lexicon/reset", { method: "POST" });
      setLexicon(restored);
      setLexiconDirty(false);
      setNotice({ kind: "success", text: "AI 味词库已恢复为内置版本。" });
    } catch (caught) {
      setNotice({ kind: "error", text: `恢复失败：${caught instanceof Error ? caught.message : String(caught)}` });
    } finally {
      setBusy("");
    }
  }

  function saveAiConfig() {
    setApiKey(apiKey.trim());
    setApiUrl(apiUrl.trim());
    setModel(model.trim());
    setConfigDirty(false);
    setNotice({ kind: "success", text: "AI 配置已保存在当前浏览器会话，后续创作请求会立即使用。" });
  }

  async function exportKnowledge() {
    if (!projectId) {
      setNotice({ kind: "error", text: "当前没有可导出的小说项目。" });
      return;
    }
    setBusy("export");
    setNotice(null);
    try {
      const rows = await api<unknown[]>(`/api/v1/knowledge?project_id=${encodeURIComponent(projectId)}`);
      const blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json;charset=utf-8" });
      const href = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = href;
      link.download = `starlume-knowledge-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      URL.revokeObjectURL(href);
      setNotice({ kind: "success", text: `已导出 ${rows.length} 条知识数据。` });
    } catch (caught) {
      setNotice({ kind: "error", text: `导出失败：${caught instanceof Error ? caught.message : String(caught)}` });
    } finally {
      setBusy("");
    }
  }

  async function importKnowledge(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !projectId) return;
    setBusy("import");
    setNotice(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api<{ imported?: number; count?: number }>(`/api/v1/knowledge/import?project_id=${encodeURIComponent(projectId)}`, { method: "POST", body: form });
      setNotice({ kind: "success", text: `知识数据导入完成：${result.imported ?? result.count ?? 0} 条。` });
    } catch (caught) {
      setNotice({ kind: "error", text: `导入失败：${caught instanceof Error ? caught.message : String(caught)}` });
    } finally {
      setBusy("");
    }
  }

  async function changePassword() {
    setBusy("password");
    setNotice(null);
    try {
      await api("/api/v1/auth/change-password", {
        method: "POST",
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      });
      setOldPassword("");
      setNewPassword("");
      setNotice({ kind: "success", text: "密码已修改，其他设备上的旧会话将失效。" });
    } catch (caught) {
      setNotice({ kind: "error", text: `修改失败：${caught instanceof Error ? caught.message : String(caught)}` });
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="novel-settings page-enter">
      <section className="settings-heading">
        <p className="eyebrow">NOVEL SETTINGS</p>
        <h2>小说设置</h2>
        <p>只保留与个人小说创作直接相关的连接、数据与账号设置。</p>
      </section>

      {!projectId && (
        <div className="settings-project-state" role="status">
          <Database size={17} />
          <span>当前还没有选中的项目。AI 连接、质量规则和词库仍可配置；创作数据导入导出会在项目加载后启用。</span>
        </div>
      )}

      {notice && <div className={`settings-notice ${notice.kind}`} role="status">{notice.kind === "success" ? <Check size={16} /> : <Lock size={16} />}{notice.text}</div>}

      <div className="settings-layout">
        <nav className="settings-nav" aria-label="小说设置分类">
          <button type="button" className={tab === "ai" ? "active" : ""} onClick={() => setTab("ai")}><KeyRound size={18} /><span>AI 连接</span></button>
          <button type="button" className={tab === "quality" ? "active" : ""} onClick={() => setTab("quality")}><SlidersHorizontal size={18} /><span>质量规则</span></button>
          <button type="button" className={tab === "data" ? "active" : ""} onClick={() => setTab("data")}><Database size={18} /><span>创作数据</span></button>
          <button type="button" className={tab === "account" ? "active" : ""} onClick={() => setTab("account")}><Lock size={18} /><span>账号安全</span></button>
        </nav>

        <main className="settings-content starlume-card">
          {tab === "ai" && (
            <section className="settings-section">
              <div><p className="eyebrow">BYOK</p><h3>AI 连接</h3><p>配置只保存在当前浏览器会话，并通过请求头交给后端；不会写进仓库或显示在页面其他位置。</p></div>
              <label className="settings-field">
                <span>Provider API Key</span>
                <div className="secret-field">
                  <input type={showKey ? "text" : "password"} autoComplete="off" placeholder="输入 DeepSeek / OpenAI / Claude / Gemini Key" value={apiKey} onChange={event => { setApiKeyValue(event.target.value); setConfigDirty(true); }} />
                  <button type="button" aria-label={showKey ? "隐藏 API Key" : "显示 API Key"} onClick={() => setShowKey(value => !value)}>{showKey ? <EyeOff size={17} /> : <Eye size={17} />}</button>
                </div>
              </label>
              <div className="settings-fields-row">
                <label className="settings-field"><span>API 地址</span><input placeholder="例如 https://api.deepseek.com/v1" value={apiUrl} onChange={event => { setApiUrlValue(event.target.value); setConfigDirty(true); }} /></label>
                <label className="settings-field"><span>模型</span><input placeholder="例如 deepseek-chat" value={model} onChange={event => { setModelValue(event.target.value); setConfigDirty(true); }} /></label>
              </div>
              <div className="settings-callout">
                <KeyRound size={18} />
                <div><strong>{apiKey ? "当前会话已配置个人 Key" : "当前会话未配置个人 Key"}</strong><p>未配置时会使用服务器全局 Provider；如果两处都未配置，创作向导会明确阻止启动。</p></div>
              </div>
              <button type="button" className="settings-save" disabled={!configDirty} onClick={saveAiConfig}><Save size={17} /> {configDirty ? "保存 AI 配置" : "配置已保存"}</button>
            </section>
          )}

          {tab === "quality" && (
            <section className="settings-section quality-section">
              <div>
                <p className="eyebrow">QUALITY RULES</p>
                <h3>AI 味词库</h3>
                <p>把审阅中反复出现的表达沉淀成可编辑的候选信号，服务生成前约束和生成后取证。</p>
              </div>

              {lexiconLoading && <div className="settings-data-loading"><span className="spinner" /> 正在读取词库配置…</div>}
              {lexiconError && <div className="settings-data-error">读取词库失败：{lexiconError}</div>}
              {lexicon && !lexiconLoading && (
                <>
                  <div className="lexicon-toolbar">
                    <div className="lexicon-summary">
                      <span><strong>{lexicon.enabled_phrase_count ?? 0}</strong> 个启用信号</span>
                      <span><strong>{lexicon.category_count ?? lexicon.categories.length}</strong> 个分类</span>
                      <span>v{lexicon.version} · {lexicon.source === "database" ? "已保存配置" : "内置默认"}</span>
                    </div>
                    <div className="lexicon-actions">
                      <button type="button" className="settings-secondary" disabled={!lexiconDirty || Boolean(busy)} onClick={() => void resetLexicon()}><RotateCcw size={16} /> 恢复内置</button>
                      <button type="button" className="settings-save" disabled={!lexiconDirty || busy === "lexicon"} onClick={() => void saveLexicon()}><Save size={16} /> {busy === "lexicon" ? "保存中…" : "保存词库"}</button>
                    </div>
                  </div>
                  <div className="settings-callout lexicon-callout">
                    <SlidersHorizontal size={18} />
                    <div><strong>候选信号，不是禁词表</strong><p>{lexicon.usage_note || "单个词、标点或题材正常术语不会单独触发门禁；只有密度、重复和语境共同成立时才进入复核。"}</p></div>
                  </div>
                  <div className="lexicon-category-list">
                    {lexicon.categories.map(category => {
                      const expanded = Boolean(expandedLexiconCategories[category.key]);
                      return (
                        <article className={`lexicon-category ${category.enabled ? "" : "is-disabled"}`} key={category.key}>
                          <div className="lexicon-category-head">
                            <label className="lexicon-enable"><input type="checkbox" checked={category.enabled} onChange={event => updateLexiconCategory(category.key, { enabled: event.target.checked })} /><span>启用</span></label>
                            <div className="lexicon-category-meta">
                              <input aria-label={`${category.label} 分类名称`} value={category.label} onChange={event => updateLexiconCategory(category.key, { label: event.target.value })} />
                              <small>{category.phrases.length} 条候选 · {category.description}</small>
                            </div>
                            <button type="button" className="icon-button" aria-label={expanded ? `收起${category.label}` : `展开${category.label}`} aria-expanded={expanded} onClick={() => setExpandedLexiconCategories(current => ({ ...current, [category.key]: !expanded }))}><ChevronDown size={18} className={expanded ? "is-rotated" : ""} /></button>
                          </div>
                          {expanded && (
                            <div className="lexicon-category-body">
                              <label className="settings-field"><span>分类说明</span><input value={category.description} onChange={event => updateLexiconCategory(category.key, { description: event.target.value })} /></label>
                              <div className="lexicon-phrases" aria-label={`${category.label} 词条`}>
                                {category.phrases.map((item, index) => (
                                  <div className="lexicon-phrase-row" key={`${category.key}-${index}-${item.phrase}`}>
                                    <label className="lexicon-phrase-enabled"><input type="checkbox" checked={item.enabled} onChange={event => updateLexiconPhrase(category.key, index, { enabled: event.target.checked })} /><span>用</span></label>
                                    <input aria-label={`编辑${category.label}词条`} value={item.phrase} onChange={event => updateLexiconPhrase(category.key, index, { phrase: event.target.value })} />
                                    <input aria-label={`编辑${item.phrase}说明`} placeholder="使用说明（可选）" value={item.note} onChange={event => updateLexiconPhrase(category.key, index, { note: event.target.value })} />
                                    <button type="button" className="icon-button danger" aria-label={`删除${item.phrase}`} onClick={() => removeLexiconPhrase(category.key, index)}><Trash2 size={16} /></button>
                                  </div>
                                ))}
                              </div>
                              <div className="lexicon-add-row">
                                <input aria-label={`为${category.label}添加词条`} placeholder="添加候选表达" value={newLexiconPhrase[category.key] || ""} onChange={event => setNewLexiconPhrase(current => ({ ...current, [category.key]: event.target.value }))} onKeyDown={event => { if (event.key === "Enter") addLexiconPhrase(category.key); }} />
                                <button type="button" className="settings-secondary" onClick={() => addLexiconPhrase(category.key)}><Plus size={16} /> 添加</button>
                              </div>
                            </div>
                          )}
                        </article>
                      );
                    })}
                  </div>
                </>
              )}
            </section>
          )}

          {tab === "data" && (
            <section className="settings-section">
              <div><p className="eyebrow">YOUR DATA</p><h3>创作数据</h3><p>导入与导出都使用当前真实项目，不会生成演示数据。</p></div>
              <div className="settings-stats">
                {statsError ? <div className="settings-data-error">{statsError}</div> : stats ? <>
                  <div><BarChart3 size={18} /><span>AI 调用</span><strong>{stats.ai_calls.toLocaleString("zh-CN")}</strong></div>
                  <div><Database size={18} /><span>内容条目</span><strong>{stats.contents.toLocaleString("zh-CN")}</strong></div>
                  <div><Database size={18} /><span>数据库</span><strong>{stats.db_size}</strong></div>
                </> : <div className="settings-data-loading"><span className="spinner" /> 正在读取真实统计…</div>}
              </div>
              <div className="data-actions">
                <label className={projectId ? "" : "disabled"}><Upload size={18} /><span><strong>导入知识数据</strong><small>支持 TXT、Markdown、JSON、PDF、DOCX</small></span><input type="file" accept=".txt,.md,.json,.jsonl,.pdf,.docx" disabled={!projectId || busy === "import"} onChange={event => void importKnowledge(event)} /></label>
                <button type="button" disabled={!projectId || Boolean(busy)} onClick={() => void exportKnowledge()}><Database size={18} /><span><strong>{busy === "export" ? "正在导出…" : "导出知识数据"}</strong><small>下载当前项目的 JSON 备份</small></span></button>
              </div>
            </section>
          )}

          {tab === "account" && (
            <section className="settings-section settings-account">
              <div><p className="eyebrow">SECURITY</p><h3>修改密码</h3><p>修改成功后，其他设备上的旧登录会话会失效。</p></div>
              <label className="settings-field"><span>当前密码</span><input type="password" autoComplete="current-password" value={oldPassword} onChange={event => setOldPassword(event.target.value)} /></label>
              <label className="settings-field"><span>新密码</span><input type="password" autoComplete="new-password" placeholder="至少 8 位" value={newPassword} onChange={event => setNewPassword(event.target.value)} /></label>
              <button type="button" className="settings-save" disabled={!oldPassword || newPassword.length < 8 || busy === "password"} onClick={() => void changePassword()}><Lock size={17} /> {busy === "password" ? "正在更新…" : "更新密码"}</button>
            </section>
          )}
        </main>
      </div>

      <footer className="settings-footer">
        <span className="settings-footer-brand">Starlume AI · 本地创作助手</span>
        <Badge data-testid="app-version-badge" className="badge gray">v{appVersion}</Badge>
      </footer>
    </div>
  );
}
