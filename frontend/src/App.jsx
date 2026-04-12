import { useEffect, useMemo, useState } from "react";
import { api } from "./api";
import AuthPage from "./pages/AuthPage";
import FilesPage from "./pages/FilesPage";
import ChatPage from "./pages/ChatPage";

const TOKEN_KEY = "smartdisk_token";

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) ?? "");
  const [user, setUser] = useState(null);
  const [activePage, setActivePage] = useState("files");
  const [authLoading, setAuthLoading] = useState(false);

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
  }

  function onAuthenticated(nextToken) {
    localStorage.setItem(TOKEN_KEY, nextToken);
    setToken(nextToken);
  }

  useEffect(() => {
    if (!token) {
      return;
    }
    let cancelled = false;
    setAuthLoading(true);
    api("/auth/me", {}, token, logout)
      .then((payload) => {
        if (!cancelled) {
          setUser(payload);
        }
      })
      .catch(() => {
        if (!cancelled) {
          logout();
        }
      })
      .finally(() => {
        if (!cancelled) {
          setAuthLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const shell = useMemo(() => {
    if (!token) {
      return <AuthPage onAuthenticated={onAuthenticated} />;
    }
    if (authLoading || !user) {
      return <p>Authorizing...</p>;
    }
    if (activePage === "chat") {
      return <ChatPage token={token} onUnauthorized={logout} />;
    }
    return <FilesPage token={token} onUnauthorized={logout} />;
  }, [activePage, authLoading, token, user]);

  return (
    <main className="app-shell">
      <header className="app-header">
        <h1>Smart Disk</h1>
        {token && user ? (
          <div className="header-row">
            <span>{user.email}</span>
            <nav className="tabs">
              <button
                className={activePage === "files" ? "active" : ""}
                onClick={() => setActivePage("files")}
              >
                Files
              </button>
              <button
                className={activePage === "chat" ? "active" : ""}
                onClick={() => setActivePage("chat")}
              >
                Chat
              </button>
            </nav>
            <button onClick={logout}>Logout</button>
          </div>
        ) : null}
      </header>
      {shell}
    </main>
  );
}
