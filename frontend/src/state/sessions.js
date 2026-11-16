import { mapSources } from "../api/client.js?v=14";
import { pickRandomStarters } from "../data/starters.js?v=14";

const STORAGE_KEY = "energytool_sessions_v1";
const ACTIVE_KEY = "energytool_active_session_v1";
const USER_SESSION_KEY = "energytool_user_session_v1";

export const WELCOME_TEXT = "Здравствуйте! Я консультант Energytool. Расскажите, какую задачу хотите решить: снизить счета, наладить учёт, найти потери?";

function loadUserSessionId() {
  let id = localStorage.getItem(USER_SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(USER_SESSION_KEY, id);
  }
  return id;
}

function loadSessions() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function saveSessions(sessions) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
}

function createEmptySession() {
  const now = Date.now();
  return {
    id: crypto.randomUUID(),
    chatId: null,
    title: "Новый диалог",
    hasUserMessage: false,
    starters: pickRandomStarters(4),
    messages: [],
    debugSteps: [],
    offerLead: false,
    leadSubmitted: false,
    pendingUntil: 0,
    createdAt: now,
    updatedAt: now,
  };
}

export class SessionStore {
  constructor() {
    this.userSessionId = loadUserSessionId();
    this.sessions = loadSessions();
    const savedActive = localStorage.getItem(ACTIVE_KEY);
    if (this.sessions.length === 0) {
      const fresh = createEmptySession();
      this.sessions.unshift(fresh);
      this.activeId = fresh.id;
      this.persist();
    } else if (savedActive && this.sessions.some(s => s.id === savedActive)) {
      this.activeId = savedActive;
    } else {
      this.activeId = this.sessions[0].id;
    }
  }

  getUserSessionId() {
    return this.userSessionId;
  }

  persist() {
    saveSessions(this.sessions);
    localStorage.setItem(ACTIVE_KEY, this.activeId);
  }

  getActive() {
    return this.sessions.find(s => s.id === this.activeId) || this.sessions[0];
  }

  getAll() {
    return this.sessions;
  }

  createNew() {
    const current = this.getActive();
    // Reuse current empty session instead of piling up blank "Новый диалог" items
    if (current && !current.hasUserMessage) {
      return current;
    }
    const fresh = createEmptySession();
    this.sessions.unshift(fresh);
    this.activeId = fresh.id;
    this.persist();
    return fresh;
  }

  select(id) {
    if (this.sessions.some(s => s.id === id)) {
      this.activeId = id;
      this.persist();
    }
    return this.getActive();
  }

  deleteSession(id) {
    const idx = this.sessions.findIndex(s => s.id === id);
    if (idx === -1) return this.getActive();
    this.sessions.splice(idx, 1);
    if (this.sessions.length === 0) {
      const fresh = createEmptySession();
      this.sessions.unshift(fresh);
      this.activeId = fresh.id;
    } else if (this.activeId === id) {
      const nextIdx = Math.min(idx, this.sessions.length - 1);
      this.activeId = this.sessions[nextIdx].id;
    }
    this.persist();
    return this.getActive();
  }

  addMessage(role, text, meta = "", sources = [], isError = false) {
    const session = this.getActive();
    if (role === "user" && !session.hasUserMessage) {
      session.hasUserMessage = true;
      session.title = text.trim().replace(/\s+/g, " ") || "Новый диалог";
    }
    const entry = { role, text, meta };
    if (Array.isArray(sources) && sources.length > 0) {
      entry.sources = sources;
    }
    if (isError) {
      entry.isError = true;
    }
    session.messages.push(entry);
    session.updatedAt = Date.now();
    this.persist();
  }

  addDebug(question, data) {
    const session = this.getActive();
    session.debugSteps.unshift({ question, data });
    session.updatedAt = Date.now();
    this.persist();
  }

  setChatId(sessionId, chatId) {
    const session = this.sessions.find(s => s.id === sessionId);
    if (session) {
      session.chatId = chatId;
      session.updatedAt = Date.now();
      this.persist();
    }
  }

  setOfferLead(flag) {
    const session = this.getActive();
    session.offerLead = flag;
    this.persist();
  }

  markLeadSubmitted() {
    const session = this.getActive();
    session.offerLead = false;
    session.leadSubmitted = true;
    session.updatedAt = Date.now();
    this.persist();
  }

  setPending(sessionId, active) {
    const session = this.sessions.find(s => s.id === sessionId);
    if (!session) return;
    session.pendingUntil = active ? Date.now() + 260_000 : 0;
    this.persist();
  }

  isPending(session) {
    return Boolean(session?.pendingUntil && session.pendingUntil > Date.now());
  }

  syncFromServer(sessionId, detail) {
    const session = this.sessions.find(s => s.id === sessionId);
    if (!session || !detail) return false;
    let changed = false;
    const serverMsgs = Array.isArray(detail.messages) ? detail.messages : [];
    const errText = "Не получилось получить ответ. Попробуйте ещё раз.";
    const localReal = session.messages.filter(
      m => !m.isError && !(m.role === "assistant" && m.text === errText)
    );

    const needsMsgSync = serverMsgs.length > localReal.length
      || (serverMsgs.length > 0 && localReal.length !== session.messages.length && serverMsgs.length >= localReal.length);

    if (needsMsgSync && serverMsgs.length > 0) {
      const merged = serverMsgs.map((m, idx) => {
        const role = m.author === "user" ? "user" : "assistant";
        const existing = localReal[idx];
        if (existing && existing.role === role && existing.text === m.message) {
          return existing;
        }
        const matched = localReal.find(x => x.role === role && x.text === m.message && x.sources?.length);
        if (matched) return matched;
        return { role, text: m.message, meta: "", sources: mapSources(m.sources) };
      });
      session.messages = merged;
      const firstUser = merged.find(m => m.role === "user");
      if (firstUser) {
        session.hasUserMessage = true;
        session.title = firstUser.text.trim().replace(/\s+/g, " ") || session.title;
      }
      changed = true;
    }

    const lastServer = serverMsgs[serverMsgs.length - 1];
    if (lastServer?.author === "assistant" && session.pendingUntil) {
      session.pendingUntil = 0;
      changed = true;
    }

    if (detail.has_lead && !session.leadSubmitted) {
      session.offerLead = false;
      session.leadSubmitted = true;
      changed = true;
    }
    if (changed) {
      session.updatedAt = Date.now();
      this.persist();
    }
    return changed;
  }
}

