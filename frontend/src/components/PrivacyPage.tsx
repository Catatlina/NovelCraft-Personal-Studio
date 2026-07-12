import React from "react";

export function PrivacyPage() {
  return (
    <div className="panel" style={{ maxWidth: 800, margin: "0 auto" }}>
      <h2>隐私政策</h2>
      <p style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 16 }}>
        最后更新：2026年7月
      </p>

      <h3>1. 信息收集</h3>
      <p>NovelCraft 收集以下信息以提供服务：</p>
      <ul>
        <li><strong>账户信息</strong>：电子邮件地址、密码（bcrypt 加密存储）</li>
        <li><strong>创作内容</strong>：您创作的小说、章节、大纲等文本内容</li>
        <li><strong>使用数据</strong>：AI 调用次数、Token 消耗量、功能使用频率</li>
      </ul>

      <h3>2. 信息使用</h3>
      <p>我们使用收集的信息：</p>
      <ul>
        <li>提供 AI 辅助创作服务</li>
        <li>改进模型质量和 Prompt 效果</li>
        <li>计算和展示 AI 调用成本</li>
        <li>发送服务相关通知</li>
      </ul>

      <h3>3. 数据存储与安全</h3>
      <ul>
        <li>所有数据存储在加密的 PostgreSQL 数据库中</li>
        <li>密码使用 bcrypt 哈希，不可逆</li>
        <li>API 通信支持 TLS 加密（生产环境）</li>
        <li>平台账号凭证使用 Fernet 加密存储</li>
      </ul>

      <h3>4. AI 模型使用</h3>
      <p>当您使用 AI 功能时，部分创作内容会发送至您配置的 AI 提供商（DeepSeek、Claude、OpenAI、Gemini）。请参阅各提供商的隐私政策：</p>
      <ul>
        <li><a href="https://api-docs.deepseek.com/" target="_blank" rel="noopener">DeepSeek API</a></li>
        <li><a href="https://docs.anthropic.com/" target="_blank" rel="noopener">Anthropic Claude</a></li>
        <li><a href="https://platform.openai.com/docs/" target="_blank" rel="noopener">OpenAI</a></li>
        <li><a href="https://ai.google.dev/" target="_blank" rel="noopener">Google Gemini</a></li>
      </ul>

      <h3>5. 数据删除</h3>
      <p>您可以通过"设置 → 账户 → 删除账户"来删除您的账户和所有关联数据。项目支持软删除（可恢复），彻底删除请联系管理员。</p>

      <h3>6. 用户权利</h3>
      <ul>
        <li>访问和导出您的所有创作内容（TXT/MD/EPub 格式）</li>
        <li>修改或删除您的个人信息</li>
        <li>随时停止使用服务</li>
      </ul>

      <h3>7. Cookie 政策</h3>
      <p>NovelCraft 使用必要的 Cookie：</p>
      <ul>
        <li><code>csrf_token</code>：CSRF 防护令牌</li>
        <li><code>refresh_token</code>（httpOnly）：自动登录刷新令牌</li>
      </ul>
      <p>不使用追踪 Cookie 或第三方分析 Cookie。</p>

      <h3>8. 联系我们</h3>
      <p>如有隐私相关问题，请通过 GitHub Issues 联系我们：<br />
      <a href="https://github.com/Catatlina/NovelCraft-Personal-Studio" target="_blank" rel="noopener">
        github.com/Catatlina/NovelCraft-Personal-Studio
      </a></p>
    </div>
  );
}
