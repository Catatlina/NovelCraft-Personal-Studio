import { useEffect, useState } from "react";
import { AlertTriangle, ArrowRight, BookOpen, Feather, Loader2, Sparkles } from "lucide-react";
import { apiRaw, getApiKey } from "../lib/api";

const GENRES = ["都市", "科幻", "玄幻", "仙侠", "悬疑", "历史", "游戏", "轻小说", "短篇", "其他"];
const WORD_PRESETS = [
  { value: 100000, label: "短篇", hint: "约 10 万字" },
  { value: 300000, label: "中篇", hint: "约 30 万字" },
  { value: 800000, label: "长篇", hint: "约 80 万字" },
  { value: 1500000, label: "超长篇", hint: "约 150 万字" },
];

export function Wizard({
  idea,
  setIdea,
  genre,
  setGenre,
  style,
  setStyle,
  targetWords,
  setTargetWords,
  busy,
  startBootstrap,
}: {
  idea: string;
  setIdea: (value: string) => void;
  genre: string;
  setGenre: (value: string) => void;
  style: string;
  setStyle: (value: string) => void;
  targetWords: number;
  setTargetWords: (value: number) => void;
  busy: boolean;
  startBootstrap: () => void;
}) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [keyMissing, setKeyMissing] = useState(false);

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
    if (!style.trim()) nextErrors.style = "请描述希望保持的写作风格";
    if (targetWords < 5000) nextErrors.targetWords = "目标字数不能少于 5,000";
    if (targetWords > 5000000) nextErrors.targetWords = "目标字数不能超过 500 万";
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
                onChange={event => { setGenre(event.target.value); clearError("genre"); }}
                aria-invalid={Boolean(errors.genre)}
              >
                <option value="">选择题材</option>
                {GENRES.map(item => <option key={item} value={item}>{item}</option>)}
              </select>
              {errors.genre && <small className="field-error">{errors.genre}</small>}
            </label>
            <label className="wizard-field">
              <span>写作风格</span>
              <input
                value={style}
                onChange={event => { setStyle(event.target.value); clearError("style"); }}
                placeholder="例如：克制、悬疑、强画面感"
                maxLength={300}
                aria-invalid={Boolean(errors.style)}
              />
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
              min={5000}
              max={5000000}
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
    </div>
  );
}
