import { useCallback, useEffect, useRef, useState } from "react";
import { api, API_BASE_URL, fetchBlob } from "../api";

const EXT_ICONS = { ".pdf": "📑", ".docx": "📝", ".txt": "📄", ".md": "📓" };

function fileExt(name) {
  return name.slice(name.lastIndexOf(".")).toLowerCase();
}

function fileIcon(name) {
  return EXT_ICONS[fileExt(name)] ?? "📎";
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function FilesPage({ token, onUnauthorized }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [preview, setPreview] = useState(null);
  const inputRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setFiles(await api("/files", {}, token, onUnauthorized));
    } catch (e) {
      setError(String(e.message ?? e));
    } finally {
      setLoading(false);
    }
  }, [token, onUnauthorized]);

  useEffect(() => { load(); }, [load]);

  async function upload(file) {
    if (!file) return;
    if (inputRef.current) inputRef.current.value = "";
    const form = new FormData();
    form.append("upload", file);
    setUploading(true);
    setError("");
    try {
      await api("/files/upload", { method: "POST", body: form }, token, onUnauthorized);
      await load();
    } catch (e) {
      setError(String(e.message ?? e));
    } finally {
      setUploading(false);
    }
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) upload(file);
  }

  async function download(f) {
    try {
      const res = await fetch(`${API_BASE_URL}/files/${f.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Ошибка загрузки (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = f.original_name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  async function openPreview(f) {
    const ext = fileExt(f.original_name);
    setPreview({ file: f, loading: true, text: "", blobUrl: "" });

    try {
      if (ext === ".pdf") {
        const blob = await fetchBlob(`/files/${f.id}/view`, token, onUnauthorized);
        const url = URL.createObjectURL(blob);
        setPreview({ file: f, loading: false, text: "", blobUrl: url });
      } else {
        const text = await api(`/files/${f.id}/content`, {}, token, onUnauthorized);
        setPreview({ file: f, loading: false, text, blobUrl: "" });
      }
    } catch (e) {
      setPreview({ file: f, loading: false, text: `Ошибка: ${e.message}`, blobUrl: "" });
    }
  }

  function closePreview() {
    if (preview?.blobUrl) URL.revokeObjectURL(preview.blobUrl);
    setPreview(null);
  }

  async function remove(id) {
    if (!window.confirm("Удалить файл?")) return;
    setError("");
    try {
      await api(`/files/${id}`, { method: "DELETE" }, token, onUnauthorized);
      await load();
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  return (
    <>
      <div className="files-header">
        <h2>Ваши файлы</h2>
        {files.length > 0 && (
          <span style={{ color: "var(--text-dim)", fontSize: 13 }}>{files.length} файл(ов)</span>
        )}
      </div>

      <div
        className={`drop-zone${dragging ? " dragging" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.txt,.md"
          onClick={(e) => { e.target.value = ""; }}
          onChange={(e) => upload(e.target.files?.[0])}
        />
        <span className="drop-icon">{uploading ? "⏳" : "📤"}</span>
        <span className="drop-text">
          {uploading ? "Загрузка..." : "Перетащите файл сюда или нажмите для выбора"}
        </span>
        <span className="drop-hint">PDF, DOCX, TXT, MD — до 20 MB</span>
      </div>

      {error && <div className="error-box" style={{ marginBottom: 16 }}>{error}</div>}

      {loading ? (
        <div style={{ textAlign: "center", padding: 32 }}><div className="spinner" /></div>
      ) : files.length === 0 ? (
        <div className="files-empty">Файлов пока нет. Загрузите первый документ.</div>
      ) : (
        <div className="file-grid">
          {files.map((f) => (
            <div key={f.id} className="file-card" onClick={() => openPreview(f)} style={{ cursor: "pointer" }}>
              <div className="file-icon">{fileIcon(f.original_name)}</div>
              <div className="file-info">
                <div className="file-name" title={f.original_name}>{f.original_name}</div>
                <div className="file-meta">{formatSize(f.size_bytes)}</div>
              </div>
              <div className="file-actions" onClick={(e) => e.stopPropagation()}>
                <button className="btn btn-ghost btn-sm" onClick={() => openPreview(f)} title="Просмотр">
                  {"👁"}
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => download(f)} title="Скачать">
                  {"⬇"}
                </button>
                <button className="btn btn-ghost btn-sm btn-danger" onClick={() => remove(f.id)} title="Удалить">
                  {"✕"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Preview modal */}
      {preview && (
        <div className="modal-overlay" onClick={closePreview}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{preview.file.original_name}</h3>
              <div className="modal-header-actions">
                <button className="btn btn-sm" onClick={() => download(preview.file)}>{"⬇"} Скачать</button>
                <button className="btn btn-ghost btn-sm" onClick={closePreview}>{"✕"}</button>
              </div>
            </div>
            <div className="modal-body">
              {preview.loading ? (
                <div style={{ textAlign: "center", padding: 48 }}>
                  <div className="spinner" />
                  <p style={{ marginTop: 12, color: "var(--text-dim)" }}>Загрузка содержимого...</p>
                </div>
              ) : preview.blobUrl ? (
                <iframe src={preview.blobUrl} className="pdf-frame" title="PDF preview" />
              ) : (
                <pre className="text-preview">{preview.text}</pre>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
