(() => {
  const tg = window.Telegram && window.Telegram.WebApp;

  function applyTelegramTheme() {
    /* ASF keeps its foundry identity; Telegram only hosts the WebApp. */
  }

  function haptic(style) {
    try {
      if (tg && tg.HapticFeedback) tg.HapticFeedback.impactOccurred(style || "light");
    } catch (_) {
      /* haptic optional */
    }
  }

  function xp(event, extra) {
    if (window.ASFExperience && typeof window.ASFExperience.emit === "function") {
      window.ASFExperience.emit(event, extra);
    }
  }

  function inTelegramWebView() {
    if (!tg) return false;
    if (tg.initData) return true;
    if (tg.platform && tg.platform !== "unknown") return true;
    return /Telegram/i.test(navigator.userAgent || "");
  }

  function enterTelegramFullscreen() {
    if (!tg) return;
    try {
      tg.ready();
    } catch (_) {
      /* ready optional */
    }
    try {
      tg.expand();
    } catch (_) {
      /* expand optional */
    }
    try {
      if (typeof tg.disableVerticalSwipes === "function") tg.disableVerticalSwipes();
    } catch (_) {
      /* older clients */
    }
    try {
      if (typeof tg.setHeaderColor === "function") tg.setHeaderColor("#07060b");
      if (typeof tg.setBackgroundColor === "function") tg.setBackgroundColor("#07060b");
      if (typeof tg.setBottomBarColor === "function") tg.setBottomBarColor("#07060b");
    } catch (_) {
      /* theme optional */
    }
    try {
      if (!tg.isFullscreen && typeof tg.requestFullscreen === "function") {
        tg.requestFullscreen();
      }
    } catch (_) {
      /* desktop / old clients keep expanded sheet */
    }
  }

  if (tg) {
    enterTelegramFullscreen();
    try {
      applyTelegramTheme();
    } catch (_) {
      /* theme optional */
    }
    document.addEventListener("pointerdown", enterTelegramFullscreen, {
      once: true,
      capture: true,
    });
  }

  if (window.ASFFoundry) {
    window.ASFFoundry.startField(document.getElementById("foundry-field"));
  }

  const params = new URLSearchParams(window.location.search);
  const userId = String(
    (tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id) ||
      params.get("uid") ||
      ""
  );

  const state = {
    mode: "home",
    listMode: "change",
    projectId: null,
    wsRequestId: 0,
    wsAbort: null,
    recording: false,
    mediaRecorder: null,
    recognition: null,
    voiceMode: null, // "speech" | "media"
    chunks: [],
    webSpeechDisabled: false,
    speechGotResult: false,
    selectedIds: new Set(),
    choiceItems: [],
    allowMultiple: false,
    sending: false,
    exportRetry: null,
    recorderExt: "webm",
    recordingStartedAt: 0,
    welcomePending: false,
    tzAvailable: false,
    wsMessages: [],
    micStream: null,
    micConstraints: null,
  };

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition || null;

  /** Web Speech is unreliable in Telegram WebView вЂ” record + Groq instead. */
  function canUseWebSpeech() {
    if (state.webSpeechDisabled) return false;
    if (inTelegramWebView()) return false;
    if (!SpeechRecognition) return false;
    if (!window.isSecureContext) return false;
    const ua = navigator.userAgent || "";
    if (/iPhone|iPad|iPod/i.test(ua)) return false;
    return true;
  }

  function pickRecorderMime() {
    const fallback = { mime: "", ext: "webm" };
    if (typeof MediaRecorder === "undefined") return fallback;
    const candidates = [
      ["audio/webm;codecs=opus", "webm"],
      ["audio/webm", "webm"],
      ["audio/mp4", "mp4"],
      ["audio/aac", "m4a"],
      ["audio/ogg;codecs=opus", "ogg"],
      ["audio/ogg", "ogg"],
      ["audio/wav", "wav"],
    ];
    if (typeof MediaRecorder.isTypeSupported !== "function") return fallback;
    for (let i = 0; i < candidates.length; i += 1) {
      const mime = candidates[i][0];
      const ext = candidates[i][1];
      try {
        if (MediaRecorder.isTypeSupported(mime)) return { mime, ext };
      } catch (_) {
        /* skip */
      }
    }
    return fallback;
  }

  const $ = (id) => document.getElementById(id);
  const views = {
    home: $("view-home"),
    create: $("view-create"),
    list: $("view-list"),
    workspace: $("view-workspace"),
    settings: $("view-settings"),
  };

  /* OWNER_CONTACT_TELEGRAM РёР· env РЅРµ РїСЂРѕРєРёРЅСѓС‚ РІ СЃС‚Р°С‚РёРєСѓ Mini App вЂ” РЅРµ РІС‹РґСѓРјС‹РІР°С‚СЊ @. */
  const OWNER_CONTACT_TELEGRAM = "@trender023";

  function show(name) {
    Object.entries(views).forEach(([key, el]) => {
      el.classList.toggle("hidden", key !== name);
    });
    state.mode = name;
    const isWs = name === "workspace";
    const appEl = $("app");
    if (appEl) {
      appEl.classList.toggle("is-workspace", isWs);
      if (!isWs) appEl.classList.remove("welcome-pending");
    }
    if (!isWs) closeWelcomeModal();
    document.documentElement.classList.toggle("asf-workspace", isWs);
    document.body.classList.toggle("asf-workspace", isWs);
    syncViewportHeight();
  }

  function syncViewportHeight() {
    const root = document.documentElement;
    const vv = window.visualViewport;
    const tgH = tg && (tg.viewportStableHeight || tg.viewportHeight);
    const candidates = [];
    if (vv && vv.height) candidates.push(vv.height);
    if (tgH) candidates.push(tgH);
    if (window.innerHeight) candidates.push(window.innerHeight);
    const h = candidates.length ? Math.round(Math.min.apply(null, candidates)) : 0;
    if (h) {
      root.style.setProperty("--app-vh", `${h}px`);
    }
    const safe = (tg && tg.safeAreaInset) || {};
    const content = (tg && tg.contentSafeAreaInset) || {};
    root.style.setProperty(
      "--safe-top",
      `${(Number(safe.top) || 0) + (Number(content.top) || 0)}px`
    );
    root.style.setProperty(
      "--safe-bottom",
      `${(Number(safe.bottom) || 0) + (Number(content.bottom) || 0)}px`
    );
    root.style.setProperty("--safe-left", `${Number(safe.left) || Number(content.left) || 0}px`);
    root.style.setProperty("--safe-right", `${Number(safe.right) || Number(content.right) || 0}px`);
  }

  function apiBase() {
    return "";
  }

  async function api(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body && !(options.body instanceof FormData) && !headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
    const res = await fetch(`${apiBase()}${path}`, {
      ...options,
      headers,
    });
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = { detail: text };
    }
    if (!res.ok) {
      const detail = (data && data.detail) || res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  }

  function requireUser() {
    if (!userId) {
      alert(
        "РќРµ СѓРґР°Р»РѕСЃСЊ РѕРїСЂРµРґРµР»РёС‚СЊ Telegram user id. РћС‚РєСЂРѕР№С‚Рµ Mini App РёР· Р±РѕС‚Р° РёР»Рё РґРѕР±Р°РІСЊС‚Рµ ?uid=YOUR_ID"
      );
      return false;
    }
    return true;
  }

  const HOME_ACTIONS = {
    empty: ["create"],
    withProject: ["create", "change"],
    withMvpReview: ["create", "change", "feedback"],
  };

  function homeActionsFromProjects(projects) {
    const list = Array.isArray(projects) ? projects : [];
    if (!list.length) return HOME_ACTIONS.empty.slice();
    const hasReview = list.some((p) => Boolean(p && p.mvp_review_sent));
    return (hasReview ? HOME_ACTIONS.withMvpReview : HOME_ACTIONS.withProject).slice();
  }

  function applyHomeActions(projects) {
    const allowed = new Set(homeActionsFromProjects(projects));
    document.querySelectorAll("[data-action]").forEach((btn) => {
      const action = btn.getAttribute("data-action");
      const showBtn = allowed.has(action);
      btn.classList.toggle("hidden", !showBtn);
      btn.setAttribute("aria-hidden", showBtn ? "false" : "true");
    });
  }

  async function refreshHome() {
    show("home");
    if (!userId) {
      applyHomeActions([]);
      return;
    }
    try {
      const projects = await api(
        `/projects?customer_telegram_id=${encodeURIComponent(userId)}`
      );
      applyHomeActions(projects);
    } catch (err) {
      applyHomeActions([]);
    }
  }

  const settingsBtn = $("btn-settings");
  if (settingsBtn) {
    settingsBtn.addEventListener("click", () => {
      haptic("light");
      abortWorkspaceLoad();
      fillSettings();
      show("settings");
    });
  }

  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      haptic("light");
      abortWorkspaceLoad();
      const action = btn.getAttribute("data-action");
      if (action === "create") {
        show("create");
        return;
      }
      state.listMode = action === "feedback" ? "feedback" : "change";
      $("list-title").textContent =
        state.listMode === "feedback" ? "Р—Р°РјРµС‡Р°РЅРёСЏ Рє СЂРµР°Р»РёР·Р°С†РёРё" : "РР·РјРµРЅРёС‚СЊ РїСЂРѕРµРєС‚";
      loadProjects();
    });
  });

  function isAbortError(err) {
    if (!err) return false;
    if (err.name === "AbortError") return true;
    const msg = String(err.message || err);
    return msg === "The user aborted a request." || /aborted/i.test(msg);
  }

  function abortWorkspaceLoad() {
    state.wsRequestId += 1;
    if (state.wsAbort) {
      try {
        state.wsAbort.abort();
      } catch (_) {
        /* already aborted */
      }
      state.wsAbort = null;
    }
  }

  const CUSTOMER_STATUS_HUD_RU = {
    NEW: "СѓС‚РѕС‡РЅСЏРµРј РёРґРµСЋ",
    INTERVIEW: "Р¶РґС‘Рј РІР°С€ РѕС‚РІРµС‚",
    ANALYZING: "СЃРѕР±РёСЂР°РµРј С‡РµСЂРЅРѕРІРёРє",
    WAITING_CUSTOMER: "Р¶РґС‘Рј РІР°С€ РѕС‚РІРµС‚",
    WAITING_OWNER: "РЅР° СЂРµРІСЊСЋ Сѓ РІР»Р°РґРµР»СЊС†Р°",
    WAITING_CLIENT_ESTIMATE: "СЃРјРѕС‚СЂРёС‚Рµ СЃРјРµС‚Сѓ",
    READY: "РјРѕР¶РЅРѕ СЃРѕР±РёСЂР°С‚СЊ MVP",
    ARCHIVED: "РїСЂРѕРµРєС‚ Р·Р°РєСЂС‹С‚",
  };
  const CUSTOMER_STAGE_HUD_RU = {
    PROJECT_CREATED: "СѓС‚РѕС‡РЅСЏРµРј РёРґРµСЋ",
    UNDERSTANDING_IDEA: "СѓС‚РѕС‡РЅСЏРµРј РёРґРµСЋ",
    BUSINESS_CONTEXT: "СѓС‚РѕС‡РЅСЏРµРј Р·Р°РґР°С‡Сѓ",
    USERS: "РєС‚Рѕ Р±СѓРґРµС‚ РїРѕР»СЊР·РѕРІР°С‚СЊСЃСЏ",
    FUNCTIONAL: "С‡С‚Рѕ РґРѕР»Р¶РЅРѕ СѓРјРµС‚СЊ",
    DATA: "РєР°РєРёРµ РґР°РЅРЅС‹Рµ РЅСѓР¶РЅС‹",
    NON_FUNCTIONAL: "РєР°Рє РґРѕР»Р¶РЅРѕ СЂР°Р±РѕС‚Р°С‚СЊ",
    INTEGRATIONS: "РєР°РєРёРµ СЃРІСЏР·Рё СЃ РґСЂСѓРіРёРјРё СЃРёСЃС‚РµРјР°РјРё",
    ACCEPTANCE: "РєР°Рє РїСЂРёРјРµРј СЂР°Р±РѕС‚Сѓ",
    RISKS: "СЂРёСЃРєРё Рё РѕРіСЂР°РЅРёС‡РµРЅРёСЏ",
    REVIEW: "РїСЂРѕРІРµСЂСЏРµРј С‡РµСЂРЅРѕРІРёРє",
    READY_FOR_OWNER: "РЅР° СЂРµРІСЊСЋ Сѓ РІР»Р°РґРµР»СЊС†Р°",
  };
  const HOLD_STATUS_HUD = {
    WAITING_OWNER: true,
    WAITING_CLIENT_ESTIMATE: true,
    READY: true,
    ARCHIVED: true,
    ANALYZING: true,
  };

  function hudKey(value) {
    return String(value || "")
      .trim()
      .toUpperCase()
      .replace(/[\s-]+/g, "_");
  }

  function customerWorkspaceHud(status, stage, paused, serverHud) {
    const ready = String(serverHud || "").trim();
    if (ready && !/[_]|^(create|change|feedback)$/i.test(ready)) {
      const looksEnglishEnum = /^[A-Z][A-Z0-9_]+$/.test(ready);
      if (!looksEnglishEnum) return ready;
    }
    if (paused) return "РЅР° РїР°СѓР·Рµ";
    const statusKey = hudKey(status);
    if (HOLD_STATUS_HUD[statusKey] && CUSTOMER_STATUS_HUD_RU[statusKey]) {
      return CUSTOMER_STATUS_HUD_RU[statusKey];
    }
    const stageKey = hudKey(stage);
    if (CUSTOMER_STAGE_HUD_RU[stageKey]) return CUSTOMER_STAGE_HUD_RU[stageKey];
    if (CUSTOMER_STATUS_HUD_RU[statusKey]) return CUSTOMER_STATUS_HUD_RU[statusKey];
    return "РІ СЂР°Р±РѕС‚Рµ";
  }

  function formatProjectTitle(name) {
    const raw = String(name || "").trim();
    if (!raw) return "РџСЂРѕРµРєС‚";
    if (/^РїСЂРѕРµРєС‚\b/i.test(raw) || raw === "Р—Р°РіСЂСѓР·РєР°вЂ¦") return raw;
    return `РџСЂРѕРµРєС‚: ${raw}`;
  }

  function fillSettings() {
    const userEl = $("settings-tg-user");
    const tgEl = $("settings-owner-tg");
    const u = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
    if (userEl) {
      if (u) {
        const name = [u.first_name, u.last_name].filter(Boolean).join(" ");
        const handle = u.username ? `@${u.username}` : "";
        const id = u.id ? `id ${u.id}` : "";
        userEl.textContent = [name, handle, id].filter(Boolean).join(" В· ") || "вЂ”";
      } else if (userId) {
        userEl.textContent = `id ${userId}`;
      } else {
        userEl.textContent = "РЅРµ РѕРїСЂРµРґРµР»С‘РЅ вЂ” РѕС‚РєСЂРѕР№С‚Рµ РёР· Р±РѕС‚Р° РёР»Рё РґРѕР±Р°РІСЊС‚Рµ ?uid=";
      }
    }
    if (tgEl) {
      const handle = String(OWNER_CONTACT_TELEGRAM || "").trim();
      tgEl.textContent = handle || "РЅРµ Р·Р°РґР°РЅ";
    }
  }

  function resetWorkspaceDom(nameText, metaText) {
    $("ws-name").textContent = formatProjectTitle(nameText);
    $("ws-meta").textContent = metaText || "";
    renderProgress(null, false);
    renderThread([]);
    renderChoices([], false, false);
    showSendHint("");
    const box = $("composer-text");
    if (box) box.value = "";
    state.tzAvailable = false;
    renderClientEstimate(null, "");
  }

  document.querySelectorAll("[data-back]").forEach((btn) => {
    btn.addEventListener("click", () => {
      abortWorkspaceLoad();
      xp("idle");
      refreshHome();
    });
  });

  document.querySelector("[data-back-workspace]").addEventListener("click", () => {
    abortWorkspaceLoad();
    state.projectId = null;
    xp("idle");
    if (state.listMode === "create") refreshHome();
    else loadProjects();
  });

  $("create-submit").addEventListener("click", async () => {
    if (!requireUser()) return;
    const name = ($("create-name").value || "").trim() || `РџСЂРѕРµРєС‚ ${userId}`;
    const btn = $("create-submit");
    btn.disabled = true;
    try {
      const project = await api("/projects", {
        method: "POST",
        body: JSON.stringify({
          name,
          customer_telegram_id: userId,
        }),
      });
      const pid = project && (project.id || project.project_id);
      if (!pid) throw new Error("РџСЂРѕРµРєС‚ СЃРѕР·РґР°РЅ, РЅРѕ РЅРµ РїРѕР»СѓС‡РµРЅ id С‡Р°С‚Р°");
      $("create-name").value = "";
      state.listMode = "create";
      await openWorkspace(pid, "create");
    } catch (err) {
      xp("error");
      alert(err.message || String(err));
    } finally {
      btn.disabled = false;
    }
  });

  async function loadProjects() {
    if (!requireUser()) return;
    show("list");
    const list = $("project-list");
    const empty = $("list-empty");
    list.innerHTML = "";
    empty.textContent = "РџРѕРєР° РЅРµС‚ РїСЂРѕРµРєС‚РѕРІ.";
    try {
      const projects = await api(
        `/projects?customer_telegram_id=${encodeURIComponent(userId)}`
      );
      const visible =
        state.listMode === "feedback"
          ? projects.filter((p) => Boolean(p && p.mvp_review_sent))
          : projects;
      if (!visible.length) {
        empty.textContent =
          state.listMode === "feedback"
            ? "РџРѕРєР° РЅРµС‚ РїСЂРѕРµРєС‚РѕРІ СЃ MVP РЅР° РїСЂРѕРІРµСЂРєРµ."
            : "РџРѕРєР° РЅРµС‚ РїСЂРѕРµРєС‚РѕРІ.";
        empty.classList.remove("hidden");
        return;
      }
      empty.classList.add("hidden");
      visible.forEach((p) => {
        const li = document.createElement("li");
        li.className = "project-row";

        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "project-open";
        btn.innerHTML = `<div>${escapeHtml(p.name)}</div><div class="meta">${escapeHtml(
          customerWorkspaceHud(p.status, p.discovery_stage, false, p.customer_hud)
        )}</div>`;
        btn.addEventListener("click", () => openWorkspace(p.id, state.listMode));
        li.appendChild(btn);

        if (state.listMode === "change" || state.listMode === "feedback") {
          const del = document.createElement("button");
          del.type = "button";
          del.className = "icon-delete";
          del.title = "РЈРґР°Р»РёС‚СЊ РїСЂРѕРµРєС‚";
          del.setAttribute("aria-label", `РЈРґР°Р»РёС‚СЊ РїСЂРѕРµРєС‚ ${p.name}`);
          del.innerHTML =
            '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>';
          del.addEventListener("click", (ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            deleteProject(p);
          });
          li.appendChild(del);
        }

        list.appendChild(li);
      });
    } catch (err) {
      xp("error");
      empty.classList.remove("hidden");
      empty.textContent = err.message || String(err);
    }
  }

  async function deleteProject(project) {
    if (!requireUser()) return;
    const ok = window.confirm(
      `РЈРґР°Р»РёС‚СЊ РїСЂРѕРµРєС‚ В«${project.name}В»?\n\nР‘СѓРґСѓС‚ СѓРґР°Р»РµРЅС‹ РІСЃРµ СЃРѕРѕР±С‰РµРЅРёСЏ, С‚СЂРµР±РѕРІР°РЅРёСЏ Рё СЃРІСЏР·Р°РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ. Р­С‚Рѕ РЅРµР»СЊР·СЏ РѕС‚РјРµРЅРёС‚СЊ.`
    );
    if (!ok) return;
    try {
      const qs = new URLSearchParams({ customer_telegram_id: userId });
      await api(`/projects/${project.id}?${qs}`, { method: "DELETE" });
      if (state.projectId === project.id) {
        state.projectId = null;
      }
      await loadProjects();
    } catch (err) {
      xp("error");
      alert(err.message || String(err));
    }
  }

  async function openWorkspace(projectId, mode, afterEvent) {
    const pid = String(projectId || "");
    if (!pid) return;
    const keepThread =
      state.mode === "workspace" &&
      String(state.projectId) === pid &&
      Boolean(afterEvent);
    abortWorkspaceLoad();
    const requestId = state.wsRequestId;
    state.projectId = pid;
    if (mode === "create" || mode === "change" || mode === "feedback") {
      state.listMode = mode;
    }
    if (!keepThread) {
      resetWorkspaceDom("Р—Р°РіСЂСѓР·РєР°вЂ¦", "РћС‚РєСЂС‹РІР°СЋ С‡Р°С‚ СЌС‚РѕРіРѕ РїСЂРѕРµРєС‚Р°вЂ¦");
    }
    show("workspace");
    xp("thinking");
    const controller = new AbortController();
    state.wsAbort = controller;
    try {
      const qs = new URLSearchParams({
        mode,
        customer_telegram_id: userId,
      });
      const ws = await api(`/projects/${pid}/workspace?${qs}`, {
        signal: controller.signal,
      });
      if (requestId !== state.wsRequestId) return;
      if (String(ws.project_id) !== pid) return;
      $("ws-name").textContent = formatProjectTitle(ws.name);
      $("ws-meta").textContent = customerWorkspaceHud(
        ws.status,
        ws.discovery_stage,
        Boolean(ws.paused),
        ws.customer_hud
      );
      renderProgress(ws.discovery_progress, mode !== "feedback");
      state.tzAvailable = Boolean(ws.tz_available);
      applyWelcomeGate(ws.messages || [], mode);
      renderChoices(
        mode === "feedback" ? [] : ws.discovery_choices || [],
        Boolean(ws.paused) && mode !== "feedback",
        Boolean(ws.allow_multiple) && mode !== "feedback"
      );
      const placeholder =
        mode === "feedback"
          ? "Р§С‚Рѕ РёСЃРїСЂР°РІРёС‚СЊ РёР»Рё РґРѕР±Р°РІРёС‚СЊ РІ СЂРµР°Р»РёР·Р°С†РёРёвЂ¦"
          : (ws.discovery_choices || []).length
            ? "РћС‚РІРµС‚СЊС‚Рµ С‚РµРєСЃС‚РѕРј РёР»Рё РѕС‚РєСЂРѕР№С‚Рµ РІР°СЂРёР°РЅС‚С‹вЂ¦"
          : ws.status === "WAITING_CLIENT_ESTIMATE"
            ? "РЎРјРµС‚Р° РЅРёР¶Рµ вЂ” РїРѕРґС‚РІРµСЂРґРёС‚Рµ РёР»Рё РЅР°РїРёС€РёС‚Рµ, С‡С‚Рѕ РѕР±СЃСѓРґРёС‚СЊвЂ¦"
          : ws.status === "WAITING_OWNER" || ws.status === "READY"
            ? "РњРѕР¶РЅРѕ РґРѕР±Р°РІРёС‚СЊ СѓС‚РѕС‡РЅРµРЅРёРµвЂ¦"
            : "РћС‚РІРµС‚СЊС‚Рµ С‚РµРєСЃС‚РѕРј РёР»Рё РѕС‚РєСЂРѕР№С‚Рµ РІР°СЂРёР°РЅС‚С‹вЂ¦";
      $("composer-text").placeholder = placeholder;
      renderClientEstimate(ws.client_estimate, ws.status);
      if (ws.tz_available) xp("draft_ready");
      else if (afterEvent) xp(afterEvent);
      else xp("idle");
      scrollThreadToLatest();
    } catch (err) {
      if (isAbortError(err) || requestId !== state.wsRequestId) return;
      xp("error");
      alert(err.message || String(err));
      refreshHome();
    }
  }

  function renderProgress(progress, visible) {
    const bar = $("ws-progress");
    const fill = $("ws-progress-fill");
    const label = $("ws-progress-label");
    if (!bar || !fill || !label) return;
    if (!visible || !progress || !progress.total) {
      bar.classList.add("hidden");
      fill.style.width = "0%";
      label.textContent = "";
      bar.setAttribute("aria-valuenow", "0");
      return;
    }
    const total = Math.max(Number(progress.total) || 1, 1);
    const done = Math.min(Math.max(Number(progress.done) || 0, 0), total);
    const percent = Math.min(
      100,
      Math.max(0, Number(progress.percent != null ? progress.percent : Math.round((done / total) * 100)))
    );
    bar.classList.remove("hidden");
    fill.style.width = `${percent}%`;
    bar.setAttribute("aria-valuenow", String(percent));
    bar.setAttribute("aria-valuemax", "100");
    const remaining = Math.max(
      0,
      Number(progress.remaining != null ? progress.remaining : total - done)
    );
    if (progress.phase === "done" || percent >= 100) {
      label.textContent = "РЎР±РѕСЂ С‚СЂРµР±РѕРІР°РЅРёР№: РіРѕС‚РѕРІРѕ";
    } else if (remaining <= 3) {
      label.textContent = "Р•С‰С‘ РїР°СЂР° СѓС‚РѕС‡РЅРµРЅРёР№";
    } else {
      label.textContent = `РЎР±РѕСЂ С‚СЂРµР±РѕРІР°РЅРёР№: ${percent}%`;
    }
  }

  function isWelcomeMessage(m) {
    if (!m || m.role === "customer") return false;
    if (m.meta_kind === "welcome") return true;
    const t = String(m.text || "").toLowerCase();
    return t.includes("РґРѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ") && t.includes("СЃР±РѕСЂ С‚СЂРµР±РѕРІР°РЅРёР№");
  }

  function welcomeKey(pid) {
    return `asf-welcome-ok:${pid}`;
  }

  function welcomeDismissed(pid) {
    try {
      return Boolean(sessionStorage.getItem(welcomeKey(pid)));
    } catch (_) {
      return false;
    }
  }

  function markWelcomeDismissed(pid) {
    try {
      sessionStorage.setItem(welcomeKey(pid), "1");
    } catch (_) {
      /* private mode */
    }
  }

  function closeWelcomeModal() {
    const modal = $("welcome-modal");
    if (modal) modal.classList.add("hidden");
    const appEl = $("app");
    if (appEl) appEl.classList.remove("welcome-pending");
    state.welcomePending = false;
  }

  function applyWelcomeGate(messages, mode) {
    const list = Array.isArray(messages) ? messages : [];
    const welcome = list.find(isWelcomeMessage);
    const hasCustomer = list.some((m) => m.role === "customer");
    const hold =
      Boolean(welcome) &&
      !hasCustomer &&
      mode !== "feedback" &&
      !welcomeDismissed(state.projectId);
    state.wsMessages = list;
    state.welcomePending = hold;
    const appEl = $("app");
    if (appEl) appEl.classList.toggle("welcome-pending", hold);
    const modal = $("welcome-modal");
    const body = $("welcome-body");
    if (hold && modal && body && welcome) {
      body.textContent = welcome.text || "";
      modal.classList.remove("hidden");
      renderThread([]);
      return;
    }
    if (modal) modal.classList.add("hidden");
    renderThread(list);
  }

  function sortThreadMessages(messages) {
    return [...(messages || [])].sort((a, b) => {
      const ta = Date.parse(a.created_at || "") || 0;
      const tb = Date.parse(b.created_at || "") || 0;
      if (ta !== tb) return ta - tb;
      return String(a.id || "").localeCompare(String(b.id || ""));
    });
  }

  function visibleThreadMessages(messages) {
    const hold = Boolean(state.welcomePending);
    return sortThreadMessages(messages).filter((m) => {
      if (isWelcomeMessage(m)) return false;
      if (hold) return false;
      return true;
    });
  }

  function isTzDownloadMessage(m) {
    if (!m) return false;
    if (m.meta_kind === "tz_download" || m.meta_kind === "tz_updated") return true;
    const t = String(m.text || "").toLowerCase();
    if (!t.includes("С‡РµСЂРЅРѕРІРёРє")) return false;
    return (
      t.includes("СЃРєР°С‡Р°Р№С‚Рµ") ||
      t.includes("СЃРєР°С‡Р°С‚СЊ РµРіРѕ РјРѕР¶РЅРѕ") ||
      t.includes("РґРѕР±Р°РІР»РµРЅРѕ Рє РјР°С‚РµСЂРёР°Р»Р°Рј СЂРµРІСЊСЋ") ||
      t.includes("РѕР±РЅРѕРІР»С‘РЅ") ||
      t.includes("РѕР±РЅРѕРІР»РµРЅ") ||
      /РѕР±РЅРѕРІРёР»[Р°Рё]?\s+С‡РµСЂРЅРѕРІРёРє/.test(t)
    );
  }

  function tzCardTitle(m) {
    if (m && m.meta_kind === "tz_updated") return "РўР— РѕР±РЅРѕРІРёР»РѕСЃСЊ";
    return "РўР— РіРѕС‚РѕРІРѕ";
  }

  function tzCardLead() {
    return "РљРёРЅСѓС‚СЊ РІ С‡Р°С‚ Р±РѕС‚Р°";
  }

  function appendTzFormatButtons(host) {
    const row = document.createElement("div");
    row.className = "tz-download-row";
    [
      ["md", "Markdown", false],
      ["docx", "Word", false],
      ["pdf", "PDF", true],
    ].forEach(([fmt, label, primary]) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = primary ? "btn primary" : "btn";
      btn.setAttribute("data-tz-fmt", fmt);
      btn.textContent = label;
      row.appendChild(btn);
    });
    host.appendChild(row);
  }

  function renderTzCard(thread, m, latest) {
    const div = document.createElement("div");
    div.className = "bubble assistant tz-card";
    if (latest) div.classList.add("latest");
    div.setAttribute("data-tz-card", m && m.id ? "message" : "synthetic");
    if (m && m.id) div.setAttribute("data-tz-msg", String(m.id));
    const title = document.createElement("p");
    title.className = "tz-download-title";
    title.textContent = tzCardTitle(m);
    div.appendChild(title);
    const lead = document.createElement("p");
    lead.className = "tz-download-lead";
    lead.textContent = tzCardLead();
    div.appendChild(lead);
    appendTzFormatButtons(div);
    thread.appendChild(div);
  }

  function renderThread(messages) {
    const thread = $("thread");
    thread.innerHTML = "";
    const rows = visibleThreadMessages(messages);
    let cards = 0;
    rows.forEach((m, idx) => {
      const latest = idx === rows.length - 1;
      if (state.tzAvailable && isTzDownloadMessage(m)) {
        cards += 1;
        renderTzCard(thread, m, latest);
        return;
      }
      const div = document.createElement("div");
      const role = m.role === "customer" ? "customer" : "assistant";
      div.className = `bubble ${role}`;
      if (latest) div.classList.add("latest");
      div.textContent = m.text;
      thread.appendChild(div);
    });
    if (state.tzAvailable && cards === 0 && !state.welcomePending) {
      renderTzCard(thread, { meta_kind: "tz_download" }, true);
    }
  }

  function scrollThreadToLatest() {
    const thread = $("thread");
    if (!thread) return;
    const last = thread.querySelector(".bubble.latest") || thread.lastElementChild;
    const go = () => {
      window.scrollTo(0, 0);
      const max = Math.max(0, thread.scrollHeight - thread.clientHeight);
      if (last) {
        const top = last.offsetTop + last.offsetHeight - thread.clientHeight;
        thread.scrollTop = Math.max(0, top, max);
      } else {
        thread.scrollTop = max;
      }
    };
    go();
    requestAnimationFrame(() => {
      go();
      requestAnimationFrame(go);
    });
    setTimeout(go, 50);
    setTimeout(go, 200);
    setTimeout(go, 480);
  }

  function showSendHint(text) {
    const hint = $("send-hint");
    if (!hint) return;
    if (!text) {
      hint.classList.add("hidden");
      hint.textContent = "";
      return;
    }
    hint.classList.remove("hidden");
    hint.textContent = text;
  }

  function hideExportFallback() {
    const box = $("export-fallback");
    const textEl = $("export-fallback-text");
    if (box) box.classList.add("hidden");
    if (textEl) textEl.textContent = "";
    state.exportRetry = null;
  }

  function humanizeTelegramSendError(raw) {
    const text = String(raw || "").trim();
    const low = text.toLowerCase();
    if (
      low.includes("СЃРµС‚СЊ РґРѕ telegram РЅРµРґРѕСЃС‚СѓРїРЅР°") ||
      low.includes("telegram_bot_api_unreachable")
    ) {
      return "РЎРµСЂРІРµСЂ РЅРµ СЃРјРѕРі СЃРІСЏР·Р°С‚СЊСЃСЏ СЃ Telegram Bot API (РЅРµ РІР°С€ РёРЅС‚РµСЂРЅРµС‚). РџРѕРїСЂРѕР±СѓР№С‚Рµ РµС‰С‘ СЂР°Р·.";
    }
    return text;
  }

  function showExportFallback(reason, kind, fmt, exportPath) {
    const why =
      humanizeTelegramSendError(reason) || "РќРµ СѓРґР°Р»РѕСЃСЊ РѕС‚РїСЂР°РІРёС‚СЊ С„Р°Р№Р» РІ С‡Р°С‚ Р±РѕС‚Р°.";
    const box = $("export-fallback");
    const textEl = $("export-fallback-text");
    const open = $("export-open");
    if (textEl) textEl.textContent = why;
    if (box) box.classList.remove("hidden");
    showSendHint(why);
    state.exportRetry = { kind, fmt, exportPath };
    if (open) {
      if (exportPath) {
        open.href = exportPath;
        open.classList.remove("hidden");
      } else {
        open.removeAttribute("href");
        open.classList.add("hidden");
      }
    }
  }

  function renderClientEstimate(est, projectStatus) {
    const card = $("client-estimate");
    if (!card) return;
    if (!est) {
      card.classList.add("hidden");
      return;
    }
    card.classList.remove("hidden");
    const cost = $("ce-cost");
    const hours = $("ce-hours");
    const disc = $("ce-disclaimer");
    const reportBody = $("ce-report-body");
    const actions = $("ce-actions");
    const statusEl = $("ce-status");
    if (cost) {
      cost.textContent = est.formatted_cost
        ? `${est.formatted_cost}`
        : "вЂ”";
    }
    if (hours) {
      const range =
        est.formatted_cost_low && est.formatted_cost_high
          ? `Р’РёР»РєР° ${est.formatted_cost_low} вЂ“ ${est.formatted_cost_high}`
          : "";
      hours.textContent = [
        est.formatted_hours ? `~${est.formatted_hours} С‡` : "",
        est.formatted_rate_mid ? `СЃРµСЂРµРґРёРЅР° ${est.formatted_rate_mid}` : "",
        range,
      ]
        .filter(Boolean)
        .join(" В· ");
    }
    if (disc) disc.textContent = est.disclaimer || "";
    if (reportBody) {
      const report = est.report || {};
      reportBody.textContent = report.body || "";
    }
    const pending = est.status === "pending" || est.status === "discuss_requested";
    const canDecide =
      pending &&
      (projectStatus === "WAITING_CLIENT_ESTIMATE" ||
        projectStatus === "WAITING_CUSTOMER");
    if (actions) actions.classList.toggle("hidden", !canDecide);
    if (statusEl) {
      if (est.status === "confirmed") {
        statusEl.textContent = "РЎРјРµС‚Р° РїРѕРґС‚РІРµСЂР¶РґРµРЅР°. РњРѕР¶РЅРѕ Р¶РґР°С‚СЊ СЃР±РѕСЂРєСѓ MVP.";
      } else if (est.status === "discuss_requested") {
        statusEl.textContent = "Р—Р°РїСЂРѕСЃ РЅР° РѕР±СЃСѓР¶РґРµРЅРёРµ РѕС‚РїСЂР°РІР»РµРЅ СЂР°Р·СЂР°Р±РѕС‚С‡РёРєСѓ.";
      } else if (projectStatus === "WAITING_CLIENT_ESTIMATE") {
        statusEl.textContent = "РџРѕРґС‚РІРµСЂРґРёС‚Рµ РѕСЂРёРµРЅС‚РёСЂ вЂ” Рё С‚РѕР»СЊРєРѕ РїРѕС‚РѕРј РЅР°С‡РЅС‘Рј MVP.";
      } else {
        statusEl.textContent = "";
      }
    }
  }

  async function decideClientEstimate(action) {
    if (!state.projectId || !requireUser() || state.sending) return;
    state.sending = true;
    const confirmBtn = $("ce-confirm");
    const discussBtn = $("ce-discuss");
    if (confirmBtn) confirmBtn.disabled = true;
    if (discussBtn) discussBtn.disabled = true;
    try {
      const qs = new URLSearchParams({ customer_telegram_id: userId });
      await api(`/projects/${state.projectId}/client-estimate/${action}?${qs}`, {
        method: "POST",
        body: JSON.stringify({
          action,
          customer_telegram_id: userId,
        }),
      });
      haptic("medium");
      await openWorkspace(state.projectId, state.listMode || "change");
    } catch (err) {
      alert(err.message || String(err));
    } finally {
      state.sending = false;
      if (confirmBtn) confirmBtn.disabled = false;
      if (discussBtn) discussBtn.disabled = false;
    }
  }

  const ceConfirm = $("ce-confirm");
  const ceDiscuss = $("ce-discuss");
  if (ceConfirm) {
    ceConfirm.addEventListener("click", () => decideClientEstimate("confirm"));
  }
  if (ceDiscuss) {
    ceDiscuss.addEventListener("click", () => decideClientEstimate("discuss"));
  }

  function openCustomerBotChat(username) {
    const name = String(username || "").replace(/^@/, "").trim();
    const link = name ? `https://t.me/${name}` : "";
    if (!link || !tg || typeof tg.openTelegramLink !== "function") return;
    try {
      tg.openTelegramLink(link);
    } catch (_) {
      /* older clients keep the hint */
    }
  }

  function openExportInBrowser(exportPath) {
    if (!exportPath) return false;
    const abs = exportPath.startsWith("http")
      ? exportPath
      : `${window.location.origin}${exportPath}`;
    if (inTelegramWebView() && tg && typeof tg.openLink === "function") {
      try {
        tg.openLink(abs, { try_instant_view: false });
        return true;
      } catch (_) {
        try {
          tg.openLink(abs);
          return true;
        } catch (__) {
          return false;
        }
      }
    }
    return false;
  }

  async function downloadExport(kind, fmt) {
    if (!state.projectId || !requireUser()) return;
    const qs = new URLSearchParams({
      format: fmt,
      customer_telegram_id: userId,
    });
    const base = kind === "estimate" ? "estimate" : "tz";
    const exportPath = `/projects/${state.projectId}/${base}-export?${qs}`;
    const sendPath = `/projects/${state.projectId}/${base}-send?${qs}`;
    hideExportFallback();
    showSendHint("РћС‚РїСЂР°РІР»СЏРµРј С„Р°Р№Р» РІ С‡Р°С‚ Р±РѕС‚Р°вЂ¦");

    try {
      const sent = await api(sendPath, { method: "POST" });
      if (!sent || sent.sent !== true || !sent.message_id) {
        throw new Error("Р‘РѕС‚ РЅРµ РїРѕРґС‚РІРµСЂРґРёР» РѕС‚РїСЂР°РІРєСѓ С„Р°Р№Р»Р° РІ Р»РёС‡РєСѓ.");
      }
      showSendHint("Р¤Р°Р№Р» РІ Р»РёС‡РєРµ СЃ Р±РѕС‚РѕРј. Р—Р°РєСЂРѕР№С‚Рµ Mini App вЂ” РµРіРѕ РЅРµС‚ РІ СЌС‚РѕР№ Р»РµРЅС‚Рµ.");
      openCustomerBotChat(sent.bot_username);
      return;
    } catch (err) {
      showExportFallback(err && err.message, kind, fmt, exportPath);
      xp("error");
    }
  }

  const exportRetryBtn = $("export-retry");
  if (exportRetryBtn) {
    exportRetryBtn.addEventListener("click", async () => {
      const retry = state.exportRetry;
      if (!retry) return;
      await downloadExport(retry.kind, retry.fmt);
    });
  }
  const exportOpenBtn = $("export-open");
  if (exportOpenBtn) {
    exportOpenBtn.addEventListener("click", (ev) => {
      const retry = state.exportRetry;
      const href = (retry && retry.exportPath) || exportOpenBtn.getAttribute("href") || "";
      if (!href || href === "#") {
        ev.preventDefault();
        return;
      }
      if (openExportInBrowser(href)) {
        ev.preventDefault();
        showSendHint("Р•СЃР»Рё С„Р°Р№Р» РЅРµ РѕС‚РєСЂС‹Р»СЃСЏ вЂ” РЅР°РїРёС€РёС‚Рµ Р±РѕС‚Сѓ /start Рё РЅР°Р¶РјРёС‚Рµ В«Р•С‰С‘ СЂР°Р· РІ Р±РѕС‚Р°В».");
      }
    });
  }

  const threadEl = $("thread");
  if (threadEl) {
    threadEl.addEventListener("click", async (ev) => {
      const btn = ev.target && ev.target.closest ? ev.target.closest("[data-tz-fmt]") : null;
      if (!btn || !threadEl.contains(btn)) return;
      try {
        await downloadExport("tz", btn.getAttribute("data-tz-fmt") || "md");
      } catch (err) {
        xp("error");
        showExportFallback(
          err.message || String(err),
          "tz",
          btn.getAttribute("data-tz-fmt") || "md",
          ""
        );
      }
    });
  }

  document.querySelectorAll("[data-ce-fmt]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await downloadExport("estimate", btn.getAttribute("data-ce-fmt") || "md");
      } catch (err) {
        xp("error");
        showExportFallback(
          err.message || String(err),
          "estimate",
          btn.getAttribute("data-ce-fmt") || "md",
          ""
        );
      }
    });
  });

  function renderChoices(choices, paused, allowMultiple) {
    const box = $("choice-chips");
    const hint = $("choice-hint");
    const openBtn = $("btn-choices");
    const applyBtn = $("choices-apply");
    if (!box) return;
    box.innerHTML = "";
    state.choiceItems = Array.isArray(choices) ? choices : [];
    state.allowMultiple = Boolean(allowMultiple);
    state.selectedIds = new Set();
    showSendHint("");
    if (hint) {
      hint.classList.add("hidden");
      hint.textContent = "";
    }
    if (applyBtn) applyBtn.classList.add("hidden");
    closeChoicesModal();
    if (!state.choiceItems.length) {
      if (openBtn) openBtn.classList.add("hidden");
      return;
    }
    if (openBtn) openBtn.classList.remove("hidden");
    if (hint && state.allowMultiple) {
      hint.classList.remove("hidden");
      hint.textContent = "РњРѕР¶РЅРѕ РѕС‚РјРµС‚РёС‚СЊ РЅРµСЃРєРѕР»СЊРєРѕ РІР°СЂРёР°РЅС‚РѕРІ, Р·Р°С‚РµРј В«Р’С‹Р±СЂР°С‚СЊВ».";
    }
    if (applyBtn) applyBtn.classList.toggle("hidden", !state.allowMultiple);
    state.choiceItems.forEach((choice) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = choice.recommended ? "choice-chip recommended" : "choice-chip";
      btn.textContent = choice.recommended
        ? `${choice.label || choice.id} В· СЂРµРєРѕРјРµРЅРґСѓРµРј`
        : choice.label || choice.id;
      btn.addEventListener("click", () => onChoiceTap(choice));
      box.appendChild(btn);
    });
    if (paused) {
      const tip = document.createElement("div");
      tip.className = "muted";
      tip.textContent = "РРЅС‚РµСЂРІСЊСЋ РЅР° РїР°СѓР·Рµ";
      box.appendChild(tip);
    }
  }

  function openChoicesModal() {
    const modal = $("choices-modal");
    if (!modal || !state.choiceItems.length) return;
    modal.classList.remove("hidden");
  }

  function closeChoicesModal() {
    const modal = $("choices-modal");
    if (modal) modal.classList.add("hidden");
  }

  function paintSelectedChips() {
    const box = $("choice-chips");
    if (!box) return;
    const buttons = box.querySelectorAll(".choice-chip");
    buttons.forEach((btn, idx) => {
      const choice = state.choiceItems[idx];
      if (!choice) return;
      btn.classList.toggle("selected", state.selectedIds.has(choice.id));
    });
  }

  function isWriteInChoice(choice) {
    const blob = [choice && choice.label, choice && choice.id]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .replace(/С‘/g, "Рµ");
    return /СЃРµР№С‡Р°СЃ\s+РЅР°РїРёС€Сѓ|РЅР°РїРёС€Сѓ\s+СЃР°Рј|СЃРІРѕР№\s+РІР°СЂРёР°РЅС‚/.test(blob);
  }

  function selectedChoices() {
    return state.choiceItems.filter((c) => {
      if (!state.selectedIds.has(c.id)) return false;
      if (c.exclusive && !isWriteInChoice(c)) return false;
      return true;
    });
  }

  function formatSelectedLabels() {
    const labels = selectedChoices()
      .map((c) => String(c.label || "").trim() || c.id)
      .filter(Boolean);
    if (!labels.length) return "";
    if (labels.length === 1) return labels[0];
    if (labels.length === 2) return `${labels[0]} Рё ${labels[1]}`;
    return `${labels.slice(0, -1).join(", ")} Рё ${labels[labels.length - 1]}`;
  }

  function encodeSelectedPayload(extraText) {
    const extra = String(extraText || "").trim();
    const labels = formatSelectedLabels();
    if (!labels) return extra;
    return extra ? `${labels}\n${extra}` : labels;
  }

  function focusComposer() {
    const box = $("composer-text");
    if (!box) return;
    try {
      box.focus({ preventScroll: true });
    } catch (_) {
      try {
        box.focus();
      } catch (__) {
        /* some WebViews */
      }
    }
  }

  function holdForWriteIn() {
    closeChoicesModal();
    paintSelectedChips();
    const labels = formatSelectedLabels();
    showSendHint(
      labels
        ? `Р’С‹Р±СЂР°РЅРѕ: ${labels}. Р”РѕРїРёС€РёС‚Рµ С‚РµРєСЃС‚ Рё РЅР°Р¶РјРёС‚Рµ В«РћС‚РїСЂР°РІРёС‚СЊВ».`
        : "Р”РѕРїРёС€РёС‚Рµ С‚РµРєСЃС‚ Рё РЅР°Р¶РјРёС‚Рµ В«РћС‚РїСЂР°РІРёС‚СЊВ»."
    );
    focusComposer();
  }

  async function onChoiceTap(choice) {
    if (!choice) return;
    if (isWriteInChoice(choice)) {
      if (state.allowMultiple) {
        if (state.selectedIds.has(choice.id)) state.selectedIds.delete(choice.id);
        else state.selectedIds.add(choice.id);
      } else {
        state.selectedIds = new Set([choice.id]);
      }
      if (state.selectedIds.has(choice.id)) {
        holdForWriteIn();
      } else {
        paintSelectedChips();
        showSendHint("");
      }
      return;
    }
    if (choice.exclusive || !state.allowMultiple) {
      closeChoicesModal();
      await sendDiscoveryText(choice.label || choice.id);
      return;
    }
    if (state.selectedIds.has(choice.id)) state.selectedIds.delete(choice.id);
    else state.selectedIds.add(choice.id);
    paintSelectedChips();
    showSendHint("");
  }

  function showTypingBubble() {
    hideTypingBubble();
    const thread = $("thread");
    if (!thread) return;
    const tip = document.createElement("div");
    tip.className = "bubble assistant typing";
    tip.id = "typing-bubble";
    tip.textContent = "РђСЃСЃРёСЃС‚РµРЅС‚ РїРµС‡Р°С‚Р°РµС‚вЂ¦";
    thread.appendChild(tip);
    scrollThreadToLatest();
  }

  function hideTypingBubble() {
    const tip = document.getElementById("typing-bubble");
    if (tip) tip.remove();
  }

  async function sendDiscoveryText(text) {
    if (!requireUser() || !state.projectId) return false;
    const payload = String(text || "").trim();
    if (!payload) {
      showSendHint("Р’С‹Р±РµСЂРёС‚Рµ РІР°СЂРёР°РЅС‚С‹ РёР»Рё РІРІРµРґРёС‚Рµ С‚РµРєСЃС‚, Р·Р°С‚РµРј РЅР°Р¶РјРёС‚Рµ В«РћС‚РїСЂР°РІРёС‚СЊВ».");
      return false;
    }
    if (state.sending) return false;
    state.sending = true;
    showSendHint("РћС‚РїСЂР°РІРєР°вЂ¦");
    xp("thinking");
    state.wsMessages = [
      ...(state.wsMessages || []),
      {
        id: `local-${Date.now()}`,
        role: "customer",
        text: payload,
        created_at: new Date().toISOString(),
      },
    ];
    renderThread(state.wsMessages);
    showTypingBubble();
    try {
      const qs = `?customer_telegram_id=${encodeURIComponent(userId)}`;
      await api(`/projects/${state.projectId}/messages${qs}`, {
        method: "POST",
        body: JSON.stringify({ text: payload, role: "customer" }),
      });
      $("composer-text").value = "";
      state.selectedIds = new Set();
      showSendHint("");
      await openWorkspace(
        state.projectId,
        state.listMode === "create" ? "create" : "change",
        "got_answer"
      );
      return true;
    } catch (err) {
      hideTypingBubble();
      xp("error");
      showSendHint(err.message || String(err));
      alert(err.message || String(err));
      return false;
    } finally {
      state.sending = false;
    }
  }

  const welcomeGo = $("welcome-go");
  if (welcomeGo) {
    welcomeGo.addEventListener("click", () => {
      haptic("light");
      markWelcomeDismissed(state.projectId);
      closeWelcomeModal();
      xp("idle");
      renderThread(state.wsMessages || []);
      scrollThreadToLatest();
    });
  }
  const btnChoices = $("btn-choices");
  if (btnChoices) {
    btnChoices.addEventListener("click", () => {
      haptic("light");
      openChoicesModal();
    });
  }
  const choicesCancel = $("choices-cancel");
  if (choicesCancel) {
    choicesCancel.addEventListener("click", closeChoicesModal);
  }
  const choicesApply = $("choices-apply");
  if (choicesApply) {
    choicesApply.addEventListener("click", async () => {
      const typed = ($("composer-text").value || "").trim();
      if (!selectedChoices().length && !typed) {
        showSendHint("РћС‚РјРµС‚СЊС‚Рµ РІР°СЂРёР°РЅС‚С‹ РёР»Рё РЅР°Р¶РјРёС‚Рµ В«РћС‚РјРµРЅР°В».");
        return;
      }
      if (selectedChoices().some(isWriteInChoice) && !typed) {
        holdForWriteIn();
        return;
      }
      const payload = encodeSelectedPayload(typed);
      if (!payload) {
        showSendHint("РћС‚РјРµС‚СЊС‚Рµ РІР°СЂРёР°РЅС‚С‹ РёР»Рё РЅР°Р¶РјРёС‚Рµ В«РћС‚РјРµРЅР°В».");
        return;
      }
      closeChoicesModal();
      await sendDiscoveryText(payload);
    });
  }
  const choicesModal = $("choices-modal");
  if (choicesModal) {
    choicesModal.addEventListener("click", (ev) => {
      if (ev.target === choicesModal) closeChoicesModal();
    });
  }

  $("composer").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (!requireUser() || !state.projectId) return;
    const mode = state.listMode;
    const typed = ($("composer-text").value || "").trim();
    try {
      if (mode === "feedback") {
        if (!typed) {
          showSendHint("Р’РІРµРґРёС‚Рµ Р·Р°РјРµС‡Р°РЅРёРµ Рё РЅР°Р¶РјРёС‚Рµ В«РћС‚РїСЂР°РІРёС‚СЊВ».");
          return;
        }
        xp("thinking");
        const res = await api(`/projects/${state.projectId}/feedback`, {
          method: "POST",
          body: JSON.stringify({ text: typed, customer_telegram_id: userId }),
        });
        $("composer-text").value = "";
        await openWorkspace(state.projectId, "feedback", "got_answer");
        const thread = $("thread");
        const tip = document.createElement("div");
        tip.className = "bubble assistant latest";
        tip.textContent = res.reply_to_customer;
        thread.querySelectorAll(".bubble.latest").forEach((el) => {
          if (el !== tip) el.classList.remove("latest");
        });
        thread.appendChild(tip);
        scrollThreadToLatest();
      } else {
        const payload = encodeSelectedPayload(typed);
        await sendDiscoveryText(payload);
      }
    } catch (err) {
      xp("error");
      alert(err.message || String(err));
    }
  });

  $("composer-text").addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" || ev.shiftKey) return;
    ev.preventDefault();
    $("composer").requestSubmit();
  });

  $("btn-attach").addEventListener("click", () => {
    if (!requireUser() || !state.projectId) return;
    if (state.listMode === "feedback") {
      alert("Р’ СЂРµР¶РёРјРµ Р·Р°РјРµС‡Р°РЅРёР№ РїСЂРёРєСЂРµРїРёС‚Рµ С„Р°Р№Р» РєР°Рє С‚РµРєСЃС‚ РѕРїРёСЃР°РЅРёСЏ РёР»Рё РёСЃРїРѕР»СЊР·СѓР№С‚Рµ РіРѕР»РѕСЃ РїРѕР·Р¶Рµ.");
    }
    $("file-input").click();
  });

  $("file-input").addEventListener("change", async () => {
    const input = $("file-input");
    const file = input.files && input.files[0];
    input.value = "";
    if (!file || !state.projectId || !requireUser()) return;
    if (state.listMode === "feedback") {
      alert("РџСЂРёРєСЂРµРїР»РµРЅРёРµ С„Р°Р№Р»РѕРІ РІ Р·Р°РјРµС‡Р°РЅРёСЏС… РїРѕРєР° С‡РµСЂРµР· С‚РµРєСЃС‚. РћРїРёС€РёС‚Рµ Р·Р°РјРµС‡Р°РЅРёРµ.");
      return;
    }
    try {
      const fd = new FormData();
      fd.append("file", file, file.name);
      const caption = ($("composer-text").value || "").trim();
      const qs = new URLSearchParams({ customer_telegram_id: userId });
      if (caption) qs.set("caption", caption);
      xp("thinking");
      showTypingBubble();
      await api(`/projects/${state.projectId}/messages/file?${qs}`, {
        method: "POST",
        body: fd,
      });
      $("composer-text").value = "";
      await openWorkspace(
        state.projectId,
        state.listMode === "create" ? "create" : "change",
        "got_file"
      );
    } catch (err) {
      hideTypingBubble();
      xp("error");
      alert(err.message || String(err));
    }
  });

  const voiceBtn = $("btn-voice");
  const voiceStatus = $("voice-status");

  voiceBtn.addEventListener("click", async () => {
    if (!requireUser() || !state.projectId) return;
    if (state.recording) {
      stopVoice();
      return;
    }
    await startVoice();
  });

  function setVoiceUi(active, statusText) {
    state.recording = active;
    if (active) xp("listening");
    voiceBtn.classList.toggle("recording", active);
    voiceBtn.setAttribute("aria-pressed", active ? "true" : "false");
    const label = voiceBtn.querySelector(".btn-label");
    if (label) label.textContent = active ? "РЎС‚РѕРї" : "Р“РѕР»РѕСЃ";
    voiceBtn.title = active ? "РћСЃС‚Р°РЅРѕРІРёС‚СЊ Р·Р°РїРёСЃСЊ" : "РќР°РґРёРєС‚РѕРІР°С‚СЊ РІ РїРѕР»Рµ РѕС‚РІРµС‚Р°";
    if (statusText) {
      voiceStatus.classList.remove("hidden");
      voiceStatus.textContent = statusText;
    } else if (!active) {
      voiceStatus.classList.add("hidden");
      voiceStatus.textContent = "";
    }
  }

  function resizeComposer() {
    /* textarea fills 20вЂ“25% composer via CSS flex */
  }

  function appendToComposer(transcript) {
    const box = $("composer-text");
    if (!box) return;
    const existing = (box.value || "").trim();
    const piece = String(transcript || "")
      .replace(/\s+/g, " ")
      .trim();
    if (!piece) return;
    box.value = existing ? `${existing} ${piece}` : piece;
    resizeComposer();
    box.focus();
    const len = box.value.length;
    try {
      box.setSelectionRange(len, len);
    } catch (_) {
      /* some WebViews */
    }
  }

  async function startVoice() {
    // Web Speech when environment is capable; otherwise Groq Whisper via /stt/transcribe.
    if (canUseWebSpeech()) {
      startSpeechDictation();
      return;
    }
    await startMediaDictation();
  }

  function fallbackToGroq(reason) {
    state.webSpeechDisabled = true;
    state.recognition = null;
    state.voiceMode = null;
    const note = reason
      ? `Web Speech РЅРµРґРѕСЃС‚СѓРїРµРЅ (${reason}). Р—Р°РїРёСЃСЊ в†’ Groq WhisperвЂ¦`
      : "Р—Р°РїРёСЃСЊ в†’ Groq WhisperвЂ¦";
    setVoiceUi(false, note);
    startMediaDictation().catch((e) => alert(e.message || String(e)));
  }

  function stopVoice() {
    if (state.voiceMode === "speech" && state.recognition) {
      try {
        state.recognition.stop();
      } catch (_) {
        /* already stopped */
      }
      return;
    }
    if (state.voiceMode === "media" && state.mediaRecorder) {
      const recorder = state.mediaRecorder;
      setVoiceUi(true, "Р Р°СЃРїРѕР·РЅР°РІР°РЅРёРµ (Groq)вЂ¦");
      try {
        if (recorder.state === "recording") recorder.requestData();
      } catch (_) {
        /* optional */
      }
      recorder.stop();
      state.mediaRecorder = null;
    }
  }

  function startSpeechDictation() {
    const rec = new SpeechRecognition();
    rec.lang = "ru-RU";
    rec.interimResults = false;
    rec.continuous = true;
    rec.maxAlternatives = 1;

    state.recognition = rec;
    state.voiceMode = "speech";
    state.speechGotResult = false;

    rec.onstart = () => {
      setVoiceUi(true, "Web Speech: СЃР»СѓС€Р°СЋвЂ¦ Р·Р°С‚РµРј РЎС‚РѕРї");
    };
    rec.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const row = event.results[i];
        if (row.isFinal) {
          state.speechGotResult = true;
          appendToComposer(row[0].transcript);
          voiceStatus.classList.remove("hidden");
          voiceStatus.textContent = "РўРµРєСЃС‚ РІСЃС‚Р°РІР»РµРЅ вЂ” РјРѕР¶РЅРѕ РґРѕРіРѕРІРѕСЂРёС‚СЊ РёР»Рё РїСЂР°РІРёС‚СЊ";
          xp("got_voice");
        }
      }
    };
    rec.onerror = (event) => {
      const code = event.error || "error";
      if (code === "aborted") return;
      if (code === "no-speech") return;
      if (code === "not-allowed") {
        xp("error");
        alert("РќРµС‚ РґРѕСЃС‚СѓРїР° Рє РјРёРєСЂРѕС„РѕРЅСѓ. Р Р°Р·СЂРµС€РёС‚Рµ РјРёРєСЂРѕС„РѕРЅ РґР»СЏ Telegram/Р±СЂР°СѓР·РµСЂР°.");
        return;
      }
      // network / service-not-allowed / audio-capture в†’ use Groq path
      if (
        code === "network" ||
        code === "service-not-allowed" ||
        code === "language-not-supported" ||
        code === "audio-capture"
      ) {
        try {
          rec.abort();
        } catch (_) {
          /* ignore */
        }
        fallbackToGroq(code);
        return;
      }
      alert("РћС€РёР±РєР° Web Speech: " + code + ". РџСЂРѕР±СѓРµРј GroqвЂ¦");
      fallbackToGroq(code);
    };
    rec.onend = () => {
      if (state.webSpeechDisabled && state.voiceMode !== "speech") {
        return;
      }
      state.recognition = null;
      state.voiceMode = null;
      const hasText = (($("composer-text").value || "").trim().length > 0);
      setVoiceUi(
        false,
        hasText ? "Р“РѕС‚РѕРІРѕ вЂ” РїРѕРїСЂР°РІСЊС‚Рµ С‚РµРєСЃС‚ РїСЂРё РЅРµРѕР±С…РѕРґРёРјРѕСЃС‚Рё Рё РЅР°Р¶РјРёС‚Рµ РћС‚РїСЂР°РІРёС‚СЊ" : ""
      );
      if (!state.speechGotResult) xp("idle");
      if (hasText) {
        setTimeout(() => {
          if (!state.recording) {
            voiceStatus.classList.add("hidden");
            voiceStatus.textContent = "";
          }
        }, 2500);
      }
    };

    try {
      rec.start();
    } catch (err) {
      fallbackToGroq("start-failed");
    }
  }

  function micStreamLive() {
    const stream = state.micStream;
    if (!stream || !stream.active) return false;
    return stream.getAudioTracks().some((t) => t && t.readyState === "live");
  }

  function setMicTracksEnabled(on) {
    const stream = state.micStream;
    if (!stream) return;
    stream.getAudioTracks().forEach((t) => {
      try {
        t.enabled = Boolean(on);
      } catch (_) {
        /* ignore */
      }
    });
  }

  async function ensureMicStream() {
    if (micStreamLive()) {
      setMicTracksEnabled(true);
      return state.micStream;
    }
    if (
      typeof MediaRecorder === "undefined" ||
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia
    ) {
      const err = new Error("getUserMedia unavailable");
      err.code = "no-media";
      throw err;
    }
    const preferred = state.micConstraints || {
      audio: { echoCancellation: true, noiseSuppression: true },
    };
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia(preferred);
      state.micConstraints = preferred;
    } catch (_) {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      state.micConstraints = { audio: true };
    }
    state.micStream = stream;
    return stream;
  }

  async function startMediaDictation() {
    try {
      const stream = await ensureMicStream();
      const picked = pickRecorderMime();
      state.chunks = [];
      state.recorderExt = picked.ext;
      state.voiceMode = "media";
      state.recordingStartedAt = Date.now();
      state.mediaRecorder = picked.mime
        ? new MediaRecorder(stream, { mimeType: picked.mime })
        : new MediaRecorder(stream);
      state.mediaRecorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) state.chunks.push(ev.data);
      };
      state.mediaRecorder.onerror = () => {
        setMicTracksEnabled(false);
        state.mediaRecorder = null;
        state.voiceMode = null;
        setVoiceUi(false, "");
        xp("error");
        alert("РћС€РёР±РєР° Р·Р°РїРёСЃРё. РџРѕРїСЂРѕР±СѓР№С‚Рµ РµС‰С‘ СЂР°Р· РёР»Рё РІРІРµРґРёС‚Рµ С‚РµРєСЃС‚.");
      };
      state.mediaRecorder.onstop = () => {
        setMicTracksEnabled(false);
        dictationViaServer();
      };
      try {
        state.mediaRecorder.start(250);
      } catch (_) {
        state.mediaRecorder.start();
      }
      setVoiceUi(true, "РРґС‘С‚ Р·Р°РїРёСЃСЊвЂ¦ РЅР°Р¶РјРёС‚Рµ РјРёРєСЂРѕС„РѕРЅ РµС‰С‘ СЂР°Р·, С‡С‚РѕР±С‹ РѕСЃС‚Р°РЅРѕРІРёС‚СЊ");
    } catch (err) {
      state.voiceMode = null;
      setVoiceUi(false, "");
      xp("error");
      if (err && err.code === "no-media") {
        alert(
          "Р“РѕР»РѕСЃРѕРІРѕР№ РІРІРѕРґ РЅРµРґРѕСЃС‚СѓРїРµРЅ РІ СЌС‚РѕРј РєР»РёРµРЅС‚Рµ Telegram. Р Р°Р·СЂРµС€РёС‚Рµ РјРёРєСЂРѕС„РѕРЅ РґР»СЏ Telegram РІ РЅР°СЃС‚СЂРѕР№РєР°С… С‚РµР»РµС„РѕРЅР° РёР»Рё РІРІРµРґРёС‚Рµ С‚РµРєСЃС‚. Р“РѕР»РѕСЃРѕРІС‹Рµ РІ С‡Р°С‚ Р±РѕС‚Р° С‚РѕР¶Рµ РїСЂРёРЅРёРјР°СЋС‚СЃСЏ."
        );
        return;
      }
      const msg = String(err && err.message ? err.message : err);
      alert(
        "РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ РґРѕСЃС‚СѓРї Рє РјРёРєСЂРѕС„РѕРЅСѓ. Р’ Android: РќР°СЃС‚СЂРѕР№РєРё в†’ РїСЂРёР»РѕР¶РµРЅРёСЏ в†’ Telegram в†’ СЂР°Р·СЂРµС€РµРЅРёСЏ в†’ РњРёРєСЂРѕС„РѕРЅ. Р—Р°С‚РµРј Р·Р°РєСЂРѕР№С‚Рµ Mini App Рё РѕС‚РєСЂРѕР№С‚Рµ СЃРЅРѕРІР°. " +
          msg
      );
    }
  }

  async function dictationViaServer() {
    state.voiceMode = null;
    const elapsed = Date.now() - (state.recordingStartedAt || 0);
    try {
      const type =
        (state.chunks[0] && state.chunks[0].type) || "audio/webm";
      const blob = new Blob(state.chunks, { type });
      state.chunks = [];
      if (!blob.size || elapsed < 400) {
        setVoiceUi(false, "");
        xp("idle");
        alert("РЎР»РёС€РєРѕРј РєРѕСЂРѕС‚РєР°СЏ Р·Р°РїРёСЃСЊ. РќР°Р¶РјРёС‚Рµ РјРёРєСЂРѕС„РѕРЅ, РіРѕРІРѕСЂРёС‚Рµ, Р·Р°С‚РµРј РЅР°Р¶РјРёС‚Рµ РµС‰С‘ СЂР°Р·.");
        return;
      }
      const ext = state.recorderExt || (type.includes("ogg") ? "ogg" : type.includes("mp4") || type.includes("aac") ? "mp4" : "webm");
      const fd = new FormData();
      fd.append("file", blob, `voice.${ext}`);
      setVoiceUi(false, "Р Р°СЃРїРѕР·РЅР°РІР°РЅРёРµ (Groq)вЂ¦");
      xp("thinking");
      const res = await api("/stt/transcribe", { method: "POST", body: fd });
      const text = (res.text || "").trim();
      if (!text) {
        setVoiceUi(false, "");
        xp("error");
        alert("РќРµ СѓРґР°Р»РѕСЃСЊ СЂР°СЃРїРѕР·РЅР°С‚СЊ СЂРµС‡СЊ. РџРѕРїСЂРѕР±СѓР№С‚Рµ РµС‰С‘ СЂР°Р· РёР»Рё РІРІРµРґРёС‚Рµ С‚РµРєСЃС‚.");
        return;
      }
      appendToComposer(text);
      setVoiceUi(false, "РўРµРєСЃС‚ РІСЃС‚Р°РІР»РµРЅ вЂ” РјРѕР¶РЅРѕ РїСЂР°РІРёС‚СЊ Рё РѕС‚РїСЂР°РІРёС‚СЊ");
      xp("got_voice");
      setTimeout(() => {
        if (!state.recording) {
          voiceStatus.classList.add("hidden");
          voiceStatus.textContent = "";
        }
      }, 2500);
    } catch (err) {
      setVoiceUi(false, "");
      xp("error");
      alert(err.message || String(err));
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  if (tg && typeof tg.onEvent === "function") {
    tg.onEvent("viewportChanged", () => {
      syncViewportHeight();
      if (state.mode === "workspace") scrollThreadToLatest();
    });
    tg.onEvent("fullscreenChanged", () => {
      syncViewportHeight();
      if (state.mode === "workspace") scrollThreadToLatest();
    });
    tg.onEvent("safeAreaChanged", syncViewportHeight);
    tg.onEvent("contentSafeAreaChanged", syncViewportHeight);
    tg.onEvent("themeChanged", applyTelegramTheme);
  }
  window.addEventListener("resize", () => {
    syncViewportHeight();
    if (state.mode === "workspace") scrollThreadToLatest();
  });
  if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => {
      syncViewportHeight();
      if (state.mode === "workspace") scrollThreadToLatest();
    });
  }
  const composerBox = $("composer-text");
  if (composerBox) {
    composerBox.addEventListener("input", resizeComposer);
  }
  syncViewportHeight();

  fillSettings();
  refreshHome();
})();
