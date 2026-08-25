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

  if (tg) {
    tg.ready();
    tg.expand();
    try {
      applyTelegramTheme();
    } catch (_) {
      /* theme optional */
    }
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
  };

  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition || null;

  /** Prefer Web Speech only when the Telegram/WebView environment looks capable. */
  function canUseWebSpeech() {
    if (state.webSpeechDisabled) return false;
    if (!SpeechRecognition) return false;
    if (!window.isSecureContext) return false;
    const ua = navigator.userAgent || "";
    // iOS Telegram WebView: SpeechRecognition is often missing or broken.
    if (/iPhone|iPad|iPod/i.test(ua)) return false;
    return true;
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
    if (appEl) appEl.classList.toggle("is-workspace", isWs);
    document.documentElement.classList.toggle("asf-workspace", isWs);
    document.body.classList.toggle("asf-workspace", isWs);
    syncViewportHeight();
  }

  function syncViewportHeight() {
    const h =
      (tg && (tg.viewportStableHeight || tg.viewportHeight)) ||
      window.innerHeight ||
      0;
    if (h) {
      document.documentElement.style.setProperty("--app-vh", `${Math.round(h)}px`);
    }
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

  function resetWorkspaceDom(nameText, metaText) {
    $("ws-name").textContent = nameText || "Проект";
    $("ws-meta").textContent = metaText || "";
    renderProgress(null, false);
    renderThread([]);
    renderChoices([], false, false);
    showSendHint("");
    const box = $("composer-text");
    if (box) box.value = "";
  }

  document.querySelectorAll("[data-back]").forEach((btn) => {
    btn.addEventListener("click", () => {
      abortWorkspaceLoad();
      show("home");
    });
  });

  document.querySelector("[data-back-workspace]").addEventListener("click", () => {
    abortWorkspaceLoad();
    state.projectId = null;
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
          p.status
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
      alert(err.message || String(err));
    }
  }

  async function openWorkspace(projectId, mode) {
    const pid = String(projectId || "");
    if (!pid) return;
    abortWorkspaceLoad();
    const requestId = state.wsRequestId;
    state.projectId = pid;
    if (mode === "create" || mode === "change" || mode === "feedback") {
      state.listMode = mode;
    }
    resetWorkspaceDom("Загрузка…", "Открываю чат этого проекта…");
    show("workspace");
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
      $("ws-meta").textContent = `${ws.status} · ${ws.mode} · ${ws.discovery_stage || "—"}${
        ws.paused ? " · пауза" : ""
      }`;
      renderProgress(ws.discovery_progress, mode !== "feedback");
      renderThread(ws.messages || []);
      renderChoices(
        mode === "feedback" ? [] : ws.discovery_choices || [],
        Boolean(ws.paused) && mode !== "feedback",
        Boolean(ws.allow_multiple) && mode !== "feedback"
      );
      const placeholder =
        mode === "feedback"
          ? "Что исправить или добавить в реализации…"
          : (ws.discovery_choices || []).length
            ? "Ответьте на вопрос, выберите вариант или опишите идею…"
          : ws.status === "WAITING_OWNER" || ws.status === "READY"
            ? "Можно добавить уточнение — оно будет зафиксировано…"
            : "Ответьте на вопрос, выберите вариант или опишите идею…";
      $("composer-text").placeholder = placeholder;
      renderTzDownload(Boolean(ws.tz_available));
      scrollThreadToLatest();
    } catch (err) {
      if (isAbortError(err) || requestId !== state.wsRequestId) return;
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
    if (progress.phase === "done" || percent >= 100) {
      label.textContent = `Сбор требований: готово (${done} из ${total})`;
    } else {
      label.textContent = `Сбор требований: ${done} из ${total}`;
    }
  }

  function renderThread(messages) {
    const thread = $("thread");
    thread.innerHTML = "";
    messages.forEach((m, idx) => {
      const div = document.createElement("div");
      const role = m.role === "customer" ? "customer" : "assistant";
      div.className = `bubble ${role}`;
      if (idx === messages.length - 1) div.classList.add("latest");
      div.textContent = m.text;
      thread.appendChild(div);
    });
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

  function renderTzDownload(available) {
    const bar = $("tz-download");
    if (!bar) return;
    bar.classList.toggle("hidden", !available);
  }

  async function downloadTz(fmt) {
    if (!state.projectId || !requireUser()) return;
    const qs = new URLSearchParams({
      format: fmt,
      customer_telegram_id: userId,
    });
    const res = await fetch(`/projects/${state.projectId}/tz-export?${qs}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText || "Не удалось скачать ТЗ");
    }
    const blob = await res.blob();
    const cd = res.headers.get("Content-Disposition") || "";
    const star = cd.match(/filename\*=UTF-8''([^;]+)/i);
    const plain = cd.match(/filename="?([^";]+)"?/i);
    const name = decodeURIComponent((star && star[1]) || (plain && plain[1]) || `tz.${fmt}`);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  document.querySelectorAll("[data-tz-fmt]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      try {
        await downloadTz(btn.getAttribute("data-tz-fmt") || "md");
      } catch (err) {
        alert(err.message || String(err));
      }
    });
  });

  function renderChoices(choices, paused, allowMultiple) {
    const box = $("choice-chips");
    const hint = $("choice-hint");
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
    if (!state.choiceItems.length) {
      box.classList.add("hidden");
      return;
    }
    box.classList.remove("hidden");
    if (hint && state.allowMultiple) {
      hint.classList.remove("hidden");
      hint.textContent = "Можно отметить несколько вариантов, затем «Отправить».";
    }
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

  function encodeSelectedPayload(extraText) {
    const extra = String(extraText || "").trim();
    const selected = state.choiceItems.filter(
      (c) => state.selectedIds.has(c.id) && !c.exclusive
    );
    if (!selected.length) return extra;
    const nums = selected
      .map((c) => state.choiceItems.indexOf(c) + 1)
      .filter((n) => n > 0)
      .join(", ");
    return extra ? `${nums}\n${extra}` : nums;
  }

  async function onChoiceTap(choice) {
    if (!choice) return;
    if (choice.exclusive || !state.allowMultiple) {
      await sendDiscoveryText(choice.label || choice.id);
      return;
    }
    if (state.selectedIds.has(choice.id)) state.selectedIds.delete(choice.id);
    else state.selectedIds.add(choice.id);
    paintSelectedChips();
    showSendHint("");
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
    try {
      const qs = `?customer_telegram_id=${encodeURIComponent(userId)}`;
      await api(`/projects/${state.projectId}/messages${qs}`, {
        method: "POST",
        body: JSON.stringify({ text: payload, role: "customer" }),
      });
      $("composer-text").value = "";
      state.selectedIds = new Set();
      showSendHint("");
      await openWorkspace(state.projectId, state.listMode === "create" ? "create" : "change");
      return true;
    } catch (err) {
      showSendHint(err.message || String(err));
      alert(err.message || String(err));
      return false;
    } finally {
      state.sending = false;
    }
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
        const res = await api(`/projects/${state.projectId}/feedback`, {
          method: "POST",
          body: JSON.stringify({ text: typed, customer_telegram_id: userId }),
        });
        $("composer-text").value = "";
        await openWorkspace(state.projectId, "feedback");
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
      await api(`/projects/${state.projectId}/messages/file?${qs}`, {
        method: "POST",
        body: fd,
      });
      $("composer-text").value = "";
      await openWorkspace(state.projectId, state.listMode === "create" ? "create" : "change");
    } catch (err) {
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
    voiceBtn.classList.toggle("recording", active);
    voiceBtn.textContent = active ? "⏹ Стоп" : "🎤 Голос";
    if (statusText) {
      voiceStatus.classList.remove("hidden");
      voiceStatus.textContent = statusText;
    } else if (!active) {
      voiceStatus.classList.add("hidden");
      voiceStatus.textContent = "";
    }
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
        }
      }
    };
    rec.onerror = (event) => {
      const code = event.error || "error";
      if (code === "aborted") return;
      if (code === "no-speech") return;
      if (code === "not-allowed") {
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

  async function startMediaDictation() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert(
        "Голосовой ввод недоступен в этом клиенте. Нужен микрофон и поддержка записи, либо введите текст."
      );
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : MediaRecorder.isTypeSupported("audio/ogg")
            ? "audio/ogg"
            : "";
      state.chunks = [];
      state.voiceMode = "media";
      state.mediaRecorder = mime
        ? new MediaRecorder(stream, { mimeType: mime })
        : new MediaRecorder(stream);
      state.mediaRecorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) state.chunks.push(ev.data);
      };
      state.mediaRecorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        dictationViaServer();
      };
      try {
        state.mediaRecorder.start(250);
      } catch (_) {
        state.mediaRecorder.start();
      }
      setVoiceUi(true, "Запись для Groq Whisper… нажмите Стоп");
    } catch (err) {
      state.voiceMode = null;
      setVoiceUi(false, "");
      alert("Не удалось получить доступ к микрофону: " + (err.message || err));
    }
  }

  async function dictationViaServer() {
    state.voiceMode = null;
    try {
      const type =
        (state.chunks[0] && state.chunks[0].type) || "audio/webm";
      const blob = new Blob(state.chunks, { type });
      state.chunks = [];
      if (!blob.size) {
        setVoiceUi(false, "");
        alert("Пустая запись. Удерживайте дольше или проверьте микрофон.");
        return;
      }
      const ext = type.includes("ogg") ? "ogg" : "webm";
      const fd = new FormData();
      fd.append("file", blob, `voice.${ext}`);
      setVoiceUi(false, "Распознавание (Groq)…");
      const res = await api("/stt/transcribe", { method: "POST", body: fd });
      const text = (res.text || "").trim();
      if (!text) {
        setVoiceUi(false, "");
        alert("Не удалось распознать речь. Попробуйте ещё раз.");
        return;
      }
      appendToComposer(text);
      setVoiceUi(false, "Текст вставлен — можно править или договорить");
      setTimeout(() => {
        if (!state.recording) {
          voiceStatus.classList.add("hidden");
          voiceStatus.textContent = "";
        }
      }, 2500);
    } catch (err) {
      setVoiceUi(false, "");
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
    tg.onEvent("themeChanged", applyTelegramTheme);
  }
  window.addEventListener("resize", () => {
    syncViewportHeight();
    if (state.mode === "workspace") scrollThreadToLatest();
  });
  syncViewportHeight();

  if (!userId) {
    $("subtitle").textContent = "Откройте из Telegram-бота или добавьте ?uid=";
  }

  show("home");
})();
