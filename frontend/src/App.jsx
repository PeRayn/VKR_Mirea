import { useEffect, useState } from "react";
import { api } from "./api";
import AuthPage from "./pages/AuthPage";
import FilesPage from "./pages/FilesPage";
import ChatPage from "./pages/ChatPage";

const TOKEN_KEY = "smartdisk_token";
const PAGE_KEY = "smartdisk_page";

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [user, setUser] = useState(null);
  const [page, setPageRaw] = useState(() => localStorage.getItem(PAGE_KEY) ?? "files");

  function setPage(p) {
    localStorage.setItem(PAGE_KEY, p);
    setPageRaw(p);
  }
  const [loading, setLoading] = useState(false);

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
  }

  function onAuth(t) {
    localStorage.setItem(TOKEN_KEY, t);
    setToken(t);
  }

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    api("/auth/me", {}, token, logout)
      .then((u) => { if (!cancelled) setUser(u); })
      .catch(() => { if (!cancelled) logout(); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token]);

  if (!token) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <h1>Умный Диск</h1>
        </header>
        <AuthPage onAuth={onAuth} />
      </div>
    );
  }

  if (loading || !user) {
    return (
      <div className="app-shell">
        <header className="app-header">
          <h1>Умный Диск</h1>
        </header>
        <div className="app-content" style={{ textAlign: "center", paddingTop: 80 }}>
          <div className="spinner" />
          <p style={{ marginTop: 12, color: "var(--text-dim)" }}>Авторизация...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Умный Диск</h1>
        <div className="header-right">
          <span className="user-email">{user.email}</span>
          <nav className="tabs">
            <button className={page === "files" ? "active" : ""} onClick={() => setPage("files")}>
              Файлы
            </button>
            <button className={page === "chat" ? "active" : ""} onClick={() => setPage("chat")}>
              Чат
            </button>
          </nav>
          <button className="btn btn-ghost btn-sm" onClick={logout}>Выйти</button>
        </div>
      </header>

      <div className="app-content">
        {page === "chat"
          ? <ChatPage token={token} onUnauthorized={logout} />
          : <FilesPage token={token} onUnauthorized={logout} />}
      </div>
    </div>
  );
}
