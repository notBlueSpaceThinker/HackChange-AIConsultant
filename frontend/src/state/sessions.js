const STORAGE_KEY = "energytool_sessions_v1";
const ACTIVE_KEY = "energytool_active_session_v1";

export const WELCOME_TEXT = "Здравствуйте! Я консультант Energytool. Расскажите, какую задачу хотите решить: снизить счета, наладить учёт, найти потери?";

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
    title: "Новый диалог",
    hasUserMessage: false,
    messages: [],
    debugSteps: [],
    offerLead: false,
    leadSubmitted: false,
    createdAt: now,
    updatedAt: now,
  };
}

export class SessionStore {
  constructor() {
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

  addMessage(role, text, meta = "") {
    const session = this.getActive();
    if (role === "user" && !session.hasUserMessage) {
      session.hasUserMessage = true;
      session.title = text.trim().replace(/\s+/g, " ") || "Новый диалог";
    }
    session.messages.push({ role, text, meta });
    session.updatedAt = Date.now();
    this.persist();
  }

  addDebug(question, data) {
    const session = this.getActive();
    session.debugSteps.unshift({ question, data });
    session.updatedAt = Date.now();
    this.persist();
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
}

