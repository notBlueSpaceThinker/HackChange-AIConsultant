// true - ответы из заглушки, false - запросы на Go-бекенд
export const USE_MOCK = false;

const API_URL = (location.port === "3000" || location.port === "80" || location.port === "")
  ? "/api"
  : "http://localhost:8090";

let mockTurn = 0;

export function resetMockTurn() {
  mockTurn = 0;
}

function mockChat() {
  mockTurn++;
  const offer = mockTurn >= 2;
  return new Promise(r => setTimeout(() => r({
    answer: offer
      ? "Чтобы подготовить предварительную оценку, могу передать заявку менеджеру. Оставите контакты?"
      : "Да, станцию можно вводить **поэтапно**:\n- начать с 60 кВт\n- затем нарастить мощность\n\nУ вас есть данные о дневном потреблении объекта?",
    action: offer ? "offer_contact" : "clarify",
    sources: [
      { doc: "solar.md", chunk_id: "12", score: 0.91, text: "Станцию можно вводить поэтапно…" },
      { doc: "solar.md", chunk_id: "14", score: 0.74, text: "Перед проектированием нужны данные о потреблении…" },
    ],
    timings: { retrieval_ms: 120, rerank_ms: 80, llm_ms: 1400, total_ms: 1600 },
  }), 700));
}

function mapTimings(data, elapsedMs) {
  if (data.timings) return data.timings;
  const p = data.profiler;
  if (p) {
    const toMs = sec => (typeof sec === "number" ? Math.round(sec * 1000) : null);
    const emb = toMs(p.embedding_time);
    const db = toMs(p.db_search_time);
    const rag = toMs(p.rag_time);
    return {
      embedding_ms: emb,
      db_search_ms: db,
      retrieval_ms: emb !== null || db !== null ? (emb || 0) + (db || 0) : null,
      rerank_ms: toMs(p.reranking_time),
      llm_ms: toMs(p.generation_time),
      rag_ms: rag,
      total_ms: rag ?? elapsedMs,
    };
  }
  return { total_ms: elapsedMs };
}

async function readError(res) {
  const fallback = `Ошибка ${res.status}`;
  try {
    const raw = (await res.text()).trim();
    if (!raw) return fallback;
    try {
      const parsed = JSON.parse(raw);
      return parsed.error || parsed.detail || parsed.message || raw;
    } catch {
      return raw;
    }
  } catch {
    return fallback;
  }
}

export async function createChat(sessionId) {
  if (USE_MOCK) return crypto.randomUUID();
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!res.ok) throw new Error(await readError(res));
  const data = await res.json();
  if (!data.chat_id) throw new Error("Сервер не вернул chat_id");
  return data.chat_id;
}

export async function getChatHistory(chatId) {
  if (USE_MOCK) return [];
  const res = await fetch(`${API_URL}/chat?chat_id=${encodeURIComponent(chatId)}`);
  if (!res.ok) throw new Error(await readError(res));
  const data = await res.json();
  return Array.isArray(data.history) ? data.history : [];
}

export async function deleteChat(chatId) {
  if (USE_MOCK || !chatId) return;
  const res = await fetch(`${API_URL}/chat?chat_id=${encodeURIComponent(chatId)}`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 404) {
    throw new Error(await readError(res));
  }
}

export async function getDocument(docId) {
  if (USE_MOCK) {
    return {
      doc_id: docId,
      filepath: "solar.md",
      chunks: [{ chunk_id: "12", chunk_index: 0, title: "СЭС", text: "Станцию можно вводить поэтапно…" }],
    };
  }
  const res = await fetch(`${API_URL}/document?doc_id=${encodeURIComponent(docId)}`);
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export function mapSources(rawSources) {
  return (rawSources || []).map(s => ({
    doc_id: s.doc_id || "",
    title: s.title || s.filepath || s.doc_id || "Источник",
    doc: s.filepath || s.file_path || s.doc_id || "kb",
    chunk_id: s.chunk_id || "",
    score: s.score ?? 0,
    text: s.text || "",
  }));
}

export async function sendMessage(chatId, text) {
  if (USE_MOCK) return mockChat();
  const startedAt = performance.now();
  const res = await fetch(`${API_URL}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: text, chat_id: chatId }),
  });
  if (!res.ok) throw new Error(await readError(res));
  const data = await res.json();
  const elapsedMs = Math.round(performance.now() - startedAt);
  const sources = mapSources(data.sources);
  return {
    answer: data.message ?? data.response ?? "",
    action: data.ready_for_lead ? "offer_contact" : "answer",
    sources,
    summary: data.summary || "",
    timings: mapTimings(data, elapsedMs),
  };
}

export async function createProfile(sessionId, profile, chatId = null) {
  if (USE_MOCK) return new Promise(r => setTimeout(() => r({ ok: true }), 400));
  const body = {
    session_id: sessionId,
    full_name: profile.full_name,
    phone: profile.phone,
    company: profile.company,
  };
  if (chatId) body.chat_id = chatId;
  const res = await fetch(`${API_URL}/profile`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await readError(res));
  const raw = (await res.text()).trim();
  if (!raw) return { ok: true };
  try {
    return JSON.parse(raw);
  } catch {
    return { ok: true };
  }
}

export async function getOperatorChats() {
  if (USE_MOCK) return [];
  const res = await fetch(`${API_URL}/operator/chats`);
  if (!res.ok) throw new Error(await readError(res));
  const data = await res.json();
  return Array.isArray(data.chats) ? data.chats : [];
}

export async function getOperatorChat(chatId) {
  if (USE_MOCK) return null;
  const res = await fetch(`${API_URL}/operator/chat?chat_id=${encodeURIComponent(chatId)}`);
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export const sendLead = createProfile;

