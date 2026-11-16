import {
  createChat,
  createProfile,
  deleteChat,
  getOperatorChat,
  resetMockTurn,
  sendMessage,
} from "./api/client.js?v=14";
import { pickRandomStarters } from "./data/starters.js?v=14";
import { SessionStore } from "./state/sessions.js?v=14";
import {
  createChipsElement,
  createDebugStepElement,
  createLeadDoneElement,
  createLeadFormElement,
  createMessageElement,
  createTypingElement,
  renderSidebar,
} from "./ui/render.js?v=14";

const $ = id => document.getElementById(id);
const store = new SessionStore();
let busy = false;
let unloading = false;
let syncTimer = null;

function clearSyncTimer() {
  if (syncTimer) {
    clearTimeout(syncTimer);
    syncTimer = null;
  }
}

async function syncSessionFromServer(sessionId, retriesLeft = 100) {
  clearSyncTimer();
  const session = store.getAll().find(s => s.id === sessionId);
  if (!session?.chatId || busy) return;
  try {
    const detail = await getOperatorChat(session.chatId);
    if (!detail) return;
    let changed = store.syncFromServer(sessionId, detail);

    const msgs = detail.messages || [];
    const last = msgs[msgs.length - 1];
    const lastTs = last?.created_at ? Date.parse(last.created_at) : 0;
    const isFreshUserMsg = last?.author === "user" && (!lastTs || Date.now() - lastTs < 260_000);

    if (isFreshUserMsg && !store.isPending(session)) {
      store.setPending(sessionId, true);
      changed = true;
    } else if (last?.author !== "user" && store.isPending(session)) {
      store.setPending(sessionId, false);
      changed = true;
    }

    if (changed && store.activeId === sessionId) {
      renderActiveSession();
    }
    if (retriesLeft > 0 && isFreshUserMsg && store.activeId === sessionId && !busy) {
      syncTimer = setTimeout(() => syncSessionFromServer(sessionId, retriesLeft - 1), 2500);
    }
  } catch {
    // Ignore transient sync errors (e.g. deleted or offline chat)
  }
}

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
  const userSessionId = store.getUserSessionId();
  return async lead => {
    const session = store.getAll().find(s => s.id === sessionId);
    await createProfile(userSessionId, lead, session?.chatId || null);
    store.markLeadSubmitted();
  };
}

function selectSession(id) {
  if (busy || id === store.activeId) return;
  store.select(id);
  renderActiveSession();
  syncSessionFromServer(id);
  $("input").focus();
}

async function removeSession(id) {
  if (busy) return;
  const target = store.getAll().find(s => s.id === id);
  if (target?.chatId) {
    try {
      await deleteChat(target.chatId);
    } catch (err) {
      console.error("Ошибка удаления чата на сервере:", err);
      return;
    }
  }
  store.deleteSession(id);
  renderActiveSession();
  $("input").focus();
}

function renderActiveSession() {
  const session = store.getActive();
  const messagesEl = $("messages");
  const debugListEl = $("debugList");

  messagesEl.innerHTML = "";
  if (!session.hasUserMessage && !session.offerLead && !session.leadSubmitted) {
    if (!Array.isArray(session.starters) || session.starters.length !== 4) {
      session.starters = pickRandomStarters(4);
      store.persist();
    }
    messagesEl.append(createChipsElement(submitStarter, session.starters));
  } else {
    for (const msg of session.messages) {
      messagesEl.append(createMessageElement(msg.role, msg.text, msg.meta, msg.sources || []));
    }
    if (session.leadSubmitted) {
      messagesEl.append(createLeadDoneElement());
    } else if (session.offerLead) {
      messagesEl.append(createLeadFormElement(submitLeadForSession(session.id)));
    }
    if (!busy && store.isPending(session)) {
      messagesEl.append(createTypingElement());
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

  renderSidebar($("chatList"), store.getAll(), session.id, selectSession, removeSession);

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

  clearSyncTimer();
  busy = true;
  $("sendBtn").disabled = true;
  $("input").value = "";
  $("chips")?.remove();

  store.addMessage("user", text);
  store.setPending(sessionId, true);
  $("messages").append(createMessageElement("user", text));
  if (wasFirstMessage) {
    renderSidebar($("chatList"), store.getAll(), sessionId, selectSession, removeSession);
  }

  const typing = createTypingElement();
  $("messages").append(typing);
  scrollMessagesToBottom();

  try {
    let chatId = session.chatId;
    if (!chatId) {
      chatId = await createChat(store.getUserSessionId());
      store.setChatId(sessionId, chatId);
    }

    const data = await sendMessage(chatId, text);
    store.setPending(sessionId, false);
    typing.remove();
    const t = data.timings?.total_ms;
    const meta = $("debugToggle").checked && t ? `${(t / 1000).toFixed(1)} с` : "";
    const sources = data.sources || [];
    store.addMessage("assistant", data.answer, meta, sources);
    $("messages").append(createMessageElement("assistant", data.answer, meta, sources));

    store.addDebug(text, data);
    const debugListEl = $("debugList");
    if (debugListEl.querySelector(".empty")) debugListEl.innerHTML = "";
    debugListEl.prepend(createDebugStepElement(text, data));

    if (data.action === "offer_contact" && !session.offerLead && !session.leadSubmitted) {
      store.setOfferLead(true);
      $("messages").append(createLeadFormElement(submitLeadForSession(sessionId)));
    }
    scrollMessagesToBottom();
  } catch (err) {
    if (unloading) return;
    store.setPending(sessionId, false);
    console.error("Ошибка отправки сообщения:", err);
    typing.remove();
    const errText = "Не получилось получить ответ. Попробуйте ещё раз.";
    store.addMessage("assistant", errText, "", [], true);
    $("messages").append(createMessageElement("assistant", errText));
    scrollMessagesToBottom();
  } finally {
    if (!unloading) {
      busy = false;
      $("sendBtn").disabled = false;
      renderSidebar($("chatList"), store.getAll(), store.activeId, selectSession, removeSession);
      $("input").focus();
    }
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
window.addEventListener("pagehide", () => {
  unloading = true;
});
window.addEventListener("pageshow", () => {
  unloading = false;
  renderActiveSession();
  syncSessionFromServer(store.activeId);
});

renderActiveSession();
syncSessionFromServer(store.activeId);
