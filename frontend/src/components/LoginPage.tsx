import React, { useState } from "react";
import { LogIn, UserPlus, Key, Eye, EyeOff } from "lucide-react";

type Props = { onLogin: (token: string, email: string) => void };

export function LoginPage({ onLogin }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login"|"register">("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPw, setShowPw] = useState(false);

  async function submit() {
    if (!email.includes("@") || password.length < 6) {
      setError("请输入有效邮箱（≥6位密码）");
      return;
    }
    setBusy(true); setError("");
    try {
      const path = mode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
      const r = await fetch(path, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({email, password}),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || d.message || "请求失败");
      const token = d.data?.access_token;
      if (token) onLogin(token, email);
      else throw new Error("未收到 token");
    } catch (e: any) {
      setError(e.message);
    } finally { setBusy(false); }
  }

  return (
    <div style={{
      minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center",
      background: "linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%)"
    }}>
      <div style={{
        width: 380, maxWidth: "90vw", padding: 32,
        background: "var(--bg-surface)", borderRadius: 16,
        border: "1px solid var(--border-subtle)",
        boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
      }}>
        <h1 style={{ textAlign: "center", marginBottom: 4, fontSize: 24 }}>
          📖 NovelCraft
        </h1>
        <p style={{ textAlign: "center", color: "var(--text-muted)", marginBottom: 24, fontSize: 14 }}>
          Personal Studio
        </p>

        {error && (
          <div style={{
            padding: "8px 12px", marginBottom: 12, borderRadius: 8,
            background: "rgba(255,107,53,0.1)", border: "1px solid var(--warning)",
            color: "var(--warning)", fontSize: 13,
          }}>{error}</div>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, fontWeight: 600 }}>
            邮箱
            <input
              value={email} onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com" type="email"
              autoComplete="email"
            />
          </label>

          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13, fontWeight: 600 }}>
            密码
            <div style={{ position: "relative" }}>
              <input
                value={password} onChange={e => setPassword(e.target.value)}
                type={showPw ? "text" : "password"} placeholder="至少6位"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                style={{ paddingRight: 40 }}
              />
              <button
                onClick={() => setShowPw(!showPw)}
                style={{
                  position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
                  border: "none", background: "none", color: "var(--text-muted)", cursor: "pointer", padding: 4,
                }}
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </label>

          <button
            className="primary" onClick={submit} disabled={busy}
            style={{ marginTop: 4, width: "100%", justifyContent: "center" }}
          >
            {busy ? "..." : mode === "login" ? <><LogIn size={16} /> 登录</> : <><UserPlus size={16} /> 注册</>}
          </button>
        </div>

        <div style={{ textAlign: "center", marginTop: 16 }}>
          <button
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            style={{ border: "none", background: "none", color: "var(--brand-500)", cursor: "pointer", fontSize: 13 }}
          >
            {mode === "login" ? "没有账号？注册 →" : "已有账号？登录 →"}
          </button>
        </div>
      </div>
    </div>
  );
}
