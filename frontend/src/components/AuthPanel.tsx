import { FormEvent, useState } from "react";

import { loginUser, registerUser } from "../api";
import type { TokenResponse } from "../types";

type AuthMode = "login" | "register";

type AuthPanelProps = {
  apiStatus: string;
  notice?: string;
  onAuthenticated: (tokenResponse: TokenResponse) => void;
};

function AuthPanel({ apiStatus, notice, onAuthenticated }: AuthPanelProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      if (mode === "register") {
        await registerUser({ username: username.trim(), email: email.trim(), password });
      }
      const tokenResponse = await loginUser({
        username_or_email: mode === "register" ? username.trim() : username.trim(),
        password,
      });
      onAuthenticated(tokenResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "认证失败");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel" aria-label="认证">
        <div className="auth-copy">
          <p className="eyebrow">方志云藏</p>
          <h1>古籍县志知识库</h1>
          <p>登录后为单本县志创建知识库，上传影像转写或整理文本，并基于来源片段进行问答。</p>
          <span className={apiStatus === "可用" ? "tone-ok" : "tone-bad"}>服务{apiStatus}</span>
          {apiStatus !== "可用" && (
            <p className="auth-hint">当前服务暂不可用，请稍后再试。</p>
          )}
        </div>

        <form className="auth-form" onSubmit={submit}>
          <div className="segmented">
            <button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>
              登录
            </button>
            <button
              type="button"
              className={mode === "register" ? "active" : ""}
              onClick={() => setMode("register")}
            >
              注册
            </button>
          </div>

          <label className="light-field">
            <span>{mode === "login" ? "用户名或邮箱" : "用户名"}</span>
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              minLength={3}
              maxLength={255}
              required
            />
          </label>

          {mode === "register" && (
            <label className="light-field">
              <span>邮箱</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                minLength={3}
                maxLength={255}
                required
              />
            </label>
          )}

          <label className="light-field">
            <span>密码</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={mode === "register" ? 8 : 1}
              maxLength={128}
              required
            />
          </label>

          {notice && <p className="form-error">{notice}</p>}
          {error && <p className="form-error">{error}</p>}

          <button className="primary-button" disabled={pending}>
            {pending ? "处理中..." : mode === "login" ? "登录" : "注册并登录"}
          </button>
        </form>
      </section>
    </main>
  );
}

export default AuthPanel;
