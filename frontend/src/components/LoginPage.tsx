import { FormEvent, useState } from "react";
import { ArrowRight, Eye, EyeOff, Lock, Mail, Moon, Sparkles, Sun } from "lucide-react";
import { api } from "../lib/api";
import { useTheme } from "./ThemeProvider";

type Props = { onLogin: (token: string, email: string) => void };

export function LoginPage({ onLogin }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const { theme, setTheme } = useTheme();

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (!email.includes("@") || password.length < 8) {
      setError(mode === "register" ? "请输入有效邮箱，密码至少 8 位" : "请输入正确的邮箱和密码");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const path = mode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
      const data = await api<{ access_token: string }>(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!data.access_token) throw new Error("服务未返回登录凭证");
      sessionStorage.setItem("nc_token", data.access_token);
      sessionStorage.setItem("starlume_user_email", email);
      onLogin(data.access_token, email);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "登录失败，请稍后重试");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <header className="auth-header">
        <button type="button" className="auth-brand" aria-label="Starlume AI 首页">
          <span><Sparkles size={20} /></span> Starlume AI
        </button>
        <button
          type="button"
          className="auth-theme"
          aria-label={theme === "dark" ? "切换浅色模式" : "切换深色模式"}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
        </button>
      </header>

      <section className="auth-content">
        <div className="auth-intro">
          <p className="eyebrow">AI NOVEL STUDIO</p>
          <h1>让故事，<br />从灵感走到终章。</h1>
          <p>专注小说创作的个人工作台。构思、生成、编辑、审阅与导出，在一条安静而清晰的链路里完成。</p>
          <div className="auth-proof">
            <span><Sparkles size={15} /> 创作过程可控</span>
            <span><Lock size={15} /> 版本安全保留</span>
          </div>
        </div>

        <form className="auth-card" onSubmit={submit}>
          <div>
            <p className="eyebrow">{mode === "login" ? "欢迎回来" : "开始创作"}</p>
            <h2>{mode === "login" ? "登录 Starlume" : "创建你的账号"}</h2>
            <p>{mode === "login" ? "回到你的故事与创作进度。" : "建立属于你的小说创作空间。"}</p>
          </div>

          {error && <div className="auth-error" role="alert">{error}</div>}

          <label className="auth-field">
            <span>邮箱</span>
            <div><Mail size={17} /><input type="email" autoComplete="email" placeholder="name@example.com" value={email} onChange={event => setEmail(event.target.value)} /></div>
          </label>
          <label className="auth-field">
            <span>密码</span>
            <div>
              <Lock size={17} />
              <input type={showPassword ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"} placeholder="至少 8 位" value={password} onChange={event => setPassword(event.target.value)} />
              <button type="button" aria-label={showPassword ? "隐藏密码" : "显示密码"} onClick={() => setShowPassword(value => !value)}>
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </div>
          </label>

          <button type="submit" className="auth-submit" disabled={busy}>
            {busy ? <><span className="spinner" /> 处理中…</> : <>{mode === "login" ? "登录" : "注册"} <ArrowRight size={17} /></>}
          </button>
          <button
            type="button"
            className="auth-switch"
            onClick={() => { setMode(value => value === "login" ? "register" : "login"); setError(""); }}
          >
            {mode === "login" ? "没有账号？注册" : "已有账号？登录"}
          </button>
        </form>
      </section>

      <footer className="auth-footer">Starlume AI · 你的故事只属于你</footer>
    </main>
  );
}
