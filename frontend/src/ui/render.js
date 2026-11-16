import { renderMarkdown } from "../utils/markdown.js";

const AVATAR = '<div class="avatar"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"><path d="M4 5h16v11H10l-4 4v-4H4z"/><path d="M12 8.2l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z" fill="#FF0032" stroke="#FF0032" stroke-width="1"/></svg></div>';

export const STARTERS = [
  "Как снизить счета за электроэнергию?",
  "Нужен автоматизированный учёт электроэнергии",
  "Хочу построить солнечную станцию",
  "Как найти потери электроэнергии?",
];

export function createMessageElement(role, text, meta = "") {
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

export function createChipsElement(onSelect) {
  const box = document.createElement("div");
  box.className = "chips";
  box.id = "chips";
  for (const q of STARTERS) {
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
  step.innerHTML = `<span class="tag"></span><p></p>
    <div class="times">
      <span>Поиск</span><span>${t.retrieval_ms ?? "-"} мс</span>
      <span>Реранкер</span><span>${t.rerank_ms ?? "-"} мс</span>
      <span>Модель</span><span>${t.llm_ms ?? "-"} мс</span>
      <b>Всего</b><b>${t.total_ms ?? "-"} мс</b>
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
    b.textContent = `${s.doc} · ${Number(s.score).toFixed(2)}`;
    src.append(b, document.createTextNode(s.text));
    step.append(src);
  }
  return step;
}

export function renderSidebar(container, sessions, activeId, onSelect) {
  container.innerHTML = "";
  for (const s of sessions) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chat-item" + (s.id === activeId ? " active" : "");
    btn.title = s.title;
    const span = document.createElement("span");
    span.className = "chat-item-title";
    span.textContent = s.title;
    btn.append(span);
    btn.addEventListener("click", () => onSelect(s.id));
    container.append(btn);
  }
}

