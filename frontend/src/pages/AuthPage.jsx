import { useState } from "react";
import { api } from "../api";

export default function AuthPage({ onAuthenticated }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  const endpoint = mode === "login" ? "/auth/login" : "/auth/register";

  async function submit(event) {
    event.preventDefault();
    setError("");
    try {
      const payload = await api(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password })
      });
      onAuthenticated(payload.access_token);
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  return (
    <section className="card">
      <h2>{mode === "login" ? "Login" : "Register"}</h2>
      <form onSubmit={submit}>
        <input
          type="email"
          placeholder="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          type="password"
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          required
        />
        <button type="submit">{mode === "login" ? "Sign in" : "Sign up"}</button>
      </form>
      <button onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "Need an account?" : "Have an account?"}
      </button>
      {error && <pre className="error">{error}</pre>}
    </section>
  );
}
