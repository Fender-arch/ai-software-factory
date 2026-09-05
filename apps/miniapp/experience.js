(() => {
  const STORAGE_KEY = "asf-calm-mode";
  const EVENTS = [
    "idle",
    "listening",
    "thinking",
    "got_answer",
    "got_voice",
    "got_file",
    "draft_ready",
    "error",
  ];
  const FLASH = new Set(["got_answer", "got_voice", "got_file", "error"]);
  const STATUS_RU = {
    idle: "На связи",
    listening: "Слушаю…",
    thinking: "Думаю…",
    got_answer: "Понял",
    got_voice: "Голос есть",
    got_file: "Файл есть",
    draft_ready: "Черновик ТЗ готов",
    error: "Что-то пошло не так",
  };
  const RIVE_CDNS = [
    "https://cdn.jsdelivr.net/npm/@rive-app/canvas@2.31.2/rive.js",
    "https://unpkg.com/@rive-app/canvas@2.31.2/rive.js",
  ];
  const CONFIG = {
    rivSrc: "./mascot.riv",
    stateMachine: "Mascot",
    flashMs: 2200,
  };

  const listeners = new Map();
  let current = "idle";
  let flashTimer = 0;
  let riveInstance = null;
  let riveReady = false;

  function $(id) {
    return document.getElementById(id);
  }

  function prefersReducedMotion() {
    return Boolean(
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function readCalm() {
    try {
      return window.localStorage.getItem(STORAGE_KEY) === "1";
    } catch (_) {
      return false;
    }
  }

  function writeCalm(on) {
    try {
      window.localStorage.setItem(STORAGE_KEY, on ? "1" : "0");
    } catch (_) {
      /* private mode */
    }
  }

  function isCalm() {
    return document.documentElement.classList.contains("asf-calm");
  }

  function motionAllowed() {
    return !isCalm() && !prefersReducedMotion();
  }

  function on(name, fn) {
    if (!listeners.has(name)) listeners.set(name, new Set());
    listeners.get(name).add(fn);
    return () => listeners.get(name) && listeners.get(name).delete(fn);
  }

  function notify(name, detail) {
    const set = listeners.get(name);
    if (set) {
      set.forEach((fn) => {
        try {
          fn(detail);
        } catch (_) {
          /* listener optional */
        }
      });
    }
    const any = listeners.get("*");
    if (any) {
      any.forEach((fn) => {
        try {
          fn(name, detail);
        } catch (_) {
          /* listener optional */
        }
      });
    }
    try {
      window.dispatchEvent(new CustomEvent("asf-experience", { detail: { event: name, ...detail } }));
    } catch (_) {
      /* CustomEvent optional */
    }
  }

  function paintStatus(name) {
    const slot = $("mascot-slot");
    const status = $("mascot-status");
    if (slot) slot.setAttribute("data-state", name);
    if (status) status.textContent = STATUS_RU[name] || STATUS_RU.idle;
    document.documentElement.setAttribute("data-asf-xp", name);
  }

  function fireRive(name) {
    if (!riveReady || !riveInstance || !motionAllowed()) return;
    try {
      const machines = riveInstance.stateMachineNames || [];
      const wanted = machines.indexOf(CONFIG.stateMachine) >= 0 ? CONFIG.stateMachine : machines[0];
      if (!wanted || typeof riveInstance.stateMachineInputs !== "function") return;
      const inputs = riveInstance.stateMachineInputs(wanted) || [];
      inputs.forEach((input) => {
        const key = String(input.name || "").toLowerCase();
        if (key === "calm" && typeof input.value === "boolean") {
          input.value = isCalm();
          return;
        }
        if (key !== name && key.replace(/-/g, "_") !== name) return;
        if (typeof input.fire === "function") input.fire();
        else if (typeof input.value === "boolean") input.value = true;
        else if (typeof input.value === "number") input.value = EVENTS.indexOf(name);
      });
    } catch (_) {
      /* riv inputs optional */
    }
  }

  function emit(name, extra) {
    const event = EVENTS.indexOf(name) >= 0 ? name : "idle";
    current = event;
    paintStatus(event);
    fireRive(event);
    notify(event, { event, calm: isCalm(), reduced: prefersReducedMotion(), ...(extra || {}) });
    if (window.ASFFoundry && typeof window.ASFFoundry.pulse === "function") {
      window.ASFFoundry.pulse(event);
    }
    window.clearTimeout(flashTimer);
    if (FLASH.has(event)) {
      flashTimer = window.setTimeout(() => {
        if (current === event) emit("idle");
      }, CONFIG.flashMs);
    }
    return event;
  }

  function syncCalmUi() {
    const on = isCalm();
    document.querySelectorAll("[data-calm-toggle]").forEach((btn) => {
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      btn.classList.toggle("is-on", on);
    });
    const slot = $("mascot-slot");
    if (slot) {
      slot.classList.toggle("is-frozen", !motionAllowed());
    }
    if (window.ASFFoundry && typeof window.ASFFoundry.setPaused === "function") {
      window.ASFFoundry.setPaused(!motionAllowed());
    }
    if (!motionAllowed()) {
      hideRiveCanvas();
    }
  }

  function setCalm(on) {
    const next = Boolean(on);
    document.documentElement.classList.toggle("asf-calm", next);
    writeCalm(next);
    syncCalmUi();
    notify("calm", { event: "calm", on: next });
    if (next) hideRiveCanvas();
    else tryLoadRive();
  }

  function hideRiveCanvas() {
    const canvas = $("mascot-rive");
    const fallback = $("mascot-fallback");
    if (canvas) canvas.classList.add("hidden");
    if (fallback) fallback.classList.remove("hidden");
  }

  function showRiveCanvas() {
    const canvas = $("mascot-rive");
    const fallback = $("mascot-fallback");
    if (canvas) canvas.classList.remove("hidden");
    if (fallback) fallback.classList.add("hidden");
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[data-asf-rive="${src}"]`);
      if (existing && window.rive) {
        resolve(window.rive);
        return;
      }
      const s = document.createElement("script");
      s.src = src;
      s.async = true;
      s.dataset.asfRive = src;
      s.onload = () => (window.rive ? resolve(window.rive) : reject(new Error("rive missing")));
      s.onerror = () => reject(new Error("cdn"));
      document.head.appendChild(s);
    });
  }

  async function loadRiveRuntime() {
    if (window.rive) return window.rive;
    let last = null;
    for (let i = 0; i < RIVE_CDNS.length; i += 1) {
      try {
        return await loadScript(RIVE_CDNS[i]);
      } catch (err) {
        last = err;
      }
    }
    throw last || new Error("rive cdn");
  }

  async function rivAvailable(src) {
    try {
      const head = await fetch(src, { method: "HEAD", cache: "no-store" });
      if (head && head.ok) return true;
      if (head && head.status === 405) {
        const get = await fetch(src, { method: "GET", cache: "no-store" });
        return Boolean(get && get.ok);
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  async function tryLoadRive() {
    if (!motionAllowed()) {
      hideRiveCanvas();
      return;
    }
    const canvas = $("mascot-rive");
    if (!canvas || riveReady) return;
    const src = CONFIG.rivSrc;
    if (!(await rivAvailable(src))) {
      hideRiveCanvas();
      return;
    }
    try {
      const runtime = await loadRiveRuntime();
      if (!runtime || !runtime.Rive) throw new Error("runtime");
      if (riveInstance && typeof riveInstance.cleanup === "function") {
        try {
          riveInstance.cleanup();
        } catch (_) {
          /* ignore */
        }
      }
      riveInstance = new runtime.Rive({
        src,
        canvas,
        autoplay: true,
        stateMachines: CONFIG.stateMachine,
        onLoad: () => {
          riveReady = true;
          try {
            if (typeof riveInstance.resizeDrawingSurfaceToCanvas === "function") {
              riveInstance.resizeDrawingSurfaceToCanvas();
            }
          } catch (_) {
            /* size optional */
          }
          showRiveCanvas();
          fireRive(current);
        },
        onLoadError: () => {
          riveReady = false;
          hideRiveCanvas();
        },
      });
    } catch (_) {
      riveReady = false;
      hideRiveCanvas();
    }
  }

  function bindToggles() {
    document.querySelectorAll("[data-calm-toggle]").forEach((btn) => {
      if (btn.dataset.calmBound) return;
      btn.dataset.calmBound = "1";
      btn.addEventListener("click", () => {
        setCalm(!isCalm());
      });
    });
  }

  function mount() {
    const metaRiv = document.querySelector('meta[name="asf-mascot-riv"]');
    const metaSm = document.querySelector('meta[name="asf-mascot-sm"]');
    if (metaRiv && metaRiv.content) CONFIG.rivSrc = metaRiv.content;
    if (metaSm && metaSm.content) CONFIG.stateMachine = metaSm.content;
    if (window.ASF_MASCOT && window.ASF_MASCOT.src) CONFIG.rivSrc = window.ASF_MASCOT.src;
    if (window.ASF_MASCOT && window.ASF_MASCOT.stateMachine) {
      CONFIG.stateMachine = window.ASF_MASCOT.stateMachine;
    }

    document.documentElement.classList.toggle("asf-calm", readCalm());
    if (prefersReducedMotion()) {
      document.documentElement.classList.add("asf-reduced");
    }
    paintStatus("idle");
    bindToggles();
    syncCalmUi();
    hideRiveCanvas();
    tryLoadRive();

    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
      const onChange = () => {
        document.documentElement.classList.toggle("asf-reduced", mq.matches);
        syncCalmUi();
        if (!mq.matches) tryLoadRive();
      };
      if (typeof mq.addEventListener === "function") mq.addEventListener("change", onChange);
      else if (typeof mq.addListener === "function") mq.addListener(onChange);
    }
  }

  window.ASFExperience = {
    EVENTS,
    STATUS_RU,
    STORAGE_KEY,
    emit,
    on,
    mount,
    setCalm,
    isCalm,
    isMotionAllowed: motionAllowed,
    prefersReducedMotion,
    current: () => current,
  };

  mount();
})();
