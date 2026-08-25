(() => {
  const reduced =
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function startField(canvas) {
    if (!canvas || reduced) return { stop() {} };
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return { stop() {} };

    const N = 52;
    const pts = Array.from({ length: N }, () => {
      const u = Math.random() * Math.PI * 2;
      const v = Math.acos(2 * Math.random() - 1);
      const r = 0.42 + Math.random() * 0.58;
      return {
        x: r * Math.sin(v) * Math.cos(u),
        y: r * Math.sin(v) * Math.sin(u),
        z: r * Math.cos(v),
        ember: Math.random() > 0.55,
      };
    });

    let raf = 0;
    let t = 0;
    let running = true;

    function size() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const w = canvas.clientWidth || window.innerWidth;
      const h = canvas.clientHeight || window.innerHeight;
      canvas.width = Math.max(1, Math.round(w * dpr));
      canvas.height = Math.max(1, Math.round(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return { w, h };
    }

    function project(p, w, h, rotY, rotX) {
      const cy = Math.cos(rotY);
      const sy = Math.sin(rotY);
      const cx = Math.cos(rotX);
      const sx = Math.sin(rotX);
      const x1 = p.x * cy - p.z * sy;
      const z1 = p.x * sy + p.z * cy;
      const y2 = p.y * cx - z1 * sx;
      const z2 = p.y * sx + z1 * cx;
      const f = 1.35 / (1.7 + z2);
      return { x: w * 0.5 + x1 * f * Math.min(w, h) * 0.42, y: h * 0.46 + y2 * f * Math.min(w, h) * 0.42, z: z2, ember: p.ember };
    }

    function frame() {
      if (!running) return;
      const { w, h } = size();
      t += 0.0042;
      ctx.clearRect(0, 0, w, h);
      const projected = pts.map((p) => project(p, w, h, t, t * 0.37));
      projected.sort((a, b) => a.z - b.z);
      for (let i = 0; i < projected.length; i += 1) {
        const a = projected[i];
        for (let j = i + 1; j < projected.length; j += 1) {
          const b = projected[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const dist = Math.hypot(dx, dy);
          if (dist > 92) continue;
          const alpha = (1 - dist / 92) * 0.16;
          ctx.strokeStyle = a.ember
            ? `rgba(255, 132, 64, ${alpha})`
            : `rgba(92, 225, 230, ${alpha})`;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        const r = 1.4 + (a.z + 1.2) * 0.9;
        ctx.fillStyle = a.ember
          ? "rgba(255, 150, 72, 0.85)"
          : "rgba(120, 236, 240, 0.8)";
        ctx.beginPath();
        ctx.arc(a.x, a.y, r, 0, Math.PI * 2);
        ctx.fill();
      }
      raf = window.requestAnimationFrame(frame);
    }

    function onVis() {
      running = document.visibilityState !== "hidden";
      if (running) {
        window.cancelAnimationFrame(raf);
        raf = window.requestAnimationFrame(frame);
      }
    }

    window.addEventListener("resize", size);
    document.addEventListener("visibilitychange", onVis);
    raf = window.requestAnimationFrame(frame);
    return {
      stop() {
        running = false;
        window.cancelAnimationFrame(raf);
        window.removeEventListener("resize", size);
        document.removeEventListener("visibilitychange", onVis);
      },
    };
  }

  window.ASFFoundry = { startField };
})();
