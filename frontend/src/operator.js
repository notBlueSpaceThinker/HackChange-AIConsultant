import { getOperatorChat, getOperatorChats, mapSources } from "./api/client.js?v=14";
import { createSourcesBar } from "./ui/render.js?v=14";
import { renderMarkdown } from "./utils/markdown.js?v=14";

const $ = id => document.getElementById(id);

let chats = [];
let activeChatId = null;
let currentFilter = "all";
let lastDetailSig = "";

function formatSec(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "—";
  }
  return `${Number(value).toFixed(2)} с`;
}

function buildStatsCard(stats = {}) {
  const card = document.createElement("section");
  card.className = "op-card op-stats-card";

  const head = document.createElement("div");
  head.className = "op-stats-head";
  const title = document.createElement("h3");
  title.textContent = "Средние показатели по чату";
  const count = document.createElement("span");
  count.className = "op-stats-count";
  const profiled = stats.profiled_messages ?? 0;
  const assistantTotal = stats.assistant_messages ?? 0;
  count.textContent = `Профилировано ответов: ${profiled} из ${assistantTotal}`;
  head.append(title, count);
  card.append(head);

  if (!profiled) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Нет данных профилирования для этого диалога.";
    card.append(empty);
    return card;
  }

  const metrics = [
    ["Эмбеддинг", stats.avg_embedding_time],
    ["Поиск в Qdrant", stats.avg_db_search_time],
    ["Реранжирование", stats.avg_reranking_time],
    ["Генерация LLM", stats.avg_generation_time],
    ["RAG пайплайн", stats.avg_rag_time],
    ["Суммаризатор", stats.avg_summarizer_time],
  ];

  const grid = document.createElement("div");
  grid.className = "op-stats-grid";
  for (const [label, val] of metrics) {
    const item = document.createElement("div");
    item.className = "op-stat-item";
    const lbl = document.createElement("span");
    lbl.textContent = label;
    const num = document.createElement("b");
    num.textContent = formatSec(val);
    item.append(lbl, num);
    grid.append(item);
  }
  card.append(grid);
  return card;
}

function buildMessageProfiler(profiler) {
  if (!profiler) return null;
  const parts = [
    ["RAG пайплайн", profiler.rag_time],
    ["эмбеддинг", profiler.embedding_time],
    ["поиск", profiler.db_search_time],
    ["реранк", profiler.reranking_time],
    ["LLM", profiler.generation_time],
  ];
  if (profiler.summarizer_time !== null && profiler.summarizer_time !== undefined) {
    parts.push(["суммаризатор", profiler.summarizer_time]);
  }
  const el = document.createElement("div");
  el.className = "op-msg-profiler";
  for (const [label, val] of parts) {
    const badge = document.createElement("span");
    badge.className = "op-prof-chip";
    badge.textContent = `${label}: ${formatSec(val)}`;
    el.append(badge);
  }
  return el;
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("ru-RU", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function getFilteredChats() {
  if (currentFilter === "lead") return chats.filter(c => c.has_lead);
  if (currentFilter === "open") return chats.filter(c => !c.has_lead);
  return chats;
}

function updateFilterBadges() {
  const leadCount = chats.filter(c => c.has_lead).length;
  const openCount = chats.length - leadCount;
  for (const btn of $("opFilters").querySelectorAll(".op-filter-btn")) {
    const f = btn.dataset.filter;
    if (f === "all") btn.textContent = `Все (${chats.length})`;
    else if (f === "lead") btn.textContent = `С заявкой (${leadCount})`;
    else if (f === "open") btn.textContent = `Открытые (${openCount})`;
    btn.classList.toggle("active", f === currentFilter);
  }
}

function renderChatList() {
  const listEl = $("opChatList");
  listEl.innerHTML = "";
  const items = getFilteredChats();

  if (items.length === 0) {
    listEl.innerHTML = '<p class="empty op-empty">Нет диалогов по фильтру.</p>';
    return;
  }

  for (const chat of items) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "op-chat-item"
      + (chat.has_lead ? " has-lead" : "")
      + (chat.chat_id === activeChatId ? " active" : "");

    const top = document.createElement("div");
    top.className = "op-chat-top";

    const title = document.createElement("span");
    title.className = "op-chat-title";
    title.textContent = chat.title || "Новый диалог";

    const badge = document.createElement("span");
    badge.className = chat.has_lead ? "op-badge op-badge-lead" : "op-badge op-badge-open";
    badge.textContent = chat.has_lead ? "Заявка" : "Открыт";

    top.append(title, badge);
    btn.append(top);

    const sub = document.createElement("div");
    sub.className = "op-chat-sub";
    if (chat.has_lead && chat.lead) {
      sub.textContent = `${chat.lead.full_name} · ${chat.lead.company || chat.lead.phone}`;
    } else {
      const ts = formatDate(chat.last_message_at || chat.created_at);
      sub.textContent = `${chat.message_count} сообщ.${ts ? ` · ${ts}` : ""}`;
    }
    btn.append(sub);

    btn.addEventListener("click", () => selectChat(chat.chat_id));
    listEl.append(btn);
  }
}

function renderChatDetail(detail, { force = false } = {}) {
  const sig = JSON.stringify(detail);
  if (!force && sig === lastDetailSig) return;
  lastDetailSig = sig;

  const box = $("opContent");
  box.innerHTML = "";

  const head = document.createElement("div");
  head.className = "op-detail-head";

  const info = document.createElement("div");
  const title = document.createElement("h2");
  title.className = "op-detail-title";
  const firstUserMsg = (detail.messages || []).find(m => m.author === "user")?.message;
  title.textContent = firstUserMsg || `Чат ${detail.chat_id.slice(0, 8)}`;
  const meta = document.createElement("div");
  meta.className = "op-detail-meta";
  meta.textContent = `Сессия: ${detail.session_id.slice(0, 8)} · ${formatDate(detail.created_at)}`;
  info.append(title, meta);

  const statusBadge = document.createElement("span");
  statusBadge.className = detail.has_lead ? "op-badge op-badge-lead" : "op-badge op-badge-open";
  statusBadge.textContent = detail.has_lead ? "Закрыт · Заявка отправлена" : "Диалог открыт";

  head.append(info, statusBadge);
  box.append(head);

  box.append(buildStatsCard(detail.stats));

  if (detail.has_lead && detail.lead) {
    const leadCard = document.createElement("section");
    leadCard.className = "op-card op-lead-card";
    leadCard.innerHTML = `<h3>Заявка клиента</h3>
      <div class="op-lead-grid">
        <span>ФИО</span><b></b>
        <span>Телефон</span><b></b>
        <span>Компания</span><b></b>
        <span>Отправлена</span><b></b>
      </div>`;
    const vals = leadCard.querySelectorAll(".op-lead-grid b");
    vals[0].textContent = detail.lead.full_name || "—";
    vals[1].textContent = detail.lead.phone || "—";
    vals[2].textContent = detail.lead.company || "—";
    vals[3].textContent = formatDate(detail.lead.created_at) || "—";
    box.append(leadCard);
  }

  const summaryCard = document.createElement("section");
  summaryCard.className = "op-card op-summary-card";
  const sumHead = document.createElement("h3");
  sumHead.textContent = "Саммари диалога от бота";
  summaryCard.append(sumHead);
  const sumBody = document.createElement("div");
  sumBody.className = detail.summary ? "op-summary-text" : "empty";
  if (detail.summary) {
    sumBody.innerHTML = renderMarkdown(detail.summary);
  } else {
    sumBody.textContent = "Саммари пока не сформировано.";
  }
  summaryCard.append(sumBody);
  box.append(summaryCard);

  const msgsCard = document.createElement("section");
  msgsCard.className = "op-card";
  const msgsHead = document.createElement("h3");
  msgsHead.textContent = `Переписка (${(detail.messages || []).length})`;
  msgsCard.append(msgsHead);

  const msgsList = document.createElement("div");
  msgsList.className = "op-messages";
  if (!detail.messages || detail.messages.length === 0) {
    msgsList.innerHTML = '<p class="empty">Сообщений в этом чате пока нет.</p>';
  } else {
    for (const msg of detail.messages) {
      const group = document.createElement("div");
      group.className = `op-msg-group ${msg.author === "user" ? "user" : "assistant"}`;

      const row = document.createElement("div");
      row.className = `row ${msg.author === "user" ? "user" : "assistant"}`;
      const bubble = document.createElement("div");
      bubble.className = `msg ${msg.author === "user" ? "user" : "assistant"}`;
      if (msg.author === "assistant") {
        bubble.innerHTML = renderMarkdown(msg.message);
      } else {
        bubble.textContent = msg.message;
      }
      if (msg.created_at) {
        const ts = document.createElement("div");
        ts.className = "meta";
        ts.textContent = formatDate(msg.created_at);
        bubble.append(ts);
      }
      row.append(bubble);
      group.append(row);

      if (msg.author !== "user") {
        const profEl = buildMessageProfiler(msg.profiler);
        if (profEl) group.append(profEl);

        const mappedSources = mapSources(msg.sources);
        if (mappedSources.length > 0) {
          group.append(createSourcesBar(mappedSources));
        }
      }

      msgsList.append(group);
    }
  }
  msgsCard.append(msgsList);
  box.append(msgsCard);
}

async function selectChat(chatId) {
  activeChatId = chatId;
  lastDetailSig = "";
  renderChatList();
  try {
    const detail = await getOperatorChat(chatId);
    if (detail && activeChatId === chatId) {
      renderChatDetail(detail, { force: true });
    }
  } catch (err) {
    lastDetailSig = "";
    $("opContent").innerHTML = `<p class="error">Не удалось загрузить чат: ${err.message}</p>`;
  }
}

async function loadChats({ preserveSelection = true } = {}) {
  try {
    chats = await getOperatorChats();
    updateFilterBadges();

    const filtered = getFilteredChats();
    if (!preserveSelection || !activeChatId || !chats.some(c => c.chat_id === activeChatId)) {
      activeChatId = filtered[0]?.chat_id || chats[0]?.chat_id || null;
      lastDetailSig = "";
    }

    renderChatList();
    if (activeChatId) {
      const detail = await getOperatorChat(activeChatId);
      if (detail) renderChatDetail(detail);
    } else {
      lastDetailSig = "";
      $("opContent").innerHTML = '<p class="empty">Диалогов пока нет.</p>';
    }
  } catch (err) {
    lastDetailSig = "";
    $("opContent").innerHTML = `<p class="error">Не удалось загрузить список диалогов: ${err.message}</p>`;
  }
}

$("opFilters").addEventListener("click", e => {
  const btn = e.target.closest(".op-filter-btn");
  if (!btn) return;
  currentFilter = btn.dataset.filter;
  updateFilterBadges();
  renderChatList();
});

$("refreshBtn").addEventListener("click", () => loadChats({ preserveSelection: true }));

loadChats({ preserveSelection: false });
setInterval(() => loadChats({ preserveSelection: true }), 10000);
