import { useEffect, useState } from "react";
import { api, API_BASE_URL } from "../api";

export default function FilesPage({ token, onUnauthorized }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

  async function loadFiles() {
    setLoading(true);
    setError("");
    try {
      const payload = await api("/files", {}, token, onUnauthorized);
      setFiles(payload);
    } catch (e) {
      setError(String(e.message ?? e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadFiles();
  }, []);

  async function handleUpload(event) {
    const selected = event.target.files?.[0];
    if (!selected) {
      return;
    }
    const formData = new FormData();
    formData.append("upload", selected);
    setUploading(true);
    setError("");
    try {
      await api(
        "/files/upload",
        {
          method: "POST",
          body: formData
        },
        token,
        onUnauthorized
      );
      await loadFiles();
    } catch (e) {
      setError(String(e.message ?? e));
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  }

  async function handleDelete(fileId) {
    if (!window.confirm("Delete this file?")) {
      return;
    }
    setError("");
    try {
      await api(`/files/${fileId}`, { method: "DELETE" }, token, onUnauthorized);
      await loadFiles();
    } catch (e) {
      setError(String(e.message ?? e));
    }
  }

  return (
    <section className="card">
      <h2>Your files</h2>
      <label className="upload-label">
        <span>{uploading ? "Uploading..." : "Upload file (.pdf/.docx/.txt/.md)"}</span>
        <input
          type="file"
          accept=".pdf,.docx,.txt,.md"
          onChange={handleUpload}
          disabled={uploading}
        />
      </label>
      {loading ? <p>Loading...</p> : null}
      {error ? <pre className="error">{error}</pre> : null}
      <ul className="file-list">
        {files.map((file) => (
          <li key={file.id}>
            <div>
              <strong>{file.original_name}</strong>
              <p>{Math.ceil(file.size_bytes / 1024)} KB</p>
            </div>
            <div className="row-actions">
              <a
                href={`${API_BASE_URL}/files/${file.id}/download`}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => {
                  e.preventDefault();
                  fetch(`${API_BASE_URL}/files/${file.id}/download`, {
                    headers: { Authorization: `Bearer ${token}` }
                  })
                    .then((res) => {
                      if (!res.ok) {
                        throw new Error(`Download failed (${res.status})`);
                      }
                      return res.blob();
                    })
                    .then((blob) => {
                      const url = URL.createObjectURL(blob);
                      const link = document.createElement("a");
                      link.href = url;
                      link.download = file.original_name;
                      link.click();
                      URL.revokeObjectURL(url);
                    })
                    .catch((err) => setError(String(err.message ?? err)));
                }}
              >
                Download
              </a>
              <button onClick={() => handleDelete(file.id)}>Delete</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
