import { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ClipboardCheck, FileCheck2, Loader2, Plus, RefreshCw, Send, Sparkles, X } from "lucide-react";
import { api } from "../lib/api";

type Chapter = {
  id: string;
  title?: string;
  body?: unknown;
  meta?: Record<string, unknown>;
  status?: string;
};

type Profile = {
  id: string;
  platform: string;
  profile_name: string;
  policy_status: string;
  policy_version?: string;
  ai_usage_policy: string;
};

type Variant = {
  id?: string;
  variant_id?: string;
  novel_id: string;
  platform: string;
  variant_name: string;
  platform_profile_id?: string | null;
  title?: string;
  synopsis?: string;
  tags?: string[] | string;
  category?: string;
  publication_status: string;
  ai_disclosure_status: string;
  ai_disclosure_text?: string;
  gate_summary?: { blocking_failures?: string[]; gate_scores?: Record<string, { passed: boolean; score?: number }> };
};

type Readiness = {
  publication_status: string;
  publish_ready: boolean;
  blocking_failures: string[];
  ai_disclosure_status: string;
  platform_policy_confirmed: boolean;
  external_ai_flagged: boolean;
  external_ai_score?: number | null;
  gate_summary?: Variant["gate_summary"];
};

type Disclosure = {
  disclosure_id: string;
  disclosure_status?: string;
  status?: string;
  disclosure_text?: string;
};

type Props = {
  projectId?: string;
  novelId?: string;
  novelTitle?: string;
  chapters: Chapter[];
};

const GATE_LABELS: Record<string, string> = {
  content_quality: "内容质量",
  continuity: "连续性",
  payoff_density: "语义爽点",
  readability: "可读性",
  platform_compliance: "平台合规",
  ai_disclosure: "AI披露",
  external_risk: "外部风险",
};

const STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  quality_candidate: "质量候选",
  publish_ready: "可发布",
  published: "已发布",
  rejected: "已拒绝",
  pending: "待生成",
  generated: "待确认",
  confirmed: "已确认",
  not_required: "无需披露",
};

function textValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(textValue).filter(Boolean).join("\n\n");
  if (!value || typeof value !== "object") return "";
  const item = value as { text?: unknown; content?: unknown; body?: unknown; paragraphs?: unknown };
  if (item.text !== undefined) return textValue(item.text);
  if (item.content !== undefined) return textValue(item.content);
  if (item.paragraphs !== undefined) return textValue(item.paragraphs);
  if (item.body !== undefined) return textValue(item.body);
  return "";
}

function variantId(variant: Variant): string {
  return String(variant.id || variant.variant_id || "");
}

function tagsValue(tags: Variant["tags"]): string {
  if (Array.isArray(tags)) return tags.join(", ");
  return tags || "";
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "请求失败，请查看服务端错误记录";
}

export function PublishingPreparation({ projectId, novelId, novelTitle, chapters }: Props) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [variants, setVariants] = useState<Variant[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [disclosure, setDisclosure] = useState<Disclosure | null>(null);
  const [selectedChapterId, setSelectedChapterId] = useState(chapters[0]?.id || "");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [platform, setPlatform] = useState("fanqie");
  const [profileName, setProfileName] = useState("");
  const [policyStatus, setPolicyStatus] = useState("unknown");
  const [policyVersion, setPolicyVersion] = useState("");
  const [aiUsagePolicy, setAiUsagePolicy] = useState("required_disclosure");
  const [variantName, setVariantName] = useState("");
  const [title, setTitle] = useState(novelTitle || "");
  const [synopsis, setSynopsis] = useState("");
  const [tags, setTags] = useState("");
  const [category, setCategory] = useState("");

  const selectedVariant = useMemo(
    () => variants.find(item => variantId(item) === selectedId) || null,
    [selectedId, variants],
  );
  const selectedChapter = chapters.find(item => item.id === selectedChapterId) || chapters[0];

  const loadProfiles = useCallback(async () => {
    if (!projectId) return;
    const result = await api<{ profiles: Profile[] }>(`/api/v1/publishing/platform-profiles?project_id=${encodeURIComponent(projectId)}`);
    setProfiles(result.profiles || []);
  }, [projectId]);

  const loadVariants = useCallback(async () => {
    if (!novelId) return;
    const result = await api<{ variants: Variant[] }>(`/api/v1/publishing/variants/novel/${novelId}`);
    const next = result.variants || [];
    setVariants(next);
    setSelectedId(current => current && next.some(item => variantId(item) === current) ? current : variantId(next[0] || {}));
  }, [novelId]);

  const loadSelected = useCallback(async (id: string) => {
    if (!id) {
      setReadiness(null);
      setDisclosure(null);
      return;
    }
    const [ready, latest] = await Promise.all([
      api<Readiness>(`/api/v1/publishing/variants/${id}/publish-readiness`),
      api<Disclosure>(`/api/v1/publishing/disclosures/variant/${id}`),
    ]);
    setReadiness(ready);
    setDisclosure(latest?.disclosure_id ? latest : null);
  }, []);

  const refresh = useCallback(async () => {
    if (!projectId || !novelId) return;
    setBusy("refresh");
    setError("");
    try {
      await Promise.all([loadProfiles(), loadVariants()]);
      if (selectedId) await loadSelected(selectedId);
      setNotice("发布准备数据已刷新");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy("");
    }
  }, [loadProfiles, loadSelected, loadVariants, novelId, projectId, selectedId]);

  useEffect(() => {
    setSelectedChapterId(chapters[0]?.id || "");
  }, [chapters]);

  useEffect(() => {
    if (!projectId || !novelId) return;
    setError("");
    void Promise.all([loadProfiles(), loadVariants()]).catch(err => setError(errorMessage(err)));
  }, [loadProfiles, loadVariants, novelId, projectId]);

  useEffect(() => {
    if (selectedVariant) {
      setPlatform(selectedVariant.platform);
      setVariantName(selectedVariant.variant_name);
      setTitle(selectedVariant.title || novelTitle || "");
      setSynopsis(selectedVariant.synopsis || "");
      setTags(tagsValue(selectedVariant.tags));
      setCategory(selectedVariant.category || "");
    }
    void loadSelected(selectedId).catch(err => setError(errorMessage(err)));
  }, [loadSelected, novelTitle, selectedId, selectedVariant]);

  async function createProfile() {
    if (!projectId || !platform.trim() || !profileName.trim()) return;
    setBusy("profile"); setError(""); setNotice("");
    try {
      await api(`/api/v1/publishing/platform-profiles`, {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, platform, profile_name: profileName, policy_status: policyStatus, policy_version: policyVersion, ai_usage_policy: aiUsagePolicy }),
      });
      setProfileName("");
      await loadProfiles();
      setNotice("平台配置已保存；规则状态仍需按真实平台资料确认");
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }

  async function createVariant() {
    if (!novelId || !variantName.trim()) return;
    const profile = profiles.find(item => item.platform === platform);
    setBusy("variant"); setError(""); setNotice("");
    try {
      const result = await api<{ variant_id: string }>(`/api/v1/publishing/variants`, {
        method: "POST",
        body: JSON.stringify({ novel_id: novelId, platform, variant_name: variantName, platform_profile_id: profile?.id || null, metadata: { title: title || novelTitle || "", synopsis, tags: tags.split(/[,，]/).map(item => item.trim()).filter(Boolean), category } }),
      });
      await loadVariants();
      setSelectedId(result.variant_id);
      setNotice("发布变体已创建；请先完成门禁与披露确认");
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }

  async function runGates() {
    if (!projectId || !selectedVariant || !selectedChapter) return;
    setBusy("gates"); setError(""); setNotice("");
    try {
      await api(`/api/v1/publishing/gates/run`, {
        method: "POST",
        body: JSON.stringify({
          chapter_id: selectedChapter.id,
          text: textValue(selectedChapter.body),
          variant_id: variantId(selectedVariant),
          project_id: projectId,
          platform: selectedVariant.platform,
          metadata: { title: selectedVariant.title || title, synopsis: selectedVariant.synopsis || synopsis, tags: selectedVariant.tags || [], category: selectedVariant.category || category },
        }),
      });
      await Promise.all([loadVariants(), loadSelected(variantId(selectedVariant))]);
      setNotice("门禁已运行；语义爽点评估使用真实 Provider，失败不会伪装成通过");
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }

  async function generateDisclosure() {
    if (!selectedVariant) return;
    setBusy("disclosure"); setError(""); setNotice("");
    try {
      const result = await api<Disclosure>(`/api/v1/publishing/disclosures/generate`, {
        method: "POST",
        body: JSON.stringify({ variant_id: variantId(selectedVariant), chapter_id: selectedChapter?.id || null }),
      });
      setDisclosure(result);
      await loadVariants();
      await loadSelected(variantId(selectedVariant));
      setNotice("AI披露草稿已生成，必须人工确认后才会解除披露门禁");
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }

  async function confirmDisclosure() {
    if (!disclosure?.disclosure_id) return;
    setBusy("confirm"); setError(""); setNotice("");
    try {
      await api(`/api/v1/publishing/disclosures/${disclosure.disclosure_id}/confirm`, { method: "POST", body: JSON.stringify({}) });
      await Promise.all([loadVariants(), loadSelected(variantId(selectedVariant!))]);
      setNotice("AI披露已人工确认");
    } catch (err) { setError(errorMessage(err)); }
    finally { setBusy(""); }
  }

  if (!projectId || !novelId) {
    return <div className="publishing-empty panel"><Send size={24} /><h2>先选择项目与小说</h2><p>发布准备页需要明确的项目和作品范围，避免把门禁结果写入错误作品。</p></div>;
  }

  const gateScores = readiness?.gate_summary?.gate_scores || selectedVariant?.gate_summary?.gate_scores || {};
  const blockingFailures = readiness?.blocking_failures || selectedVariant?.gate_summary?.blocking_failures || [];
  const profileForPlatform = profiles.find(item => item.platform === (selectedVariant?.platform || platform));

  return (
    <main className="publishing-page page-enter">
      <div className="page-head">
        <div>
          <div className="eyebrow"><Send size={14} /> RELEASE CONTROL</div>
          <h1>发布准备</h1>
          <p>{novelTitle || "当前作品"} · 七道门禁、平台规则、AI披露与真实 Provider 证据</p>
        </div>
        <div className="head-actions">
          <button className="btn-ghost btn-sm" onClick={() => void refresh()} disabled={Boolean(busy)}><RefreshCw size={14} />刷新</button>
        </div>
      </div>

      {error && <div className="error publishing-alert"><X size={16} />{error}</div>}
      {notice && <div className="publishing-notice"><Check size={16} />{notice}</div>}

      <div className="publishing-layout">
        <section className="card publishing-main-card">
          <div className="card-head"><div><div className="card-title"><ClipboardCheck size={17} />发布变体</div><div className="card-sub">一个基础作品可以对应多个平台版本</div></div><span className="badge cyan">{variants.length} 个变体</span></div>
          {variants.length > 0 ? <div className="publishing-variant-list">{variants.map(item => {
            const id = variantId(item);
            return <button key={id} className={`publishing-variant${id === selectedId ? " selected" : ""}`} onClick={() => setSelectedId(id)}>
              <span><strong>{item.variant_name}</strong><small>{item.platform} · {STATUS_LABELS[item.publication_status] || item.publication_status}</small></span>
              <span className={`badge ${item.ai_disclosure_status === "confirmed" ? "green" : "orange"}`}>{STATUS_LABELS[item.ai_disclosure_status] || item.ai_disclosure_status}</span>
            </button>;
          })}</div> : <p className="muted">还没有发布变体，先在下方创建一个。</p>}

          <div className="publishing-section-divider" />
          <div className="card-head"><div><div className="card-title"><Plus size={17} />创建发布变体</div><div className="card-sub">平台规则状态为 stale/unknown 时，系统会继续阻断发布</div></div></div>
          <div className="publishing-form-grid">
            <label className="field"><span className="form-label">平台</span><input className="form-input" value={platform} onChange={event => setPlatform(event.target.value)} placeholder="fanqie" /></label>
            <label className="field"><span className="form-label">变体名称</span><input className="form-input" value={variantName} onChange={event => setVariantName(event.target.value)} placeholder="番茄首发版" /></label>
            <label className="field publishing-field-wide"><span className="form-label">发布标题</span><input className="form-input" value={title} onChange={event => setTitle(event.target.value)} /></label>
            <label className="field publishing-field-wide"><span className="form-label">简介</span><textarea className="form-input" value={synopsis} onChange={event => setSynopsis(event.target.value)} placeholder="平台展示简介" /></label>
            <label className="field"><span className="form-label">标签</span><input className="form-input" value={tags} onChange={event => setTags(event.target.value)} placeholder="重生，逆袭" /></label>
            <label className="field"><span className="form-label">分类</span><input className="form-input" value={category} onChange={event => setCategory(event.target.value)} placeholder="都市" /></label>
          </div>
          <button className="btn-primary" onClick={() => void createVariant()} disabled={busy === "variant" || !variantName.trim()}>{busy === "variant" ? <Loader2 className="spin" size={15} /> : <Plus size={15} />}创建变体</button>

          <div className="publishing-section-divider" />
          <div className="card-head"><div><div className="card-title"><FileCheck2 size={17} />平台规则配置</div><div className="card-sub">当前平台：{profileForPlatform?.profile_name || "未配置"}</div></div></div>
          <div className="publishing-form-grid">
            <label className="field"><span className="form-label">配置名称</span><input className="form-input" value={profileName} onChange={event => setProfileName(event.target.value)} placeholder="番茄小说-2026" /></label>
            <label className="field"><span className="form-label">规则状态</span><select className="form-input" value={policyStatus} onChange={event => setPolicyStatus(event.target.value)}><option value="unknown">unknown</option><option value="stale">stale</option><option value="confirmed">confirmed</option></select></label>
            <label className="field"><span className="form-label">规则版本</span><input className="form-input" value={policyVersion} onChange={event => setPolicyVersion(event.target.value)} placeholder="人工核实后填写" /></label>
            <label className="field"><span className="form-label">AI政策</span><select className="form-input" value={aiUsagePolicy} onChange={event => setAiUsagePolicy(event.target.value)}><option value="allowed">allowed</option><option value="allowed_with_human_editing">allowed_with_human_editing</option><option value="required_disclosure">required_disclosure</option><option value="prohibited">prohibited</option></select></label>
          </div>
          <button className="btn-ghost" onClick={() => void createProfile()} disabled={busy === "profile" || !profileName.trim()}>{busy === "profile" ? <Loader2 className="spin" size={15} /> : <Plus size={15} />}保存平台配置</button>
        </section>

        <aside className="publishing-side">
          <section className="card">
            <div className="card-head"><div><div className="card-title"><Sparkles size={17} />就绪状态</div><div className="card-sub">{selectedVariant ? selectedVariant.variant_name : "尚未选择变体"}</div></div>{selectedVariant && <span className={`badge ${readiness?.publish_ready ? "green" : "orange"}`}>{readiness?.publish_ready ? "可发布" : STATUS_LABELS[selectedVariant.publication_status] || "需处理"}</span>}</div>
            {!selectedVariant ? <p className="muted">选择或创建一个变体后查看门禁。</p> : <>
              <div className="publishing-readiness-list">{Object.keys(GATE_LABELS).map(key => {
                const gate = gateScores[key];
                const failed = blockingFailures.includes(key) || (gate && !gate.passed);
                return <div key={key} className="publishing-readiness-row"><span>{failed ? <X size={15} /> : gate?.passed ? <Check size={15} /> : <span className="dot" />}{GATE_LABELS[key]}</span><small>{gate ? `${gate.passed ? "通过" : "未通过"}${gate.score != null ? ` · ${gate.score}` : ""}` : "未运行"}</small></div>;
              })}</div>
              <div className="publishing-meta-line">平台规则：{readiness?.platform_policy_confirmed ? "已确认" : "未确认"} · AI披露：{STATUS_LABELS[readiness?.ai_disclosure_status || "pending"] || readiness?.ai_disclosure_status || "待生成"}</div>
              <button className="btn-primary publishing-full-button" onClick={() => void runGates()} disabled={busy === "gates" || !selectedChapter}>{busy === "gates" ? <Loader2 className="spin" size={15} /> : <ClipboardCheck size={15} />}运行七道门禁</button>
            </>}
          </section>

          <section className="card">
            <div className="card-head"><div><div className="card-title"><FileCheck2 size={17} />AI披露</div><div className="card-sub">Provider草稿不会自动确认</div></div></div>
            <p className="publishing-disclosure-text">{disclosure?.disclosure_text || selectedVariant?.ai_disclosure_text || "尚未生成披露文案"}</p>
            <div className="row-actions">
              <button className="btn-ghost btn-sm" onClick={() => void generateDisclosure()} disabled={!selectedVariant || Boolean(busy)}><Sparkles size={14} />生成草稿</button>
              <button className="btn-primary btn-sm" onClick={() => void confirmDisclosure()} disabled={!disclosure?.disclosure_id || (disclosure.status || disclosure.disclosure_status) === "confirmed" || Boolean(busy)}><Check size={14} />人工确认</button>
            </div>
          </section>

          <section className="card">
            <div className="card-head"><div><div className="card-title">本次门禁章节</div><div className="card-sub">语义评估将读取所选章节正文</div></div></div>
            <select className="form-input" value={selectedChapter?.id || ""} onChange={event => setSelectedChapterId(event.target.value)} disabled={!chapters.length}>
              {chapters.length ? chapters.map(item => <option key={item.id} value={item.id}>{item.title || `第${String(item.meta?.seq || "")}章`}</option>) : <option value="">暂无章节</option>}
            </select>
            <p className="muted publishing-chapter-note">{selectedChapter ? `${textValue(selectedChapter.body).length} 字` : "请先回到编辑器生成章节正文"}</p>
          </section>
        </aside>
      </div>
    </main>
  );
}

export default PublishingPreparation;
