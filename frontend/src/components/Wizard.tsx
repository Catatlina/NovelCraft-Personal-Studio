import { useEffect, useRef, useState } from "react";
import { AlertTriangle, ArrowRight, BookOpen, Copy, Feather, FileUp, Link2, Loader2, Sparkles, Wand2 } from "lucide-react";
import { api, apiRaw, getApiKey } from "../lib/api";

const GENRES = ["都市", "科幻", "玄幻", "仙侠", "悬疑", "历史", "游戏", "轻小说", "短篇", "其他"];
const SUBGENRES: Record<string, string[]> = {
  都市: ["都市神豪", "都市商战", "都市重生", "都市异能", "都市高武", "都市脑洞", "都市系统"],
  玄幻: ["传统升级流", "凡人流", "苟道流", "系统流", "长生流", "史诗玄幻", "宿命流", "设定流", "家族修仙"],
  仙侠: ["传统升级流", "凡人流", "苟道流", "系统流", "长生流", "史诗玄幻", "宿命流", "设定流", "家族修仙"],
};
const WORD_PRESETS = [
  { value: 100000, label: "短篇", hint: "约 10 万字" },
  { value: 300000, label: "中篇", hint: "约 30 万字" },
  { value: 800000, label: "长篇", hint: "约 80 万字" },
  { value: 1500000, label: "超长篇", hint: "约 150 万字" },
];

const CUSTOM_STYLE_VALUE = "__custom__";
const STYLE_PRESETS = [
  { value: "第三人称、克制、悬疑、强画面感", label: "悬疑压迫 · 强画面", hint: "线索递进，信息留白，章末留钩" },
  { value: "第三人称、冲突前置、节奏明快、爽点密集、少解释", label: "网文爽感 · 快节奏", hint: "开局见冲突，行动推动情节" },
  { value: "第三人称、对白自然、细节具体、冲突递进、少空泛评价", label: "都市现实 · 自然对白", hint: "用具体行动和对白承载信息" },
  { value: "第三人称、升级目标清晰、战斗推进有代价、爽点密集、少空泛感叹", label: "玄幻升级 · 强推进", hint: "目标、阻碍、收益和代价清楚" },
  { value: "第三人称、谨慎决策、资源账本清晰、反差爽点、节奏张弛", label: "凡人苟道 · 慢热反差", hint: "谨慎积累，关键处爆发" },
  { value: "第三人称、人物行动驱动情绪、对白自然、少总结、重视关系变化", label: "情感成长 · 强代入", hint: "情绪落在选择和后果上" },
];

export function Wizard({
  idea,
  setIdea,
  genre,
  setGenre,
  platform,
  setPlatform,
  subgenre,
  setSubgenre,
  stylePlugin,
  setStylePlugin,
  style,
  setStyle,
  targetWords,
  setTargetWords,
  busy,
  startBootstrap,
  projectId,
}: {
  idea: string;
  setIdea: (value: string) => void;
  genre: string;
  setGenre: (value: string) => void;
  platform: string;
  setPlatform: (value: string) => void;
  subgenre: string;
  setSubgenre: (value: string) => void;
  stylePlugin: string;
  setStylePlugin: (value: string) => void;
  style: string;
  setStyle: (value: string) => void;
  targetWords: number;
  setTargetWords: (value: number) => void;
  busy: boolean;
  startBootstrap: () => void;
  projectId?: string;
}) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [keyMissing, setKeyMissing] = useState(false);
  // 仿写/润色状态
  const [imitText, setImitText] = useState("");
  const [imitUrl, setImitUrl] = useState("");
  const [imitInstruction, setImitInstruction] = useState("");
  const [imitFileName, setImitFileName] = useState("");
  const [imitBusy, setImitBusy] = useState<"" | "imitate" | "polish">("");
  const [imitError, setImitError] = useState("");
  const [imitResult, setImitResult] = useState<{
    mode: "imitate" | "polish";
    text: string;
    similarity?: { verdict?: string; max_similarity?: number };
    copyright_warning?: string;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const subgenreOptions = SUBGENRES[genre] || [];
  const longLifeEligible = ["凡人流", "苟道流", "系统流", "长生流"].includes(subgenre);
  const [customStyleMode, setCustomStyleMode] = useState(() => Boolean(style.trim() && !STYLE_PRESETS.some(item => item.value === style)));
  const selectedStylePreset = customStyleMode
    ? CUSTOM_STYLE_VALUE
    : (STYLE_PRESETS.some(item => item.value === style) ? style : STYLE_PRESETS[0].value);

  function handleImitFile(file: File | undefined) {
    if (!file) return;
    const name = file.name.toLowerCase();
    if (!/\.(txt|md|json)$/.test(name)) {
      setImitError("暂只支持 .txt / .md / .json 文件；docx/pdf 请将内容粘贴到文本框。");
      return;
    }
    if (file.size > 2 * 1024 * 1024) {
      setImitError("文件过大（上限 2MB），请截取需要的片段。");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const raw = String(reader.result || "");
      setImitText(raw.slice(0, 20000));
      setImitFileName(file.name + (raw.length > 20000 ? "（已截取前 2 万字）" : ""));
      setImitError("");
    };
    reader.onerror = () => setImitError("文件读取失败，请重试或改用粘贴文本。");
    reader.readAsText(file);
  }

  async function runImitation(mode: "imitate" | "polish") {
    setImitError("");
    setImitResult(null);
    if (!projectId) { setImitError("项目尚未加载完成，请稍后再试。"); return; }
    const text = imitText.trim();
    const url = imitUrl.trim();
    if (!text && !url) { setImitError("请先粘贴文本、上传文档或填写链接。"); return; }
    if (text && text.length < (mode === "imitate" ? 200 : 50)) {
      setImitError(mode === "imitate" ? "仿写需要至少 200 字的原文素材。" : "润色需要至少 50 字的文本。");
      return;
    }
    if (url && !/^https:\/\//.test(url)) { setImitError("链接必须以 https:// 开头。"); return; }
    setImitBusy(mode);
    try {
      const payload: Record<string, string> = { project_id: projectId, source_text: text, source_url: text ? "" : url };
      if (mode === "imitate" && imitInstruction.trim()) payload.instruction = imitInstruction.trim();
      const data = await api<{ text?: string; sample?: string; similarity?: { verdict?: string; max_similarity?: number }; copyright_warning?: string }>(
        mode === "imitate" ? "/api/v1/imitation" : "/api/v1/imitation/polish",
        { method: "POST", body: JSON.stringify(payload) },
      );
      const outText = String(data?.text || (data as any)?.sample || "").trim();
      if (!outText) throw new Error("AI 未返回有效文本");
      setImitResult({ mode, text: outText, similarity: data?.similarity, copyright_warning: data?.copyright_warning });
    } catch (error: any) {
      const detail = error?.payload?.detail ?? error?.payload?.message ?? error?.message ?? String(error);
      const detailText = typeof detail === "object" ? (detail.code === "IMITATION_SIMILARITY_BLOCKED" ? `与原文相似度过高（${Math.round((detail.max_similarity || 0) * 100)}%），已按版权红线拦截，请调整仿写指令后重试。` : JSON.stringify(detail)) : String(detail);
      setImitError(`${mode === "imitate" ? "仿写" : "润色"}失败：${detailText}`);
    } finally {
      setImitBusy("");
    }
  }

  useEffect(() => {
    if (getApiKey()) {
      setKeyMissing(false);
      return;
    }
    apiRaw<{ data?: { ai_key_configured?: boolean } }>("/api/v1/healthz")
      .then(health => setKeyMissing(!health?.data?.ai_key_configured))
      .catch(() => setKeyMissing(false));
  }, []);

  function clearError(field: string) {
    if (errors[field]) setErrors(current => ({ ...current, [field]: "" }));
  }

  function validate() {
    const nextErrors: Record<string, string> = {};
    if (idea.trim().length < 4) nextErrors.idea = "请至少用 4 个字描述你的故事";
    if (!genre.trim()) nextErrors.genre = "请选择小说题材";
    if (customStyleMode && !style.trim()) nextErrors.style = "请填写自定义写作风格，或改选一个预设";
    if (targetWords < 10000) nextErrors.targetWords = "目标字数不能少于 10,000";
    if (targetWords > 3000000) nextErrors.targetWords = "目标字数不能超过 300 万";
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) startBootstrap();
  }

  return (
    <div className="wizard-page page-enter">
      <section className="wizard-heading">
        <p className="eyebrow">CREATE A NOVEL</p>
        <h2>把一个念头，变成完整故事。</h2>
        <p>你负责给出方向，Starlume 会依次完成定位、世界观、人物、情节蓝图和首章草稿。书名生成后仍由你最终确认。</p>
      </section>

      {keyMissing && (
        <div className="wizard-alert" role="alert">
          <span><AlertTriangle size={18} /></span>
          <div>
            <strong>开始前需要配置 AI</strong>
            <p>当前账号和服务器都没有可用的 AI API Key。请先在「小说设置」中完成配置，否则流程会明确失败。</p>
          </div>
        </div>
      )}

      <div className="wizard-layout">
        <form className="wizard-form starlume-card" onSubmit={event => { event.preventDefault(); validate(); }}>
          <div className="wizard-step">
            <span>01</span>
            <div>
              <h3>故事灵感</h3>
              <p>不必完整，只要说清人物、变化或最想写的冲突。</p>
            </div>
          </div>
          <label className="wizard-field">
            <span>用几句话描述你的故事</span>
            <textarea
              value={idea}
              onChange={event => { setIdea(event.target.value); clearError("idea"); }}
              rows={6}
              maxLength={3000}
              placeholder="例如：一个写作者发现，自己删掉的章节正在现实里发生……"
              aria-invalid={Boolean(errors.idea)}
            />
            <small className={errors.idea ? "field-error" : ""}>{errors.idea || `${idea.length} / 3000`}</small>
          </label>

          <div className="wizard-divider" />
          <div className="wizard-step">
            <span>02</span>
            <div>
              <h3>作品气质</h3>
              <p>这些选择会成为后续所有 AI 节点共同遵守的创作边界。</p>
            </div>
          </div>
          <div className="wizard-fields-grid">
            <label className="wizard-field">
              <span>小说题材</span>
              <select
                value={genre}
                onChange={event => { setGenre(event.target.value); setSubgenre(""); setStylePlugin(""); clearError("genre"); }}
                aria-invalid={Boolean(errors.genre)}
              >
                <option value="">选择题材</option>
                {GENRES.map(item => <option key={item} value={item}>{item}</option>)}
              </select>
              {errors.genre && <small className="field-error">{errors.genre}</small>}
            </label>
            <label className="wizard-field">
              <span>目标平台</span>
              <select value={platform} onChange={event => setPlatform(event.target.value)} aria-label="目标平台">
                <option value="fanqie">番茄小说（高留存）</option>
                <option value="qidian">起点中文网（长线）</option>
              </select>
            </label>
            <label className="wizard-field">
              <span>细分流派 <small>可选</small></span>
              <select value={subgenre} onChange={event => {
                const next = event.target.value;
                setSubgenre(next);
                if (!["凡人流", "苟道流", "系统流", "长生流"].includes(next)) setStylePlugin("");
              }} aria-label="细分流派">
                <option value="">自动匹配</option>
                {subgenreOptions.map(item => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            {(genre === "玄幻" || genre === "仙侠") && (
              <label className="wizard-field">
                <span>风格插件 <small>可选</small></span>
                <select value={stylePlugin} onChange={event => setStylePlugin(event.target.value)} aria-label="玄幻仙侠风格插件">
                  <option value="">不叠加专用插件</option>
                  <option value="xuanhuan_longlife" disabled={!longLifeEligible}>长生苟道（反差 / 种田 / 系统内化）</option>
                </select>
                <small>{longLifeEligible ? "只调整节奏、反差和系统呈现，不覆盖事实与世界规则。" : "先选择凡人流、苟道流、系统流或长生流，才可启用此插件。"}</small>
              </label>
            )}
            <label className="wizard-field">
              <span>写作风格 <small>生成前约束</small></span>
              <select
                value={selectedStylePreset}
                onChange={event => {
                  const next = event.target.value;
                  if (next === CUSTOM_STYLE_VALUE) {
                    setCustomStyleMode(true);
                    setStyle("");
                  } else {
                    setCustomStyleMode(false);
                    setStyle(next);
                  }
                  clearError("style");
                }}
                aria-label="写作风格预设"
              >
                {STYLE_PRESETS.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}
                <option value={CUSTOM_STYLE_VALUE}>自定义风格（高级）</option>
              </select>
              {customStyleMode ? (
                <input
                  value={style}
                  onChange={event => { setStyle(event.target.value); clearError("style"); }}
                  placeholder="例如：冷峻、短句、少比喻、强冲突"
                  maxLength={300}
                  aria-label="自定义写作风格"
                  aria-invalid={Boolean(errors.style)}
                />
              ) : (
                <small>{STYLE_PRESETS.find(item => item.value === selectedStylePreset)?.hint || "会写入生成约束，影响节奏、对白和叙述表达。"}</small>
              )}
              {errors.style && <small className="field-error">{errors.style}</small>}
            </label>
          </div>

          <div className="wizard-divider" />
          <div className="wizard-step">
            <span>03</span>
            <div>
              <h3>创作规模</h3>
              <p>目标字数只用于规划篇幅，不会一次生成整本小说。</p>
            </div>
          </div>
          <div className="word-presets">
            {WORD_PRESETS.map(preset => (
              <button
                type="button"
                key={preset.value}
                className={targetWords === preset.value ? "active" : ""}
                onClick={() => { setTargetWords(preset.value); clearError("targetWords"); }}
              >
                <strong>{preset.label}</strong><span>{preset.hint}</span>
              </button>
            ))}
          </div>
          <label className="wizard-field custom-words">
            <span>自定义目标字数</span>
            <input
              type="number"
              value={targetWords}
              min={10000}
              max={3000000}
              step={10000}
              onChange={event => { setTargetWords(Number(event.target.value)); clearError("targetWords"); }}
              aria-invalid={Boolean(errors.targetWords)}
            />
            {errors.targetWords && <small className="field-error">{errors.targetWords}</small>}
          </label>

          <button type="submit" className="wizard-submit" disabled={busy || keyMissing}>
            {busy ? <><Loader2 className="spin" size={18} /> 正在创建并启动…</> : <><Sparkles size={18} /> 开始生成小说 <ArrowRight size={17} /></>}
          </button>
          <p className="wizard-submit-note">启动后可离开页面，进度会持续保存；书名确认前不会继续后续创作。</p>
        </form>

        <aside className="wizard-aside">
          <div className="wizard-preview starlume-card">
            <span className="preview-icon"><BookOpen size={22} /></span>
            <p className="eyebrow">本次创作</p>
            <h3>{genre || "待选择题材"} · {(targetWords || 0).toLocaleString("zh-CN")} 字</h3>
            <p>{idea.trim() || "你的故事灵感会在这里形成第一份创作摘要。"}</p>
            <div><Feather size={15} /><span>{style || "待设置写作风格"}</span></div>
          </div>
          <div className="wizard-promise">
            <strong>你始终拥有最终决定权</strong>
            <p>AI 先产出候选方案，关键节点需要你确认。失败会明确展示并允许重试，不会用占位内容冒充结果。</p>
          </div>
        </aside>
      </div>

      <section className="wizard-form starlume-card" style={{ marginTop: 24 }}>
        <div className="wizard-step">
          <span><Wand2 size={18} /></span>
          <div>
            <h3>仿写工坊（可选）</h3>
            <p>粘贴一段范文、上传文档或给出链接，一键仿写其文风，或直接润色这段文字。仿写只学习文风，不复制内容，高相似输出会被版权红线拦截。</p>
          </div>
        </div>

        <label className="wizard-field">
          <span>范文 / 待润色文本</span>
          <textarea
            value={imitText}
            onChange={event => { setImitText(event.target.value); setImitFileName(""); }}
            rows={6}
            maxLength={20000}
            placeholder="粘贴 200 字以上的范文用于仿写，或 50 字以上的文本用于润色……"
          />
          <small>{imitFileName ? `已读取：${imitFileName}` : `${imitText.length} / 20000`}</small>
        </label>

        <div className="wizard-fields-grid">
          <label className="wizard-field">
            <span><Link2 size={13} style={{ verticalAlign: "-2px" }} /> 或者填写文章链接（HTTPS）</span>
            <input
              value={imitUrl}
              onChange={event => setImitUrl(event.target.value)}
              placeholder="https://…（填写文本后优先使用文本）"
              maxLength={1000}
            />
          </label>
          <label className="wizard-field">
            <span><FileUp size={13} style={{ verticalAlign: "-2px" }} /> 或者上传文档（.txt / .md / .json）</span>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.json,text/plain,text/markdown,application/json"
              onChange={event => { handleImitFile(event.target.files?.[0]); if (fileInputRef.current) fileInputRef.current.value = ""; }}
            />
          </label>
        </div>

        <label className="wizard-field">
          <span>仿写指令（可选）</span>
          <input
            value={imitInstruction}
            onChange={event => setImitInstruction(event.target.value)}
            placeholder="例如：用这个文风写一段都市悬疑的开头，主角是外卖骑手"
            maxLength={1000}
          />
        </label>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <button
            type="button"
            className="wizard-submit"
            style={{ flex: 1, minWidth: 180 }}
            disabled={!!imitBusy || keyMissing || !projectId}
            onClick={() => void runImitation("imitate")}
          >
            {imitBusy === "imitate" ? <><Loader2 className="spin" size={18} /> 正在仿写…</> : <><Sparkles size={18} /> 一键仿写</>}
          </button>
          <button
            type="button"
            className="wizard-submit"
            style={{ flex: 1, minWidth: 180, opacity: 0.92 }}
            disabled={!!imitBusy || keyMissing || !projectId}
            onClick={() => void runImitation("polish")}
          >
            {imitBusy === "polish" ? <><Loader2 className="spin" size={18} /> 正在润色…</> : <><Feather size={18} /> 一键润色</>}
          </button>
        </div>
        {imitError && <p className="field-error" role="alert" style={{ marginTop: 10 }}>{imitError}</p>}

        {imitResult && (
          <div style={{ marginTop: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, flexWrap: "wrap" }}>
              <strong>{imitResult.mode === "imitate" ? "仿写样稿" : "润色结果"}（{imitResult.text.length.toLocaleString("zh-CN")} 字）</strong>
              {imitResult.similarity?.max_similarity !== undefined && (
                <small>与原文相似度 {Math.round((imitResult.similarity.max_similarity || 0) * 100)}%{imitResult.similarity.verdict === "warning" ? " · 建议人工复核" : ""}</small>
              )}
              <button
                type="button"
                className="btn-sm"
                onClick={() => { void navigator.clipboard?.writeText(imitResult.text); }}
              >
                <Copy size={13} style={{ verticalAlign: "-2px" }} /> 复制
              </button>
              <button
                type="button"
                className="btn-sm"
                onClick={() => { setIdea(imitResult.text.slice(0, 3000)); window.scrollTo({ top: 0, behavior: "smooth" }); }}
              >
                <ArrowRight size={13} style={{ verticalAlign: "-2px" }} /> 用作故事灵感
              </button>
            </div>
            <textarea readOnly value={imitResult.text} rows={12} style={{ width: "100%", fontSize: 13, lineHeight: 1.8 }} />
            {imitResult.copyright_warning && <small style={{ display: "block", marginTop: 6, opacity: 0.75 }}>{imitResult.copyright_warning}</small>}
          </div>
        )}
      </section>
    </div>
  );
}
