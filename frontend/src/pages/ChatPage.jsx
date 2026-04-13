import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

export default function ChatPage({ token, onUnauthorized }) {
  const [chats, setChats] = useState([]);
  const [activeId, setActiveId] = useState("");
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState("");
  const [removingId, setRemovingId] = useState("");
  const bottomRef = useRef(null);

  const loadChats = useCallback(async () => {
    try {
      const list = await api("/chats", {}, token, onUnauthorized);
      setChats(list);
      if (list.length > 0 && !activeId) setActiveId(list[0].id);
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }, [token, onUnauthorized]);

  const loadMessages = useCallback(async (chatId) => {
    if (!chatId) { setMessages([]); return; }
    try {
      setMessages(await api(`/chats/${chatId}/messages`, {}, token, onUnauthorized));
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }, [token, onUnauthorized]);

  useEffect(() => { loadChats(); }, [loadChats]);
  useEffect(() => { loadMessages(activeId); }, [activeId, loadMessages]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function createChat() {
    setError("");
    try {
      const chat = await api("/chats", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: `Чат ${new Date().toLocaleString("ru")}` }),
      }, token, onUnauthorized);
      await loadChats();
      setActiveId(chat.id);
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  async function deleteChat(chatId) {
    if (!confirm("Удалить этот чат и все сообщения?")) return;
    setError("");
    setRemovingId(chatId);
    try {
      await api(`/chats/${chatId}`, { method: "DELETE" }, token, onUnauthorized);
      await new Promise((r) => setTimeout(r, 300));
      if (activeId === chatId) {
        setActiveId("");
        setMessages([]);
      }
      setChats((prev) => prev.filter((c) => c.id !== chatId));
    } catch (e) {
      setError(String(e.message ?? e));
    } finally {
      setRemovingId("");
    }
  }

  async function ask(e) {
    e.preventDefault();
    const q = question.trim();
    if (!activeId || !q) return;

    setMessages((prev) => [...prev, { id: `tmp-${Date.now()}`, role: "user", content: q }]);
    setQuestion("");
    setThinking(true);
    setError("");
    try {
      await api(`/chats/${activeId}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      }, token, onUnauthorized);
      await loadMessages(activeId);
    } catch (e) {
      setError(String(e.message ?? e));
    } finally {
      setThinking(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask(e);
    }
  }

  return (
    <div className="chat-wrapper">
      {/* sidebar */}
      <div className="chat-sidebar">
        <div className="chat-sidebar-header">
          <h3>Чаты</h3>
          <button className="btn btn-primary btn-sm" onClick={createChat}>+ Новый</button>
        </div>
        <ul className="chat-list">
          {chats.map((c) => (
            <li key={c.id} className={`chat-list-item${c.id === removingId ? " removing" : ""}`}>
              <button className={c.id === activeId ? "active" : ""} onClick={() => setActiveId(c.id)}>
                {c.title}
              </button>
              <button
                className="chat-delete-btn"
                title="Удалить чат"
                onClick={(e) => { e.stopPropagation(); deleteChat(c.id); }}
              >
                ✕
              </button>
            </li>
          ))}
          {chats.length === 0 && (
            <li style={{ padding: "16px", color: "var(--text-dim)", fontSize: 13, textAlign: "center" }}>
              Нет чатов
            </li>
          )}
        </ul>
      </div>

      {/* main */}
      <div className="chat-main">
        {error && <div className="error-box" style={{ margin: "12px 16px 0" }}>{error}</div>}

        {!activeId ? (
          <div className="chat-empty">
            Создайте чат, чтобы задать вопрос по вашим документам
          </div>
        ) : (
          <>
            <div className="chat-messages">
              {messages.length === 0 && !thinking && (
                <div className="chat-empty">Задайте вопрос — система найдёт ответ в ваших файлах</div>
              )}
              {messages.map((m) => (
                <div key={m.id} className={`msg ${m.role}`}>
                  <div className="msg-role">{m.role === "user" ? "Вы" : "Ассистент"}</div>
                  {m.content}
                  {m.sources?.length > 0 && (
                    <div className="msg-sources">
                      Источники: {m.sources.map((s) => s.file_name).join(", ")}
                    </div>
                  )}
                </div>
              ))}
              {thinking && (
                <div className="msg assistant">
                  <div className="msg-role">Ассистент</div>
                  <span className="spinner" /> Думаю...
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            <form onSubmit={ask} className="chat-input-row">
              <textarea
                className="textarea"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Задайте вопрос по вашим документам..."
                rows={1}
                disabled={thinking}
              />
              <button type="submit" className="btn btn-primary" disabled={thinking || !question.trim()}>
                {thinking ? <span className="spinner" /> : "Отправить"}
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
