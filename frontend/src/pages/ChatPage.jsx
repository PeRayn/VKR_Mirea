import { useEffect, useState } from "react";
import { api } from "../api";

export default function ChatPage({ token, onUnauthorized }) {
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState("");
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function loadChats() {
    const payload = await api("/chats", {}, token, onUnauthorized);
    setChats(payload);
    if (payload.length > 0 && !activeChatId) {
      setActiveChatId(payload[0].id);
    }
  }

  async function loadMessages(chatId) {
    if (!chatId) {
      setMessages([]);
      return;
    }
    const payload = await api(`/chats/${chatId}/messages`, {}, token, onUnauthorized);
    setMessages(payload);
  }

  useEffect(() => {
    loadChats().catch((e) => setError(String(e.message ?? e)));
  }, []);

  useEffect(() => {
    loadMessages(activeChatId).catch((e) => setError(String(e.message ?? e)));
  }, [activeChatId]);

  async function createChat() {
    setError("");
    try {
      const chat = await api(
        "/chats",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: `Chat ${new Date().toLocaleString()}` })
        },
        token,
        onUnauthorized
      );
      await loadChats();
      setActiveChatId(chat.id);
      await loadMessages(chat.id);
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  async function askQuestion(event) {
    event.preventDefault();
    if (!activeChatId || !question.trim()) {
      return;
    }
    setLoading(true);
    setError("");
    try {
      await api(
        `/chats/${activeChatId}/ask`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: question.trim() })
        },
        token,
        onUnauthorized
      );
      setQuestion("");
      await loadMessages(activeChatId);
    } catch (e) {
      setError(String(e.message ?? e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card chat-layout">
      <aside>
        <div className="chat-title-row">
          <h2>Chats</h2>
          <button onClick={createChat}>New</button>
        </div>
        <ul className="chat-list">
          {chats.map((chat) => (
            <li key={chat.id}>
              <button
                className={chat.id === activeChatId ? "active" : ""}
                onClick={() => setActiveChatId(chat.id)}
              >
                {chat.title}
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <div>
        <h2>Ask documents</h2>
        {error ? <pre className="error">{error}</pre> : null}
        <div className="messages">
          {messages.map((message) => (
            <article key={message.id} className={`message ${message.role}`}>
              <h4>{message.role}</h4>
              <p>{message.content}</p>
              {message.sources?.length ? (
                <small>
                  Sources:{" "}
                  {message.sources.map((source) => source.file_name).join(", ")}
                </small>
              ) : null}
            </article>
          ))}
        </div>
        <form onSubmit={askQuestion} className="ask-form">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about your files"
            rows={4}
          />
          <button type="submit" disabled={loading || !activeChatId}>
            {loading ? "Thinking..." : "Ask"}
          </button>
        </form>
      </div>
    </section>
  );
}
