import { resetMockTurn, sendLead, sendMessage } from "./api/client.js";
import { SessionStore } from "./state/sessions.js";
import {
  createChipsElement,
  createDebugStepElement,
  createLeadDoneElement,
  createLeadFormElement,
  createMessageElement,
  createTypingElement,
  renderSidebar,
} from "./ui/render.js";

const $ = id => document.getElementById(id);
const store = new SessionStore();
let busy = false;

function scrollMessagesToBottom() {
  const box = $("messages");
  box.scrollTop = box.scrollHeight;
}

function submitStarter(query) {
  if (busy) return;
  $("input").value = query;
  $("sendForm").requestSubmit();
}

function submitLeadForSession(sessionId) {
  return async lead => {
    await sendLead(sessionId, lead);
    store.markLeadSubmitted();
  };
}

function selectSession(id) {
  if (busy || id === store.activeId) return;
  store.select(id);
  renderActiveSession();
  $("input").focus();
}

function renderActiveSession() {
  const session = store.getActive();
  const messagesEl = $("messages");
  const debugListEl = $("debugList");

  messagesEl.innerHTML = "";
  if (!session.hasUserMessage) {
    messagesEl.append(createChipsElement(submitStarter));
  } else {
    for (const msg of session.messages) {
      messagesEl.append(createMessageElement(msg.role, msg.text, msg.meta));
    }
    if (session.leadSubmitted) {
      messagesEl.append(createLeadDoneElement());
    } else if (session.offerLead) {
      messagesEl.append(createLeadFormElement(submitLeadForSession(session.id)));
    }
  }

  debugListEl.innerHTML = "";
  if (session.debugSteps.length === 0) {
    debugListEl.innerHTML = '<p class="empty">Здесь появятся время ответа и документы базы знаний.</p>';
  } else {
    for (const step of session.debugSteps) {
      debugListEl.append(createDebugStepElement(step.question, step.data));
    }
  }

  renderSidebar($("chatList"), store.getAll(), session.id, selectSession);

  scrollMessagesToBottom();
}

function startNewDialog() {
  if (busy) return;
  resetMockTurn();
  store.createNew();
  renderActiveSession();
  $("input").focus();
}

$("sendForm").addEventListener("submit", async e => {
  e.preventDefault();
  const text = $("input").value.trim();
  if (!text || busy) return;

  const session = store.getActive();
  const sessionId = session.id;
  const wasFirstMessage = !session.hasUserMessage;

  busy = true;
  $("sendBtn").disabled = true;
  $("input").value = "";
  $("chips")?.remove();

  store.addMessage("user", text);
  $("messages").append(createMessageElement("user", text));
  if (wasFirstMessage) {
    renderSidebar($("chatList"), store.getAll(), sessionId, selectSession);
  }

  const typing = createTypingElement();
  $("messages").append(typing);
  scrollMessagesToBottom();

  try {
    const data = await sendMessage(sessionId, text);
    typing.remove();
    const t = data.timings?.total_ms;
    const meta = $("debugToggle").checked && t ? `${(t / 1000).toFixed(1)} с` : "";
    store.addMessage("assistant", data.answer, meta);
    $("messages").append(createMessageElement("assistant", data.answer, meta));

    store.addDebug(text, data);
    const debugListEl = $("debugList");
    if (debugListEl.querySelector(".empty")) debugListEl.innerHTML = "";
    debugListEl.prepend(createDebugStepElement(text, data));

    if (data.action === "offer_contact") {
      store.setOfferLead(true);
      $("messages").append(createLeadFormElement(submitLeadForSession(sessionId)));
    }
    scrollMessagesToBottom();
  } catch {
    typing.remove();
    const errText = "Не получилось получить ответ. Попробуйте ещё раз.";
    store.addMessage("assistant", errText);
    $("messages").append(createMessageElement("assistant", errText));
    scrollMessagesToBottom();
  } finally {
    busy = false;
    $("sendBtn").disabled = false;
    renderSidebar($("chatList"), store.getAll(), store.activeId, selectSession);
    $("input").focus();
  }
});

$("input").addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("sendForm").requestSubmit();
  }
});

$("newDialog").addEventListener("click", startNewDialog);
$("debugToggle").addEventListener("change", e => $("debug").classList.toggle("on", e.target.checked));

renderActiveSession();
