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

  /** Web Speech is unreliable in Telegram WebView — record + Groq instead. */
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
  };

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
        "Не удалось определить Telegram user id. Откройте Mini App из бота или добавьте ?uid=YOUR_ID"
      );
      return false;
    }
    return true;
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
        state.listMode === "feedback" ? "Замечания к реализации" : "Изменить проект";
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
    NEW: "уточняем идею",
    INTERVIEW: "ждём ваш ответ",
    ANALYZING: "собираем черновик",
    WAITING_CUSTOMER: "ждём ваш ответ",
    WAITING_OWNER: "на ревью у владельца",
    WAITING_CLIENT_ESTIMATE: "смотрите смету",
    READY: "можно собирать MVP",
    ARCHIVED: "проект закрыт",
  };
  const CUSTOMER_STAGE_HUD_RU = {
    PROJECT_CREATED: "уточняем идею",
    UNDERSTANDING_IDEA: "уточняем идею",
    BUSINESS_CONTEXT: "уточняем задачу",
    USERS: "кто будет пользоваться",
    FUNCTIONAL: "что должно уметь",
    DATA: "какие данные нужны",
    NON_FUNCTIONAL: "как должно работать",
    INTEGRATIONS: "какие связи с другими системами",
    ACCEPTANCE: "как примем работу",
    RISKS: "риски и ограничения",
    REVIEW: "проверяем черновик",
    READY_FOR_OWNER: "на ревью у владельца",
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
    if (paused) return "на паузе";
    const statusKey = hudKey(status);
    if (HOLD_STATUS_HUD[statusKey] && CUSTOMER_STATUS_HUD_RU[statusKey]) {
      return CUSTOMER_STATUS_HUD_RU[statusKey];
    }
    const stageKey = hudKey(stage);
    if (CUSTOMER_STAGE_HUD_RU[stageKey]) return CUSTOMER_STAGE_HUD_RU[stageKey];
    if (CUSTOMER_STATUS_HUD_RU[statusKey]) return CUSTOMER_STATUS_HUD_RU[statusKey];
    return "в работе";
  }

  function resetWorkspaceDom(nameText, metaText) {
    $("ws-name").textContent = nameText || "Проект";
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
      show("home");
    });
  });

  document.querySelector("[data-back-workspace]").addEventListener("click", () => {
    abortWorkspaceLoad();
    state.projectId = null;
    xp("idle");
    if (state.listMode === "create") show("home");
    else loadProjects();
  });

  $("create-submit").addEventListener("click", async () => {
    if (!requireUser()) return;
    const name = ($("create-name").value || "").trim() || `Проект ${userId}`;
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
      if (!pid) throw new Error("Проект создан, но не получен id чата");
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
    try {
      const projects = await api(
        `/projects?customer_telegram_id=${encodeURIComponent(userId)}`
      );
      if (!projects.length) {
        empty.classList.remove("hidden");
        return;
      }
      empty.classList.add("hidden");
      projects.forEach((p) => {
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
          del.title = "Удалить проект";
          del.setAttribute("aria-label", `Удалить проект ${p.name}`);
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
      `Удалить проект «${project.name}»?\n\nБудут удалены все сообщения, требования и связанные данные. Это нельзя отменить.`
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
      resetWorkspaceDom("Загрузка…", "Открываю чат этого проекта…");
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
      $("ws-name").textContent = ws.name;
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
          ? "Что исправить или добавить в реализации…"
          : (ws.discovery_choices || []).length
            ? "Ответьте текстом или откройте варианты…"
          : ws.status === "WAITING_CLIENT_ESTIMATE"
            ? "Смета ниже — подтвердите или напишите, что обсудить…"
          : ws.status === "WAITING_OWNER" || ws.status === "READY"
            ? "Можно добавить уточнение…"
            : "Ответьте текстом или откройте варианты…";
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
      show("home");
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
      label.textContent = "Сбор требований: готово";
    } else if (remaining <= 3) {
      label.textContent = "Ещё пара уточнений";
    } else {
      label.textContent = `Сбор требований: ${percent}%`;
    }
  }

  function isWelcomeMessage(m) {
    if (!m || m.role === "customer") return false;
    if (m.meta_kind === "welcome") return true;
    const t = String(m.text || "").toLowerCase();
    return t.includes("добро пожаловать") && t.includes("сбор требований");
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
    if (!t.includes("черновик")) return false;
    return (
      t.includes("скачайте") ||
      t.includes("скачать его можно") ||
      t.includes("добавлено к материалам ревью") ||
      t.includes("обновлён") ||
      t.includes("обновлен") ||
      /обновил[аи]?\s+черновик/.test(t)
    );
  }

  function tzCardLead(m) {
    if (m && m.meta_kind === "tz_updated") {
      return "Черновик ТЗ обновлён. Получить новую версию в чат бота:";
    }
    return "Черновик ТЗ готов. Получить в чат бота:";
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
    title.textContent = (m && m.text) || tzCardLead(m);
    div.appendChild(title);
    if (m && m.text) {
      const lead = document.createElement("p");
      lead.className = "tz-download-lead";
      lead.textContent = "Получить в чат бота";
      div.appendChild(lead);
    }
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
      renderTzCard(thread, { text: tzCardLead(null), meta_kind: "tz_download" }, true);
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
        : "—";
    }
    if (hours) {
      const range =
        est.formatted_cost_low && est.formatted_cost_high
          ? `Вилка ${est.formatted_cost_low} – ${est.formatted_cost_high}`
          : "";
      hours.textContent = [
        est.formatted_hours ? `~${est.formatted_hours} ч` : "",
        est.formatted_rate_mid ? `середина ${est.formatted_rate_mid}` : "",
        range,
      ]
        .filter(Boolean)
        .join(" · ");
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
        statusEl.textContent = "Смета подтверждена. Можно ждать сборку MVP.";
      } else if (est.status === "discuss_requested") {
        statusEl.textContent = "Запрос на обсуждение отправлен разработчику.";
      } else if (projectStatus === "WAITING_CLIENT_ESTIMATE") {
        statusEl.textContent = "Подтвердите ориентир — и только потом начнём MVP.";
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

  function filenameFromDisposition(cd, fallback) {
    const header = cd || "";
    const star = header.match(/filename\*=UTF-8''([^;]+)/i);
    const plain = header.match(/filename="?([^";]+)"?/i);
    try {
      return decodeURIComponent((star && star[1]) || (plain && plain[1]) || fallback);
    } catch (_) {
      return fallback;
    }
  }

  function triggerBlobDownload(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.rel = "noopener";
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  function withTimeout(promise, ms, fallback) {
    return new Promise((resolve) => {
      let settled = false;
      const timer = window.setTimeout(() => {
        if (!settled) {
          settled = true;
          resolve(fallback);
        }
      }, ms);
      Promise.resolve(promise).then(
        (value) => {
          if (!settled) {
            settled = true;
            window.clearTimeout(timer);
            resolve(value);
          }
        },
        () => {
          if (!settled) {
            settled = true;
            window.clearTimeout(timer);
            resolve(fallback);
          }
        }
      );
    });
  }

  function tryTelegramDownloadFile(abs, name) {
    if (!tg || typeof tg.downloadFile !== "function") return Promise.resolve(false);
    return new Promise((resolve) => {
      try {
        tg.downloadFile({ url: abs, file_name: name }, (done) => resolve(Boolean(done)));
      } catch (_) {
        resolve(false);
      }
    });
  }

  function dismissExportHint() {
    window.setTimeout(() => showSendHint(""), 1400);
  }

  function finishTzExportUi() {
    dismissExportHint();
  }

  function fallbackExportHint(reason, kind) {
    const why = String(reason || "").trim() || "Не удалось отправить файл в чат бота.";
    const suffix =
      kind === "estimate"
        ? " Скачиваем смету сюда."
        : " Скачиваем файл сюда.";
    showSendHint(why.endsWith(".") ? why + suffix : `${why}.${suffix}`);
  }

  async function fallbackDeviceExport(kind, fmt, exportPath, fallbackName) {
    const res = await fetch(exportPath);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showSendHint("");
      throw new Error(err.detail || res.statusText || "Не удалось скачать файл");
    }
    const blob = await res.blob();
    const name = filenameFromDisposition(res.headers.get("Content-Disposition"), fallbackName);
    triggerBlobDownload(blob, name);
    if (inTelegramWebView()) {
      const abs = `${window.location.origin}${exportPath}`;
      const saved = await withTimeout(tryTelegramDownloadFile(abs, name), 4000, false);
      if (saved) {
        showSendHint("В чат бота не ушло. Файл сохранён на устройство.");
        dismissExportHint();
        return;
      }
      if (tg && typeof tg.openLink === "function") {
        try {
          tg.openLink(abs, { try_instant_view: false });
        } catch (_) {
          try {
            tg.openLink(abs);
          } catch (__) {
            /* ignore */
          }
        }
      }
    }
    showSendHint(
      kind === "estimate"
        ? "В чат бота не ушло. Смета скачана на устройство."
        : "В чат бота не ушло. Файл скачан на устройство."
    );
    dismissExportHint();
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
    const fallbackName = kind === "estimate" ? `smeta.${fmt}` : `tz.${fmt}`;
    showSendHint("Отправляем файл в чат бота…");

    try {
      const sent = await api(sendPath, { method: "POST" });
      const sentName = (sent && sent.filename) || fallbackName;
      showSendHint(`Файл «${sentName}» отправлен в чат с ботом.`);
      if (kind === "tz") finishTzExportUi();
      else dismissExportHint();
      return;
    } catch (err) {
      fallbackExportHint(err && err.message, kind);
    }

    await fallbackDeviceExport(kind, fmt, exportPath, fallbackName);
  }

  const threadEl = $("thread");
  if (threadEl) {
    threadEl.addEventListener("click", async (ev) => {
      const btn = ev.target && ev.target.closest ? ev.target.closest("[data-tz-fmt]") : null;
      if (!btn || !threadEl.contains(btn)) return;
      try {
        await downloadExport("tz", btn.getAttribute("data-tz-fmt") || "md");
      } catch (err) {
        showSendHint("");
        xp("error");
        alert(err.message || String(err));
      }
    });
  }

  document.querySelectorAll("[data-ce-fmt]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await downloadExport("estimate", btn.getAttribute("data-ce-fmt") || "md");
      } catch (err) {
        showSendHint("");
        xp("error");
        alert(err.message || String(err));
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
      hint.textContent = "Можно отметить несколько вариантов, затем «Выбрать».";
    }
    if (applyBtn) applyBtn.classList.toggle("hidden", !state.allowMultiple);
    state.choiceItems.forEach((choice) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = choice.recommended ? "choice-chip recommended" : "choice-chip";
      btn.textContent = choice.recommended
        ? `${choice.label || choice.id} · рекомендуем`
        : choice.label || choice.id;
      btn.addEventListener("click", () => onChoiceTap(choice));
      box.appendChild(btn);
    });
    if (paused) {
      const tip = document.createElement("div");
      tip.className = "muted";
      tip.textContent = "Интервью на паузе";
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
      .replace(/ё/g, "е");
    return /сейчас\s+напишу|напишу\s+сам|свой\s+вариант/.test(blob);
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
    if (labels.length === 2) return `${labels[0]} и ${labels[1]}`;
    return `${labels.slice(0, -1).join(", ")} и ${labels[labels.length - 1]}`;
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
        ? `Выбрано: ${labels}. Допишите текст и нажмите «Отправить».`
        : "Допишите текст и нажмите «Отправить»."
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
    tip.textContent = "Ассистент печатает…";
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
      showSendHint("Выберите варианты или введите текст, затем нажмите «Отправить».");
      return false;
    }
    if (state.sending) return false;
    state.sending = true;
    showSendHint("Отправка…");
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
        showSendHint("Отметьте варианты или нажмите «Отмена».");
        return;
      }
      if (selectedChoices().some(isWriteInChoice) && !typed) {
        holdForWriteIn();
        return;
      }
      const payload = encodeSelectedPayload(typed);
      if (!payload) {
        showSendHint("Отметьте варианты или нажмите «Отмена».");
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
          showSendHint("Введите замечание и нажмите «Отправить».");
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
      alert("В режиме замечаний прикрепите файл как текст описания или используйте голос позже.");
    }
    $("file-input").click();
  });

  $("file-input").addEventListener("change", async () => {
    const input = $("file-input");
    const file = input.files && input.files[0];
    input.value = "";
    if (!file || !state.projectId || !requireUser()) return;
    if (state.listMode === "feedback") {
      alert("Прикрепление файлов в замечаниях пока через текст. Опишите замечание.");
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
    if (label) label.textContent = active ? "Стоп" : "Голос";
    voiceBtn.title = active ? "Остановить запись" : "Надиктовать в поле ответа";
    if (statusText) {
      voiceStatus.classList.remove("hidden");
      voiceStatus.textContent = statusText;
    } else if (!active) {
      voiceStatus.classList.add("hidden");
      voiceStatus.textContent = "";
    }
  }

  function resizeComposer() {
    /* textarea fills 20–25% composer via CSS flex */
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
      ? `Web Speech недоступен (${reason}). Запись → Groq Whisper…`
      : "Запись → Groq Whisper…";
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
      setVoiceUi(true, "Распознавание (Groq)…");
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
      setVoiceUi(true, "Web Speech: слушаю… затем Стоп");
    };
    rec.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const row = event.results[i];
        if (row.isFinal) {
          state.speechGotResult = true;
          appendToComposer(row[0].transcript);
          voiceStatus.classList.remove("hidden");
          voiceStatus.textContent = "Текст вставлен — можно договорить или править";
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
        alert("Нет доступа к микрофону. Разрешите микрофон для Telegram/браузера.");
        return;
      }
      // network / service-not-allowed / audio-capture → use Groq path
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
      alert("Ошибка Web Speech: " + code + ". Пробуем Groq…");
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
        hasText ? "Готово — поправьте текст при необходимости и нажмите Отправить" : ""
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
        alert("Ошибка записи. Попробуйте ещё раз или введите текст.");
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
      setVoiceUi(true, "Идёт запись… нажмите микрофон ещё раз, чтобы остановить");
    } catch (err) {
      state.voiceMode = null;
      setVoiceUi(false, "");
      xp("error");
      if (err && err.code === "no-media") {
        alert(
          "Голосовой ввод недоступен в этом клиенте Telegram. Разрешите микрофон для Telegram в настройках телефона или введите текст. Голосовые в чат бота тоже принимаются."
        );
        return;
      }
      const msg = String(err && err.message ? err.message : err);
      alert(
        "Не удалось получить доступ к микрофону. В Android: Настройки → приложения → Telegram → разрешения → Микрофон. Затем закройте Mini App и откройте снова. " +
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
        alert("Слишком короткая запись. Нажмите микрофон, говорите, затем нажмите ещё раз.");
        return;
      }
      const ext = state.recorderExt || (type.includes("ogg") ? "ogg" : type.includes("mp4") || type.includes("aac") ? "mp4" : "webm");
      const fd = new FormData();
      fd.append("file", blob, `voice.${ext}`);
      setVoiceUi(false, "Распознавание (Groq)…");
      xp("thinking");
      const res = await api("/stt/transcribe", { method: "POST", body: fd });
      const text = (res.text || "").trim();
      if (!text) {
        setVoiceUi(false, "");
        xp("error");
        alert("Не удалось распознать речь. Попробуйте ещё раз или введите текст.");
        return;
      }
      appendToComposer(text);
      setVoiceUi(false, "Текст вставлен — можно править и отправить");
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

  if (!userId) {
    $("subtitle").textContent = "Откройте из Telegram-бота или добавьте ?uid=";
  }

  show("home");
})();
