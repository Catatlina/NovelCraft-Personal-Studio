import React, { useState } from "react";
import { Sparkles, Mail, Lock, Eye, EyeOff, LogIn, UserPlus } from "lucide-react";
import "../styles/proto.css";
import { api } from "../lib/api";

type Props = { onLogin: (token: string, email: string) => void };

export function LoginPage({ onLogin }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPw, setShowPw] = useState(false);

  async function submit() {
    if (!email.includes("@") || password.length < 8) {
      setError(mode === "register" ? "密码至少8位" : "请输入正确邮箱和密码");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const path =
        mode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
      const data = await api<{
        code: number;
        message: string;
        data?: { access_token: string };
      }>(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (data.code === 0 && data.data?.access_token) {
        const t = data.data.access_token;
        sessionStorage.setItem("nc_token", t);
        onLogin(t, email);
      } else {
        setError(data.message || "操作失败");
      }
    } catch {
      setError("网络错误，请检查后端是否运行");
    }
    setBusy(false);
  }

  return (
    <div style={{ height: "100vh", position: "relative", overflow: "hidden" }}>
      {/* Ambient background layers */}
      <div className="bg-ambient" />
      <div className="bg-grid" />

      {/* Login wrapper */}
      <div
        className="login-wrap"
        style={{ display: "flex", height: "100%", position: "relative", zIndex: 1 }}
      >
        <div className="login-card">
          {/* Brand lockup */}
          <div className="brand-lockup">
            <div className="brand-icon">
              <Sparkles />
            </div>
            <span className="brand-text">NovelCraft</span>
          </div>

          <h1>欢迎回来</h1>
          <p className="login-sub">AI 驱动的个人创作工作台</p>

          {/* Error message */}
          {error && (
            <div
              className="badge red"
              style={{
                width: "100%",
                justifyContent: "center",
                marginBottom: 16,
                padding: "8px 14px",
                borderRadius: "var(--r-sm)",
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}

          {/* Email */}
          <div className="form-group">
            <label className="form-label">邮箱</label>
            <div style={{ position: "relative" }}>
              <Mail
                size={16}
                style={{
                  position: "absolute",
                  left: 14,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--text-3)",
                  pointerEvents: "none",
                }}
              />
              <input
                className="form-input"
                type="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{ paddingLeft: 40 }}
                onKeyDown={(e) => e.key === "Enter" && submit()}
              />
            </div>
          </div>

          {/* Password */}
          <div className="form-group">
            <label className="form-label">密码</label>
            <div className="pw-wrap">
              <Lock
                size={16}
                style={{
                  position: "absolute",
                  left: 14,
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--text-3)",
                  pointerEvents: "none",
                  zIndex: 1,
                }}
              />
              <input
                className="form-input"
                type={showPw ? "text" : "password"}
                placeholder="输入密码"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ paddingLeft: 40, paddingRight: 44 }}
                onKeyDown={(e) => e.key === "Enter" && submit()}
              />
              <button
                type="button"
                className="eye-btn"
                onClick={() => setShowPw(!showPw)}
              >
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {/* Submit button */}
          <button
            className="btn-primary"
            onClick={submit}
            disabled={busy}
          >
            {busy ? (
              "处理中..."
            ) : (
              <>
                <LogIn size={18} />
                {mode === "login" ? "登录" : "注册"}
              </>
            )}
          </button>

          {/* Divider */}
          <div className="divider">
            <span>或</span>
          </div>

          {/* Toggle register/login */}
          <button
            className="btn-secondary"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError("");
            }}
            style={{ marginTop: 0 }}
          >
            {mode === "login" ? (
              <>
                <UserPlus size={16} />
                没有账号？注册
              </>
            ) : (
              <>
                <LogIn size={16} />
                已有账号？登录
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
