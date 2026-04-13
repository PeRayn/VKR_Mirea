function resolveApiBase() {
  const raw = (import.meta.env.VITE_API_URL ?? "").trim().replace(/\/$/, "");
  if (import.meta.env.DEV) {
    return raw || "/api";
  }
  return raw || "http://localhost:8000";
}

export const API_BASE_URL = resolveApiBase();

const ERROR_MAP = {
  "Invalid credentials": "Неверный логин или пароль",
  "Email already exists": "Пользователь с таким email уже существует",
  "Invalid token": "Сессия истекла. Войдите заново",
  "User not found": "Пользователь не найден",
  "Unsupported file extension": "Неподдерживаемый формат файла",
  "Empty file is not allowed": "Нельзя загрузить пустой файл",
  "Could not parse document content": "Не удалось прочитать содержимое файла",
  "Could not extract text from file": "Не удалось извлечь текст из файла",
  "File not found": "Файл не найден",
  "Chat not found": "Чат не найден",
};

const FIELD_NAMES = {
  question: "Вопрос",
  password: "Пароль",
  email: "Email",
  title: "Название",
};

const VALIDATION_MAP = {
  string_too_short: (ctx, field) => `Для ${field.toLowerCase() === "вопрос" ? "запроса" : `поля «${field}»`} требуется минимум ${ctx.min_length} символа`,
  string_too_long: (ctx, field) => `${field}: максимум ${ctx.max_length} символов`,
  value_error: (_ctx, field) => `${field}: некорректное значение`,
  missing: (_ctx, field) => `${field}: обязательное поле`,
};

function humanError(raw) {
  if (typeof raw === "string") return ERROR_MAP[raw] ?? raw;

  if (Array.isArray(raw)) {
    const lines = raw.map((err) => {
      const fieldKey = err.loc?.slice(-1)[0] ?? "";
      const field = FIELD_NAMES[fieldKey] ?? fieldKey;
      const handler = VALIDATION_MAP[err.type];
      if (handler) return handler(err.ctx ?? {}, field);
      return `${field}: ${err.msg}`;
    });
    return lines.join("\n");
  }

  return JSON.stringify(raw);
}

export async function api(path, options = {}, token, onUnauthorized) {
  const headers = { ...(options.headers ?? {}) };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error("Не удалось подключиться к серверу. Проверьте, что backend запущен.");
  }

  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = humanError(body.detail ?? body);
    } catch {
      try { detail = await response.text(); } catch { /* empty */ }
    }

    if ((response.status === 401 || response.status === 403) && onUnauthorized) {
      onUnauthorized();
    }

    throw new Error(detail || `Ошибка сервера (${response.status})`);
  }

  const ct = response.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

export async function fetchBlob(path, token, onUnauthorized) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { headers });
  } catch {
    throw new Error("Не удалось подключиться к серверу. Проверьте, что backend запущен.");
  }

  if (!response.ok) {
    let detail = "";
    try {
      const body = await response.json();
      detail = humanError(body.detail ?? body);
    } catch {
      try { detail = await response.text(); } catch { /* empty */ }
    }

    if ((response.status === 401 || response.status === 403) && onUnauthorized) {
      onUnauthorized();
    }

    throw new Error(detail || `Ошибка сервера (${response.status})`);
  }

  return response.blob();
}
