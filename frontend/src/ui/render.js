import { getDocument } from "../api/client.js?v=14";
import { pickRandomStarters, STARTERS_POOL } from "../data/starters.js?v=14";
import { renderMarkdown } from "../utils/markdown.js?v=14";

const AVATAR = '<div class="avatar"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"><path d="M4 5h16v11H10l-4 4v-4H4z"/><path d="M12 8.2l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z" fill="#FF0032" stroke="#FF0032" stroke-width="1"/></svg></div>';
const INITIAL_VISIBLE_CHUNKS = 4;
const docCache = new Map();

function stripTitlePrefix(text, title) {
  const raw = text || "";
  if (title && raw.startsWith(title)) {
    return raw.slice(title.length).replace(/^\s+/, "") || raw;
  }
  return raw;
}

function formatScore(score) {
  if (typeof score !== "number" || Number.isNaN(score)) return "";
  return score === 0 ? "0.00 (expanded)" : score.toFixed(2);
}

export const STARTERS = STARTERS_POOL;

export function openChunkModal(source) {
  document.querySelector(".chunk-modal-backdrop")?.remove();

  const backdrop = document.createElement("div");
  backdrop.className = "chunk-modal-backdrop";

  const modal = document.createElement("div");
  modal.className = "chunk-modal";
  modal.setAttribute("role", "dialog");
  modal.setAttribute("aria-modal", "true");

  const header = document.createElement("div");
  header.className = "chunk-modal-head";

  const titleWrap = document.createElement("div");
  titleWrap.className = "chunk-modal-titles";

  const titleEl = document.createElement("h3");
  titleEl.textContent = source.title || source.doc || "Источник";
  titleWrap.append(titleEl);

  if (source.doc) {
    const sub = document.createElement("div");
    sub.className = "chunk-modal-sub";
    const scoreStr = formatScore(source.score);
    sub.textContent = scoreStr ? `${source.doc} · ${scoreStr}` : source.doc;
    titleWrap.append(sub);
  }

  const actions = document.createElement("div");
  actions.className = "chunk-modal-actions";

  let docBtn = null;
  if (source.doc_id) {
    docBtn = document.createElement("button");
    docBtn.type = "button";
    docBtn.className = "chunk-modal-doc-btn";
    docBtn.textContent = "Открыть весь документ";
    actions.append(docBtn);
  }

  const closeBtn = document.createElement("button");
  closeBtn.type = "button";
  closeBtn.className = "chunk-modal-close";
  closeBtn.setAttribute("aria-label", "Закрыть");
  closeBtn.textContent = "×";
  actions.append(closeBtn);

  header.append(titleWrap, actions);

  const body = document.createElement("div");
  body.className = "chunk-modal-body";

  const renderChunkOnly = () => {
    titleEl.textContent = source.title || source.doc || "Источник";
    body.innerHTML = renderMarkdown(stripTitlePrefix(source.text, source.title));
    body.scrollTop = 0;
    if (docBtn) docBtn.textContent = "Открыть весь документ";
  };

  const renderFullDocument = doc => {
    titleEl.textContent = doc.filepath || source.doc || "Документ";
    body.innerHTML = "";
    const container = document.createElement("div");
    container.className = "doc-view";
    let prevTitle = "";
    let activeEl = null;

    for (const chunk of doc.chunks || []) {
      const block = document.createElement("div");
      const isActive = chunk.chunk_id === source.chunk_id;
      block.className = isActive ? "doc-chunk is-active" : "doc-chunk";

      if (chunk.title && chunk.title !== prevTitle) {
        const heading = document.createElement("div");
        heading.className = "doc-chunk-heading";
        heading.textContent = chunk.title;
        block.append(heading);
      }
      prevTitle = chunk.title || prevTitle;

      if (isActive) {
        const tag = document.createElement("span");
        tag.className = "doc-chunk-tag";
        tag.textContent = "Выбранный фрагмент";
        block.append(tag);
        activeEl = block;
      }

      const contentEl = document.createElement("div");
      contentEl.innerHTML = renderMarkdown(stripTitlePrefix(chunk.text, chunk.title));
      block.append(contentEl);
      container.append(block);
    }

    body.append(container);
    if (docBtn) docBtn.textContent = "← К фрагменту";
    if (activeEl) {
      requestAnimationFrame(() => activeEl.scrollIntoView({ block: "center", behavior: "smooth" }));
    }
  };

  renderChunkOnly();

  let showingDoc = false;
  if (docBtn) {
    docBtn.addEventListener("click", async () => {
      if (showingDoc) {
        showingDoc = false;
        renderChunkOnly();
        return;
      }
      showingDoc = true;
      docBtn.disabled = true;
      docBtn.textContent = "Загрузка…";
      try {
        let doc = docCache.get(source.doc_id);
        if (!doc) {
          doc = await getDocument(source.doc_id);
          docCache.set(source.doc_id, doc);
        }
        if (!document.body.contains(backdrop)) return;
        renderFullDocument(doc);
      } catch (err) {
        showingDoc = false;
        renderChunkOnly();
        const errBox = document.createElement("div");
        errBox.className = "chunk-modal-status";
        errBox.textContent = `Не удалось загрузить документ: ${err.message || "ошибка"}`;
        body.prepend(errBox);
      } finally {
        docBtn.disabled = false;
      }
    });
  }

  modal.append(header, body);
  backdrop.append(modal);

  const close = () => {
    backdrop.remove();
    document.removeEventListener("keydown", onKeyDown);
  };
  const onKeyDown = e => {
    if (e.key === "Escape") close();
  };

  closeBtn.addEventListener("click", close);
  backdrop.addEventListener("click", e => {
    if (e.target === backdrop) close();
  });
  document.addEventListener("keydown", onKeyDown);
  document.body.append(backdrop);
  closeBtn.focus();
}

export function createSourcesBar(sources) {
  const wrap = document.createElement("div");
  wrap.className = "chunk-list";

  const makePill = source => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chunk-pill";
    const label = source.title || source.doc || "Источник";
    const isExpanded = source.score === 0;
    btn.title = isExpanded ? `${label} (expanded)` : label;
    const titleSpan = document.createElement("span");
    titleSpan.className = "chunk-pill-title";
    titleSpan.textContent = label;
    btn.append(titleSpan);
    if (isExpanded) {
      const badge = document.createElement("span");
      badge.className = "chunk-pill-badge";
      badge.textContent = "expanded";
      btn.append(badge);
    }
    btn.addEventListener("click", () => openChunkModal(source));
    return btn;
  };

  const hasMore = sources.length > INITIAL_VISIBLE_CHUNKS;
  let expanded = false;

  const renderPills = () => {
    wrap.innerHTML = "";
    const visible = !hasMore || expanded ? sources : sources.slice(0, INITIAL_VISIBLE_CHUNKS);
    for (const src of visible) {
      wrap.append(makePill(src));
    }
    if (hasMore) {
      const toggleBtn = document.createElement("button");
      toggleBtn.type = "button";
      toggleBtn.className = "chunk-pill chunk-more";
      toggleBtn.title = expanded
        ? "Свернуть источники"
        : `Показать все источники (${sources.length})`;
      toggleBtn.textContent = expanded ? "Свернуть" : "…";
      toggleBtn.addEventListener("click", () => {
        expanded = !expanded;
        renderPills();
      });
      wrap.append(toggleBtn);
    }
  };

  renderPills();
  return wrap;
}

export function createMessageElement(role, text, meta = "", sources = []) {
  const row = document.createElement("div");
  row.className = `row ${role}`;
  if (role === "assistant") row.insertAdjacentHTML("beforeend", AVATAR);
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  if (role === "assistant") el.innerHTML = renderMarkdown(text);
  else el.textContent = text;
  if (meta) {
    const m = document.createElement("div");
    m.className = "meta";
    m.textContent = meta;
    el.append(m);
  }
  row.append(el);

  if (role === "assistant" && Array.isArray(sources) && sources.length > 0) {
    const group = document.createElement("div");
    group.className = "msg-group";
    group.append(row, createSourcesBar(sources));
    return group;
  }
  return row;
}

export function createTypingElement() {
  const row = document.createElement("div");
  row.className = "row assistant";
  row.insertAdjacentHTML("beforeend", AVATAR);
  const el = document.createElement("div");
  el.className = "msg assistant";
  el.innerHTML = '<span class="dots"><i></i><i></i><i></i></span>';
  row.append(el);
  return row;
}

export function createChipsElement(onSelect, starters = pickRandomStarters(4)) {
  const box = document.createElement("div");
  box.className = "chips";
  box.id = "chips";
  for (const q of starters) {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = q;
    b.addEventListener("click", () => onSelect(q));
    box.append(b);
  }
  return box;
}

export function createLeadDoneElement() {
  const d = document.createElement("div");
  d.className = "lead-ok";
  d.innerHTML = '<svg viewBox="0 0 52 52"><circle cx="26" cy="26" r="24"/><path d="M15 27l8 8 14-16"/></svg><p>Спасибо! Заявка передана менеджеру, он свяжется с вами.</p>';
  return d;
}

export function createLeadFormElement(onSubmit) {
  const form = document.createElement("form");
  form.className = "lead";
  form.innerHTML = `<h3>Заявка менеджеру</h3>
    <input name="full_name" placeholder="ФИО">
    <input name="phone" placeholder="Телефон, например +7 900 123-45-67">
    <input name="company" placeholder="Компания">
    <div class="error"></div>
    <button class="primary">Отправить заявку</button>`;
  const err = form.querySelector(".error");
  form.addEventListener("input", () => { err.textContent = ""; });
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const lead = Object.fromEntries(new FormData(form));
    for (const k in lead) lead[k] = lead[k].trim();
    if (!lead.full_name || !lead.phone || !lead.company) {
      err.textContent = "Заполните все три поля";
      return;
    }
    if (lead.phone.replace(/\D/g, "").length !== 11) {
      err.textContent = "Проверьте номер телефона";
      return;
    }
    const btn = form.querySelector("button");
    btn.disabled = true;
    try {
      await onSubmit(lead);
      form.replaceWith(createLeadDoneElement());
    } catch {
      err.textContent = "Не удалось отправить, попробуйте ещё раз";
      btn.disabled = false;
    }
  });
  return form;
}

export function createDebugStepElement(question, data) {
  const t = data.timings || {};
  const step = document.createElement("div");
  step.className = "step";
  const fmt = v => (v ?? "-");
  step.innerHTML = `<span class="tag"></span><p></p>
    <div class="times">
      <span>Эмбеддинги</span><span>${fmt(t.embedding_ms)} мс</span>
      <span>Поиск в БД</span><span>${fmt(t.db_search_ms ?? t.retrieval_ms)} мс</span>
      <span>Реранкер</span><span>${fmt(t.rerank_ms)} мс</span>
      <span>Модель</span><span>${fmt(t.llm_ms)} мс</span>
      <b>Всего</b><b>${fmt(t.total_ms)} мс</b>
    </div>`;
  step.querySelector(".tag").textContent = data.action || "answer";
  step.querySelector("p").textContent = "Вопрос: " + question;
  if (data.summary) {
    const sum = document.createElement("div");
    sum.className = "src";
    const b = document.createElement("b");
    b.textContent = "Текущее саммари";
    sum.append(b, document.createTextNode(data.summary));
    step.append(sum);
  }
  for (const s of data.sources || []) {
    const src = document.createElement("div");
    src.className = "src";
    const b = document.createElement("b");
    const scoreStr = formatScore(Number(s.score));
    b.textContent = scoreStr ? `${s.doc} · ${scoreStr}` : s.doc;
    src.append(b, document.createTextNode(s.text));
    step.append(src);
  }
  return step;
}

export function renderSidebar(container, sessions, activeId, onSelect, onDelete) {
  container.innerHTML = "";
  for (const s of sessions) {
    const row = document.createElement("div");
    row.className = "chat-row" + (s.id === activeId ? " active" : "");

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chat-item";
    btn.title = s.title;
    const span = document.createElement("span");
    span.className = "chat-item-title";
    span.textContent = s.title;
    btn.append(span);
    btn.addEventListener("click", () => onSelect(s.id));

    row.append(btn);
    if (onDelete) {
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "chat-delete-btn";
      delBtn.title = "Удалить чат";
      delBtn.setAttribute("aria-label", "Удалить чат");
      delBtn.textContent = "×";
      delBtn.addEventListener("click", e => {
        e.stopPropagation();
        onDelete(s.id);
      });
      row.append(delBtn);
    }
    container.append(row);
  }
}

