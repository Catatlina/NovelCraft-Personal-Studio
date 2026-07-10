import React, { useState } from "react";
import { LogIn, UserPlus, Eye, EyeOff } from "lucide-react";
import { api } from "../lib/api";

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
      setError(mode === "register" ? "密码至少6位" : "请输入正确邮箱和密码");
      return;
    }
    setBusy(true); setError("");
    try {
      const path = mode === "login" ? "/api/v1/auth/login" : "/api/v1/auth/register";
      const data = await api<{ code: number; message: string; data?: { token: string } }>(path, {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({ email, password }),
      });
      if (data.code === 0 && data.data?.token) {
        const t = data.data.token;
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
    <div style={{ display:"flex", justifyContent:"center", alignItems:"center", minHeight:"100vh" }}>
      <div className="panel" style={{ maxWidth:400, width:"100%" }}>
        <h2 style={{ textAlign:"center", marginBottom:16 }}>{mode === "login" ? "登录" : "注册"}</h2>
        {error && <div style={{ color:"var(--warning)", marginBottom:12, fontSize:14 }}>{error}</div>}
        <div style={{ display:"flex",flexDirection:"column",gap:12 }}>
          <input type="email" placeholder="邮箱" value={email} onChange={e => setEmail(e.target.value)} />
          <div style={{ display:"flex", alignItems:"center", gap:4 }}>
            <input type={showPw ? "text" : "password"} placeholder="密码" value={password}
              onChange={e => setPassword(e.target.value)} style={{ flex:1 }}
              onKeyDown={e => e.key === "Enter" && submit()} />
            <button type="button" onClick={() => setShowPw(!showPw)} style={{ padding:"4px 8px", background:"none", border:"none", cursor:"pointer" }}>
              {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <button className="primary" onClick={submit} disabled={busy} style={{ justifyContent:"center" }}>
            {busy ? "处理中..." : (mode === "login" ? <><LogIn size={16} /> 登录</> : <><UserPlus size={16} /> 注册</>)}
          </button>
        </div>
        <div style={{ marginTop:16, textAlign:"center" }}>
          <button className="primary" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }} style={{ justifyContent:"center" }}>
            {mode === "login" ? <><UserPlus size={14} /> 没有账号？注册</> : <><LogIn size={14} /> 已有账号？登录</>}
          </button>
        </div>
      </div>
    </div>
  );
}
