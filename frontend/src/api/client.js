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

export async function sendMessage(sessionId, text) {
  if (USE_MOCK) return mockChat();
  const res = await fetch(`${API_URL}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, query: text }),
  });
  if (!res.ok) {
    let reason = `Ошибка ${res.status}`;
    try { reason = (await res.json()).error || reason; } catch (e) {}
    throw new Error(reason);
  }
  const data = await res.json();
  const sources = (data.sources || []).map(s => ({
    doc: s.filepath || s.doc_id || "kb",
    chunk_id: s.chunk_id || "",
    score: s.score ?? 0,
    text: s.text || "",
  }));
  return {
    answer: data.message,
    action: data.ready_for_lead ? "offer_contact" : "answer",
    sources,
    summary: data.summary || "",
    timings: data.timings || {},
  };
}

export async function sendLead(sessionId, lead) {
  if (USE_MOCK) return new Promise(r => setTimeout(() => r({ ok: true }), 400));
  const res = await fetch(`${API_URL}/sessions/${sessionId}/lead`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(lead),
  });
  if (!res.ok) throw new Error(`Ошибка ${res.status}`);
  return res.json();
}

