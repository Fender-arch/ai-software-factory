(() => {
  let fieldCtl = null;
  let pulseUntil = 0;
  let pulseKind = "";

  const GLYPHS = "01アイウエオカキクケコサシスセソタチツテト0123456789UNI4IT#$%<>";
  const CYAN = [0, 210, 255];
  const PURPLE = [157, 80, 187];

  function motionBlocked() {
    if (document.documentElement.classList.contains("asf-calm")) return true;
    if (document.documentElement.classList.contains("asf-reduced")) return true;
    return Boolean(
      window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
  }

  function startField(canvas) {
    if (!canvas) return { stop() {}, setPaused() {} };
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return { stop() {}, setPaused() {} };

    let raf = 0;
    let running = !motionBlocked();
    let cols = [];
    let font = 14;
    let lastW = 0;
    let lastH = 0;

    function size() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = canvas.clientWidth || window.innerWidth;
      const h = canvas.clientHeight || window.innerHeight;
      canvas.width = Math.max(1, Math.round(w * dpr));
      canvas.height = Math.max(1, Math.round(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      font = w < 420 ? 13 : 15;
      const n = Math.max(8, Math.floor(w / font));
      if (n !== cols.length || w !== lastW || h !== lastH) {
        const prev = cols;
        cols = Array.from({ length: n }, (_, i) => {
          const old = prev[i];
          return {
            y: old ? old.y : Math.random() * (h / font),
            speed: 0.35 + Math.random() * 0.55,
            purple: i % 3 === 0,
          };
        });
        lastW = w;
        lastH = h;
      }
      return { w, h };
    }

    function paintStatic() {
      const { w, h } = size();
      ctx.clearRect(0, 0, w, h);
      ctx.font = `${font}px "SF Mono", "Consolas", ui-monospace, monospace`;
      ctx.textBaseline = "top";
      for (let i = 0; i < cols.length; i += 1) {
        const x = i * font;
        const y = ((i * 17) % Math.max(1, Math.floor(h / font))) * font;
        const [r, g, b] = cols[i].purple ? PURPLE : CYAN;
        ctx.fillStyle = `rgba(${r},${g},${b},0.09)`;
        ctx.fillText(GLYPHS[(i * 7) % GLYPHS.length], x, y);
      }
    }

    function frame() {
      if (!running) return;
      const { w, h } = size();
      const pulsing = pulseUntil > Date.now();
      const fade = pulsing ? 0.07 : 0.1;
      ctx.fillStyle = `rgba(7, 6, 11, ${fade})`;
      ctx.fillRect(0, 0, w, h);
      ctx.font = `${font}px "SF Mono", "Consolas", ui-monospace, monospace`;
      ctx.textBaseline = "top";
      const boost = pulsing ? 0.08 : 0;
      for (let i = 0; i < cols.length; i += 1) {
        const col = cols[i];
        const x = i * font;
        const y = col.y * font;
        let [r, g, b] = col.purple ? PURPLE : CYAN;
        if (pulsing && pulseKind === "error") {
          r = 255;
          g = 107;
          b = 44;
        } else if (pulsing && pulseKind === "draft_ready" && col.purple) {
          r = 0;
          g = 210;
          b = 255;
        }
        const ch = GLYPHS[Math.floor(Math.random() * GLYPHS.length)];
        ctx.fillStyle = `rgba(${r},${g},${b},${0.16 + boost})`;
        ctx.fillText(ch, x, y);
        col.y += col.speed;
        if (y > h && Math.random() > 0.975) col.y = -2;
      }
      raf = window.requestAnimationFrame(frame);
    }

    function go() {
      running = document.visibilityState !== "hidden" && !motionBlocked();
      window.cancelAnimationFrame(raf);
      if (running) {
        raf = window.requestAnimationFrame(frame);
      } else {
        paintStatic();
      }
    }

    window.addEventListener("resize", () => {
      size();
      if (!running) paintStatic();
    });
    document.addEventListener("visibilitychange", go);
    go();
    const ctl = {
      stop() {
        running = false;
        window.cancelAnimationFrame(raf);
      },
      setPaused(paused) {
        if (paused) {
          running = false;
          window.cancelAnimationFrame(raf);
          paintStatic();
          return;
        }
        go();
      },
    };
    fieldCtl = ctl;
    return ctl;
  }

  function setPaused(paused) {
    if (fieldCtl && typeof fieldCtl.setPaused === "function") fieldCtl.setPaused(paused);
  }

  function pulse(kind) {
    if (motionBlocked()) return;
    pulseKind = String(kind || "");
    pulseUntil = Date.now() + 720;
  }

  window.ASFFoundry = { startField, setPaused, pulse };
})();
