(() => {
  const TOKEN_KEY = "asf_console_token";
  const STATUS_LABELS = {
    new: "новое",
    processed: "отработано",
    needs_clarification: "уточняется",
    conflict: "конфликт",
    rejected: "отклонено",
    superseded: "заменено",
  };
  const STATUS_COLORS = {
    new: { background: "#3d8bfd", border: "#7eb3ff" },
    processed: { background: "#3ecf8e", border: "#7be0b2" },
    needs_clarification: { background: "#e4c27a", border: "#f0d59a" },
    conflict: { background: "#e05a4f", border: "#ff8a80" },
    rejected: { background: "#6b7380", border: "#9aa3b0" },
    superseded: { background: "#8b7bb8", border: "#b9aad8" },
  };
  const STAGE_COLORS = {
    PROJECT_CREATED: "#6b7380",
    UNDERSTANDING_IDEA: "#e4c27a",
    BUSINESS_CONTEXT: "#7eb3ff",
    USERS: "#3ecf8e",
    FUNCTIONAL: "#5aa7ff",
    DATA: "#8b7bb8",
    NON_FUNCTIONAL: "#d4a24a",
    INTEGRATIONS: "#e07a3d",
    ACCEPTANCE: "#3ecf8e",
    RISKS: "#e05a4f",
    REVIEW: "#9b8bb8",
    READY_FOR_OWNER: "#7be0b2",
    UNSCOPED: "#5c6770",
  };
  const EDGE_COLORS = {
    structure: "#4b5a6a",
    depends_on: "#e4a23c",
    conflicts_with: "#e05a4f",
  };
  const KIND_RU = {
    project: "проект",
    stage: "этап",
    topic: "раздел",
    requirement: "требование",
  };
  const PRIORITY_LABELS = {
    must: "must",
    should: "should",
    could: "could",
  };
  const PRODUCT_RU = {
    website: "сайт",
    telegram_bot: "Telegram-бот",
    rest_service: "REST-сервис",
    ai_automation: "AI-автоматизация",
    mobile_native: "нативное приложение",
  };

  const JOB_STATUS_RU = {
    queued: "в очереди",
    preparing: "готовим brief",
    waiting_intervention: "ждём ваши ответы",
    running: "собирается",
    ready_for_client: "готово к review клиента",
    sent_to_client: "отправлено клиенту",
    failed: "ошибка",
    cancelled: "отменено",
  };

  const $ = (id) => document.getElementById(id);
  const state = {
    graph: null,
    expanded: new Set(),
    network: null,
    nodesDS: null,
    edgesDS: null,
    selectedId: null,
    anim: null,
    iconMap: { topics: {}, stages: {}, products: {}, fallback: "circle-dot" },
    files: { files: [], history: [], stages: [], current_stage: "" },
    factory: {
      job: null,
      interventions: [],
      can_create: false,
      can_send: false,
      gate: "",
      message: "",
    },
  };

  function iconFile(name) {
    return `./icons/${name}.svg`;
  }

  function iconForNode(n) {
    const map = state.iconMap || {};
    if (n.kind === "project") {
      const pt =
        (state.graph && state.graph.project && state.graph.project.product_type) ||
        "default";
      return (map.products && (map.products[pt] || map.products.default)) || "hexagon";
    }
    if (n.kind === "stage") {
      return (map.stages && map.stages[n.stage]) || map.fallback || "folder-open";
    }
    if (n.kind === "topic") {
      const tid = n.topic_id || String(n.id || "").replace(/^topic:/, "");
      return (map.topics && map.topics[tid]) || map.fallback || "circle-dot";
    }
    return null;
  }

  function iconImg(node, cls) {
    const name = iconForNode(node);
    if (!name) {
      const dot = node.kind === "requirement" ? node.status || "new" : node.kind;
      return `<i class="dot ${escapeHtml(dot)}"></i>`;
    }
    return `<img class="${cls}" src="${iconFile(name)}" alt="" width="24" height="24">`;
  }

  function wrapLabel(text, width = 16) {
    const raw = String(text || "").trim();
    if (raw.length <= width) return raw;
    const words = raw.split(/\s+/);
    const lines = [];
    let line = "";
    for (const w of words) {
      const next = line ? `${line} ${w}` : w;
      if (next.length > width && line) {
        lines.push(line);
        line = w;
      } else {
        line = next;
      }
    }
    if (line && lines.length < 2) lines.push(line);
    let out = lines.join("\n");
    if (raw.length > width * 2) out = `${out.slice(0, width * 2 - 1)}…`;
    return out;
  }

  function childrenOf(parentId) {
    return (state.graph.nodes || []).filter((n) => n.parent === parentId);
  }

  function requirementLeaves(nodeId) {
    const out = [];
    const walk = (id) => {
      for (const child of childrenOf(id)) {
        if (child.kind === "requirement") out.push(child);
        else walk(child.id);
      }
    };
    walk(nodeId);
    return out;
  }

  function statusBreakdown(nodes) {
    const counts = {};
    for (const n of nodes) {
      const key = n.status || "new";
      counts[key] = (counts[key] || 0) + 1;
    }
    return counts;
  }

  function ringRadius(kind, count) {
    const base = { stage: 230, topic: 390, requirement: 560 }[kind] || 560;
    return base + Math.max(0, count - 10) * 8;
  }

  function radialPositions(visible) {
    const pos = {};
    const project = visible.find((n) => n.kind === "project");
    if (!project) return pos;
    pos[project.id] = { x: 0, y: 0 };

    const byParent = new Map();
    const byKind = { stage: 0, topic: 0, requirement: 0 };
    for (const n of visible) {
      if (byKind[n.kind] != null) byKind[n.kind] += 1;
      const key = n.parent || "";
      if (!byParent.has(key)) byParent.set(key, []);
      byParent.get(key).push(n);
    }

    function weight(node) {
      const kids = byParent.get(node.id) || [];
      if (!kids.length) return 1;
      return kids.reduce((sum, child) => sum + weight(child), 0);
    }

    function place(parentId, a0, a1) {
      const kids = byParent.get(parentId) || [];
      if (!kids.length) return;
      const weights = kids.map(weight);
      const total = weights.reduce((a, b) => a + b, 0) || 1;
      const gap = kids.length > 1 ? 0.04 : 0;
      const usable = a1 - a0 - gap * kids.length;
      let a = a0;
      kids.forEach((child, i) => {
        const span = (usable * weights[i]) / total;
        const mid = a + span / 2;
        const r = ringRadius(child.kind, byKind[child.kind] || 1);
        pos[child.id] = { x: r * Math.cos(mid), y: r * Math.sin(mid) };
        place(child.id, a, a + span);
        a += span + gap;
      });
    }

    place(project.id, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2);
    return pos;
  }

  function visNode(n, pos) {
    const p = pos[n.id] || { x: 0, y: 0 };
    const frozen = { x: true, y: true };
    const font = {
      color: "#d7e0ea",
      size: 12,
      face: "Segoe UI",
      strokeWidth: 4,
      strokeColor: "#07090d",
      vadjust: 2,
    };
    if (n.kind === "project") {
      const image = iconFile(iconForNode(n));
      return {
        id: n.id,
        label: wrapLabel(n.label, 14),
        title: n.label,
        x: 0,
        y: 0,
        fixed: frozen,
        physics: false,
        shape: "image",
        image,
        brokenImage: iconFile("hexagon"),
        size: 36,
        shapeProperties: { useBorderWithImage: false },
        color: { background: "rgba(0,0,0,0)", border: "#e4c27a", highlight: "#f0d59a" },
        font: { ...font, size: 15, color: "#f4ead2" },
        borderWidth: 0,
        shadow: { enabled: true, color: "rgba(228,194,122,0.55)", size: 28, x: 0, y: 0 },
      };
    }
    if (n.kind === "stage" || n.kind === "topic") {
      const isStage = n.kind === "stage";
      const hue = STAGE_COLORS[n.stage] || "#5aa7ff";
      const count = childrenOf(n.id).length;
      const image = iconFile(iconForNode(n));
      return {
        id: n.id,
        label: `${wrapLabel(n.label, isStage ? 12 : 14)}\n${count}`,
        title: `${n.label} · ${count} ${isStage ? "разделов" : "требований"}`,
        x: p.x,
        y: p.y,
        fixed: frozen,
        physics: false,
        shape: "image",
        image,
        brokenImage: iconFile("circle-dot"),
        size: isStage ? 26 : 20,
        shapeProperties: { useBorderWithImage: false },
        color: {
          background: "rgba(0,0,0,0)",
          border: hue,
          highlight: "#ffffff",
        },
        font: { ...font, size: isStage ? 12 : 11 },
        borderWidth: 0,
        shadow: { enabled: true, color: hue, size: isStage ? 18 : 12, x: 0, y: 0 },
      };
    }
    const colors = STATUS_COLORS[n.status] || STATUS_COLORS.new;
    return {
      id: n.id,
      label: wrapLabel(n.label, 18),
      title: n.label,
      x: p.x,
      y: p.y,
      fixed: frozen,
      physics: false,
      shape: "dot",
      size: n.has_conflict ? 11 : 8,
      color: {
        background: colors.background,
        border: n.has_conflict ? "#ff8a80" : colors.border,
        highlight: "#ffffff",
      },
      borderWidth: n.has_conflict ? 2 : 1,
      font: { ...font, size: 11 },
      shadow: { enabled: true, color: "rgba(0,0,0,0.3)", size: 8, x: 0, y: 0 },
    };
  }

  function visEdge(e, dashed) {
    const color = EDGE_COLORS[e.kind] || EDGE_COLORS.structure;
    const structural = e.kind === "structure";
    return {
      id: e.id + (dashed ? ":proxy" : ""),
      from: e.from,
      to: e.to,
      arrows: structural ? "" : "to",
      color: { color, opacity: dashed ? 0.35 : structural ? 0.32 : 0.7 },
      dashes: dashed || !structural,
      width: e.kind === "conflicts_with" ? 1.8 : e.kind === "depends_on" ? 1.5 : 0.9,
      smooth: { enabled: false },
    };
  }

  function visibleGraph() {
    const visible = state.graph.nodes.filter((n) => isVisible(n, state.expanded));
    const visibleIds = new Set(visible.map((n) => n.id));
    const byId = nodeMap();
    const pos = radialPositions(visible);
    const visNodes = visible.map((n) => visNode(n, pos));
    const visEdges = [];
    const seen = new Set();
    for (const e of state.graph.edges) {
      const fromVis = visibleIds.has(e.from);
      const toVis = visibleIds.has(e.to);
      if (fromVis && toVis) {
        visEdges.push(visEdge({ ...e, from: e.from, to: e.to }, false));
        continue;
      }
      if (e.kind === "structure") continue;
      const a = visibleAnchor(e.from, byId, visibleIds);
      const b = visibleAnchor(e.to, byId, visibleIds);
      if (!a || !b || a === b) continue;
      const key = `${e.kind}:${a}:${b}`;
      if (seen.has(key)) continue;
      seen.add(key);
      visEdges.push(visEdge({ ...e, id: key, from: a, to: b }, true));
    }
    return { visNodes, visEdges, pos };
  }

  function networkOptions(height, width) {
    return {
      autoResize: true,
      height: `${height}px`,
      width: `${width}px`,
      layout: { improvedLayout: false },
      physics: { enabled: false },
      interaction: {
        hover: true,
        tooltipDelay: 180,
        zoomView: true,
        dragView: true,
        dragNodes: false,
        selectable: true,
      },
      nodes: {
        chosen: true,
        scaling: { min: 8, max: 42 },
      },
      edges: { selectionWidth: 0, hoverWidth: 0, chosen: false },
    };
  }

  function stopAnim() {
    if (state.anim) {
      cancelAnimationFrame(state.anim);
      state.anim = null;
    }
  }

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function animateMove(targets, duration = 680) {
    stopAnim();
    const start = {};
    let moved = false;
    for (const [id, dest] of Object.entries(targets)) {
      const cur = state.nodesDS.get(id);
      const sx = cur && cur.x != null ? cur.x : dest.x;
      const sy = cur && cur.y != null ? cur.y : dest.y;
      start[id] = { x: sx, y: sy };
      if (Math.hypot(dest.x - sx, dest.y - sy) > 1) moved = true;
    }
    if (!moved) return Promise.resolve();
    const t0 = performance.now();
    return new Promise((resolve) => {
      function tick(now) {
        const t = Math.min(1, (now - t0) / duration);
        const e = easeOutCubic(t);
        const updates = [];
        for (const [id, dest] of Object.entries(targets)) {
          const s = start[id];
          updates.push({
            id,
            x: s.x + (dest.x - s.x) * e,
            y: s.y + (dest.y - s.y) * e,
            fixed: { x: true, y: true },
            physics: false,
          });
        }
        state.nodesDS.update(updates);
        if (t < 1) {
          state.anim = requestAnimationFrame(tick);
        } else {
          state.anim = null;
          resolve();
        }
      }
      state.anim = requestAnimationFrame(tick);
    });
  }

  function ensureNetwork(container, visNs, visNodes, visEdges) {
    const height = Math.max(container.clientHeight, 480);
    const width = Math.max(container.clientWidth, 320);
    container.style.height = `${height}px`;
    state.nodesDS = new visNs.DataSet(visNodes);
    state.edgesDS = new visNs.DataSet(visEdges);
    state.network = new visNs.Network(
      container,
      { nodes: state.nodesDS, edges: state.edgesDS },
      networkOptions(height, width)
    );
    state.network.on("click", onGraphClick);
    state.network.on("hoverNode", (p) => applyFocus(p.node));
    state.network.on("blurNode", () => applyFocus(state.selectedId));
    requestAnimationFrame(() => {
      try {
        state.network.fit({ animation: false });
      } catch (_) {
        /* ignore */
      }
    });
  }

  function spawnAtParent(n) {
    const data = nodeMap().get(n.id);
    const parentPos = data && data.parent && state.nodesDS.get(data.parent);
    return {
      ...n,
      x: parentPos ? parentPos.x : 0,
      y: parentPos ? parentPos.y : 0,
      fixed: { x: true, y: true },
      physics: false,
    };
  }

  async function syncNetwork(visNodes, visEdges, { animate = false } = {}) {
    const nextNodeIds = new Set(visNodes.map((n) => n.id));
    const nextEdgeIds = new Set(visEdges.map((e) => e.id));
    const currentIds = state.nodesDS.getIds();
    const dropNodes = currentIds.filter((id) => !nextNodeIds.has(id));
    const existingNodes = new Set(currentIds);
    const targets = {};
    const toAdd = [];
    const toUpdate = [];

    for (const n of visNodes) {
      targets[n.id] = { x: n.x, y: n.y };
      if (existingNodes.has(n.id)) {
        const cur = state.nodesDS.get(n.id);
        toUpdate.push({
          ...n,
          x: animate ? cur.x : n.x,
          y: animate ? cur.y : n.y,
          fixed: { x: true, y: true },
          physics: false,
        });
      } else if (animate) {
        toAdd.push(spawnAtParent(n));
      } else {
        toAdd.push({ ...n, fixed: { x: true, y: true }, physics: false });
      }
    }

    if (animate) {
      for (const id of dropNodes) {
        const data = nodeMap().get(id);
        const parentPos = data && data.parent && state.nodesDS.get(data.parent);
        const cur = state.nodesDS.get(id);
        targets[id] = parentPos
          ? { x: parentPos.x, y: parentPos.y }
          : { x: cur ? cur.x : 0, y: cur ? cur.y : 0 };
      }
    }

    if (toAdd.length) state.nodesDS.add(toAdd);
    if (toUpdate.length) state.nodesDS.update(toUpdate);

    const existingEdges = new Set(state.edgesDS.getIds());
    const addEdges = visEdges.filter((e) => !existingEdges.has(e.id));
    if (addEdges.length) state.edgesDS.add(addEdges);

    if (animate) await animateMove(targets);

    if (dropNodes.length) state.nodesDS.remove(dropNodes);
    const dropEdges = state.edgesDS.getIds().filter((id) => !nextEdgeIds.has(id));
    if (dropEdges.length) state.edgesDS.remove(dropEdges);

    if (!animate) {
      const snap = visNodes.map((n) => ({
        id: n.id,
        x: n.x,
        y: n.y,
        fixed: { x: true, y: true },
        physics: false,
      }));
      if (snap.length) state.nodesDS.update(snap);
    }
    applyFocus(state.selectedId);
  }

  function applyFocus(focusId) {
    if (!state.nodesDS || !state.network) return;
    const keep = new Set();
    if (focusId && state.nodesDS.get(focusId)) {
      keep.add(focusId);
      try {
        state.network.getConnectedNodes(focusId).forEach((id) => keep.add(id));
      } catch (_) {
        /* ignore */
      }
      let cur = nodeMap().get(focusId);
      while (cur && cur.parent) {
        keep.add(cur.parent);
        cur = nodeMap().get(cur.parent);
      }
    }
    const updates = state.nodesDS.getIds().map((id) => ({
      id,
      opacity: !focusId || keep.has(id) ? 1 : 0.18,
    }));
    if (updates.length) state.nodesDS.update(updates);
  }

  function updateHud() {
    const el = $("hud-stats");
    if (!el || !state.graph) {
      if (el) el.textContent = "Выберите проект";
      return;
    }
    const nodes = state.graph.nodes || [];
    const reqs = nodes.filter((n) => n.kind === "requirement");
    const stages = nodes.filter((n) => n.kind === "stage").length;
    const topics = nodes.filter((n) => n.kind === "topic").length;
    const conflicts = reqs.filter((n) => n.has_conflict).length;
    const fresh = reqs.filter((n) => n.status === "new").length;
    el.textContent = [
      `${stages} этапов`,
      `${topics} разделов`,
      `${reqs.length} требований`,
      fresh ? `${fresh} новых` : null,
      conflicts ? `${conflicts} конфликтов` : null,
    ]
      .filter(Boolean)
      .join("  ·  ");
  }

  function renderGraph({ animate = false } = {}) {
    const container = $("graph");
    const visNs = window.vis;
    if (!state.graph) return;
    if (!visNs || !visNs.Network || !visNs.DataSet) {
      showError("Библиотека графа не загрузилась. Обновите страницу (Ctrl+F5).");
      return;
    }
    try {
      const { visNodes, visEdges } = visibleGraph();
      updateHud();
      if (!state.network) {
        ensureNetwork(container, visNs, visNodes, visEdges);
      } else {
        syncNetwork(visNodes, visEdges, { animate });
      }
    } catch (err) {
      showError(err && err.message ? err.message : String(err));
    }
  }

  function token() {
    return sessionStorage.getItem(TOKEN_KEY) || $("console-token").value.trim();
  }

  function headers() {
    const h = { Accept: "application/json" };
    const t = token();
    if (t) {
      h["X-Console-Token"] = t;
      h["Authorization"] = "Bearer " + t;
    }
    return h;
  }

  function showAuthFailure(detail) {
    const el = $("auth-banner");
    el.classList.remove("hidden");
    if (detail === "invalid console token") {
      el.textContent =
        "Токен неверный. Вставьте CONSOLE_TOKEN с последнего деплоя и нажмите «Сохранить».";
      return "Неверный токен консоли";
    }
    el.textContent = "Нужен CONSOLE_TOKEN. Вставьте его в шапку и сохраните.";
    return "Нужен токен консоли";
  }

  function showError(msg) {
    const el = $("error-banner");
    if (!msg) {
      el.classList.add("hidden");
      el.textContent = "";
      return;
    }
    el.textContent = msg;
    el.classList.remove("hidden");
  }

  async function api(path, options = {}) {
    const isForm = typeof FormData !== "undefined" && options.body instanceof FormData;
    const res = await fetch(path, {
      ...options,
      headers: {
        ...headers(),
        ...(options.body && !isForm ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
    if (res.status === 401) {
      let detail = "";
      try {
        const body = await res.json();
        detail = body.detail || "";
      } catch (_) {
        /* ignore */
      }
      throw new Error(showAuthFailure(detail));
    }
    $("auth-banner").classList.add("hidden");
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail || JSON.stringify(body);
      } catch (_) {
        /* ignore */
      }
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  async function loadProjects() {
    const projects = await api("/console/api/projects");
    const sel = $("project-select");
    const current = sel.value;
    sel.innerHTML = '<option value="">— выберите —</option>';
    for (const p of projects) {
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = `${p.name} (${p.status})`;
      sel.appendChild(opt);
    }
    if (current && [...sel.options].some((o) => o.value === current)) {
      sel.value = current;
    }
  }

  function nodeMap() {
    const map = new Map();
    for (const n of state.graph.nodes) map.set(n.id, n);
    return map;
  }

  function isVisible(node, expanded) {
    if (node.kind === "project") return true;
    return expanded.has(node.parent);
  }

  function visibleAnchor(id, byId, visibleIds) {
    let cur = byId.get(id);
    while (cur && !visibleIds.has(cur.id)) {
      cur = cur.parent ? byId.get(cur.parent) : null;
    }
    return cur ? cur.id : null;
  }

  function collapseBranch(id) {
    state.expanded.delete(id);
    for (const child of childrenOf(id)) collapseBranch(child.id);
  }

  function expandPath(id) {
    let cur = nodeMap().get(id);
    while (cur) {
      state.expanded.add(cur.id);
      cur = cur.parent ? nodeMap().get(cur.parent) : null;
    }
  }

  function toggleBranch(node) {
    if (state.expanded.has(node.id)) {
      collapseBranch(node.id);
      return;
    }
    if (node.kind === "stage") {
      for (const stage of (state.graph.nodes || []).filter((n) => n.kind === "stage")) {
        if (stage.id !== node.id) collapseBranch(stage.id);
      }
    }
    state.expanded.add(node.id);
  }

  function showSheet(html) {
    $("panel-hint").classList.add("hidden");
    const body = $("panel-body");
    body.classList.remove("hidden");
    body.innerHTML = html;
    body.querySelectorAll("[data-go]").forEach((btn) => {
      btn.onclick = () => inspectNode(btn.getAttribute("data-go"), { toggle: false });
    });
    body.querySelectorAll("[data-del-rel]").forEach((btn) => {
      btn.onclick = () => delRel(btn.getAttribute("data-del-rel"));
    });
    body.querySelectorAll("[data-tz-export]").forEach((btn) => {
      btn.onclick = () => exportTz(btn.getAttribute("data-tz-export"));
    });
    body.querySelectorAll("[data-file-dl]").forEach((btn) => {
      btn.onclick = () => downloadProjectFile(btn.getAttribute("data-file-dl"));
    });
    body.querySelectorAll("[data-file-del]").forEach((btn) => {
      btn.onclick = () => deleteProjectFile(btn.getAttribute("data-file-del"));
    });
    const fileAdd = $("file-add");
    if (fileAdd) fileAdd.onclick = () => addProjectFile();
    const statusSave = $("status-save");
    if (statusSave) statusSave.onclick = () => saveStatus(state.selectedId);
    const relAdd = $("rel-add");
    if (relAdd) relAdd.onclick = () => addRel(state.selectedId);
    const textSave = $("req-text-save");
    if (textSave) textSave.onclick = () => saveRequirementText(state.selectedId);
    const reqAdd = $("req-add");
    if (reqAdd) reqAdd.onclick = () => addRequirement();
    const mvpCreate = $("mvp-create");
    if (mvpCreate) mvpCreate.onclick = () => createMvp();
    const mvpSend = $("mvp-send");
    if (mvpSend) mvpSend.onclick = () => sendMvpToClient();
    body.querySelectorAll("[data-iv-resolve]").forEach((btn) => {
      btn.onclick = () => resolveIntervention(btn.getAttribute("data-iv-resolve"));
    });
  }

  function countChips(breakdown, extra = []) {
    const chips = extra.concat(
      Object.entries(breakdown).map(
        ([k, v]) =>
          `<span class="count-chip"><i class="dot ${escapeHtml(k)}"></i> ${v} ${escapeHtml(
            STATUS_LABELS[k] || k
          )}</span>`
      )
    );
    return chips.length ? `<div class="counts">${chips.join("")}</div>` : "";
  }

  function rosterHtml(nodes, metaFn) {
    if (!nodes.length) return "<p class=\"hint\">Пока пусто</p>";
    const items = nodes
      .map((n) => {
        const meta = metaFn ? metaFn(n) : "";
        return `<li><button type="button" class="roster-item" data-go="${escapeHtml(n.id)}">
          ${iconImg(n, "roster-icon")}
          <span class="roster-title">${escapeHtml(n.label)}</span>
          <span class="roster-meta">${escapeHtml(meta)}</span>
        </button></li>`;
      })
      .join("");
    return `<ul class="roster">${items}</ul>`;
  }

  function estimateHtml(est) {
    if (!est) {
      return `<p class="hint">Оценка стоимости появится, когда в проекте будут требования.</p>`;
    }
    const rationale = (est.rationale || [])
      .map((line) => `<li>${escapeHtml(line)}</li>`)
      .join("");
    const capNote = est.capped
      ? ` <span class="hint">(потолок ${escapeHtml(est.formatted_hours || "")} ч, без потолка ${escapeHtml(
          est.formatted_hours_uncapped || ""
        )} ч)</span>`
      : "";
    return `
      <h3>Оценка стоимости</h3>
      <p class="hint">Подсказка для HITL владельца, не цена клиенту.</p>
      <div class="estimate-hero">
        <div class="estimate-cost">${escapeHtml(est.formatted_cost || "—")}</div>
        <div class="estimate-hours">~${escapeHtml(est.formatted_hours || "—")} ч × ${escapeHtml(
          est.formatted_rate || "—"
        )}${capNote}</div>
      </div>
      <div class="meta">
        <div>Тип в оценке: <b>${escapeHtml(est.product_type_label || est.product_type || "—")}</b></div>
        <div>Ориентир заказчика: <b>${escapeHtml(est.customer_budget_label || "не указан")}</b></div>
        <div>Сравнение с ориентиром: <b>${escapeHtml(est.budget_fit_label || "—")}</b></div>
        <div>Метод: <b>${escapeHtml(est.method || "heuristic_v1")}</b></div>
      </div>
      ${countChips({}, [
        `<span class="count-chip">must ${Number(est.must_count) || 0}</span>`,
        `<span class="count-chip">should ${Number(est.should_count) || 0}</span>`,
        `<span class="count-chip">could ${Number(est.could_count) || 0}</span>`,
        `<span class="count-chip">пропущено ${Number(est.skipped_requirement_count) || 0}</span>`,
        `<span class="count-chip">открытых вопросов ${Number(est.open_question_count) || 0}</span>`,
        `<span class="count-chip">рисков ${Number(est.risk_count) || 0}</span>`,
      ])}
      <h3>Почему так</h3>
      <ul class="estimate-rationale">${rationale || "<li>—</li>"}</ul>
    `;
  }

  function factoryHtml(factory) {
    const snap = factory || {};
    const job = snap.job;
    const items = snap.interventions || [];
    const status = job ? JOB_STATUS_RU[job.status] || job.status : "ещё не создан";
    const openItems = items.filter((i) => i.status === "open");
    const ivHtml = items.length
      ? items
          .map((iv) => {
            const secret = iv.answer_type === "secret";
            const resolved = iv.status === "resolved";
            const input = resolved
              ? `<p class="hint">${
                  secret
                    ? "Секрет принят (не показывается)."
                    : escapeHtml(iv.answer_preview || "ответ записан")
                }</p>`
              : `<label class="field">
                  ${secret ? "Секрет" : "Ответ"}
                  <input id="iv-${escapeHtml(iv.id)}" type="${
                    secret ? "password" : "text"
                  }" autocomplete="off" />
                </label>
                <button type="button" class="btn" data-iv-resolve="${escapeHtml(
                  iv.id
                )}">Ответить</button>`;
            return `<li class="factory-iv">
              <div class="factory-iv-title">${escapeHtml(iv.kind_label || iv.kind)}</div>
              <p class="hint">${escapeHtml(iv.question || "")}</p>
              <div class="meta">Тип: <b>${secret ? "секрет" : "текст"}</b> · статус: <b>${escapeHtml(
                iv.status
              )}</b></div>
              ${input}
            </li>`;
          })
          .join("")
      : "<p class=\"hint\">Очередь вмешательств пуста.</p>";
    const createBtn = snap.can_create
      ? `<button type="button" class="btn primary" id="mvp-create">Создать MVP</button>`
      : `<p class="hint">Сначала утвердите ТЗ (HITL approve). Если появится клиентская смета — после её confirm.</p>`;
    const sendBtn = snap.can_send
      ? `<button type="button" class="btn primary" id="mvp-send">Отправить клиенту на review</button>`
      : "";
    const link = job && job.deep_link
      ? `<div class="meta">Brief / export: <b>${escapeHtml(job.deep_link)}</b></div>`
      : "";
    return `
      <h3>MVP Factory</h3>
      <p class="hint">Сборка из approved MVP-среза. Секреты только в Intervention Queue, не в графе.</p>
      <div class="factory-hero">
        <div class="factory-status">${escapeHtml(status)}</div>
        <div class="meta">
          <div>Исполнитель: <b>${escapeHtml((job && job.executor) || "—")}</b></div>
          <div>Открытых вопросов: <b>${openItems.length}</b></div>
        </div>
        ${link}
        ${snap.message ? `<p class="hint">${escapeHtml(snap.message)}</p>` : ""}
      </div>
      <div class="export-row">
        ${createBtn}
        ${sendBtn}
      </div>
      <h3>Intervention Queue</h3>
      <ul class="factory-queue">${ivHtml}</ul>
    `;
  }

  async function loadFactory() {
    const pid = state.graph && state.graph.project && state.graph.project.id;
    if (!pid) return;
    state.factory = await api(`/console/api/projects/${pid}/mvp`);
  }

  async function createMvp() {
    const pid = state.graph && state.graph.project && state.graph.project.id;
    if (!pid) return;
    try {
      state.factory = await api(`/console/api/projects/${pid}/mvp`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      const node = nodeMap().get(state.selectedId) || nodeMap().get(`project:${pid}`);
      if (node) renderGroupPanel(node);
    } catch (err) {
      showError(err.message);
    }
  }

  async function sendMvpToClient() {
    const pid = state.graph && state.graph.project && state.graph.project.id;
    if (!pid) return;
    try {
      state.factory = await api(`/console/api/projects/${pid}/mvp/send-to-client`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      const node = nodeMap().get(state.selectedId);
      if (node) renderGroupPanel(node);
    } catch (err) {
      showError(err.message);
    }
  }

  async function resolveIntervention(id) {
    const input = $(`iv-${id}`);
    const answer = input ? input.value : "";
    if (!answer.trim()) {
      showError("Введите ответ");
      return;
    }
    try {
      state.factory = await api(`/console/api/interventions/${id}/resolve`, {
        method: "POST",
        body: JSON.stringify({ answer }),
      });
      const node = nodeMap().get(state.selectedId);
      if (node) renderGroupPanel(node);
    } catch (err) {
      showError(err.message);
    }
  }

  function renderGroupPanel(node) {
    const leaves = requirementLeaves(node.id);
    const kids = childrenOf(node.id);
    const breakdown = statusBreakdown(leaves);
    const badge = iconImg(node, "sheet-icon");
    if (node.kind === "project") {
      const info = state.graph.project || {};
      showSheet(`
        ${badge}
        <p class="kicker">${escapeHtml(KIND_RU.project)}</p>
        <h2>${escapeHtml(node.label)}</h2>
        ${countChips(breakdown, [
          `<span class="count-chip">${kids.length} этапов</span>`,
          `<span class="count-chip">${leaves.length} требований</span>`,
        ])}
        <div class="meta">
          <div>Тип продукта: <b>${escapeHtml(PRODUCT_RU[info.product_type] || info.product_type || "—")}</b></div>
          <div>Статус проекта: <b>${escapeHtml(info.status || "—")}</b></div>
        </div>
        ${estimateHtml(info.estimate)}
        ${factoryHtml(state.factory)}
        <h3>Выгрузить полное ТЗ</h3>
        <div class="export-row">
          <button type="button" class="btn" data-tz-export="md">Markdown</button>
          <button type="button" class="btn" data-tz-export="docx">Word</button>
          <button type="button" class="btn primary" data-tz-export="pdf">PDF</button>
        </div>
        ${filesHtml(state.files)}
        <h3>Этапы</h3>
        ${rosterHtml(kids, (s) => `${requirementLeaves(s.id).length} тр.`)}
      `);
      return;
    }
    if (node.kind === "stage") {
      showSheet(`
        ${badge}
        <p class="kicker">${escapeHtml(KIND_RU.stage)}</p>
        <h2>${escapeHtml(node.label)}</h2>
        ${countChips(breakdown, [
          `<span class="count-chip">${kids.length} разделов</span>`,
          `<span class="count-chip">${leaves.length} требований</span>`,
        ])}
        <p class="hint">Клик по разделу на карте или в списке раскрывает листья и открывает его карточку.</p>
        <h3>Разделы</h3>
        ${rosterHtml(kids, (t) => `${childrenOf(t.id).length}`)}
        ${addRequirementForm(kids.filter((k) => k.kind === "topic"))}
      `);
      return;
    }
    showSheet(`
      ${badge}
      <p class="kicker">${escapeHtml(KIND_RU.topic)}</p>
      <h2>${escapeHtml(node.label)}</h2>
      ${countChips(breakdown, [`<span class="count-chip">${kids.length} требований</span>`])}
      <h3>Требования</h3>
      ${rosterHtml(kids, (r) => STATUS_LABELS[r.status] || r.status || "")}
      ${addRequirementForm([], node.topic_id || String(node.id || "").replace(/^topic:/, ""))}
    `);
  }

  async function inspectNode(id, { toggle = false } = {}) {
    const node = nodeMap().get(id);
    if (!node) return;
    state.selectedId = id;
    if (node.kind === "requirement") {
      expandPath(node.parent);
      renderGraph({ animate: false });
      await loadRequirement(id);
      applyFocus(id);
      return;
    }
    if (toggle && (node.kind === "stage" || node.kind === "topic")) {
      toggleBranch(node);
      renderGraph({ animate: true });
    } else {
      expandPath(id);
      if (node.kind === "stage" || node.kind === "topic") state.expanded.add(id);
      renderGraph({ animate: false });
    }
    if (node.kind === "project") {
      try {
        await loadProjectFiles();
        await loadFactory();
      } catch (err) {
        showError(err.message);
      }
    }
    renderGroupPanel(node);
    applyFocus(id);
  }

  function onGraphClick(params) {
    if (!params.nodes.length) {
      const project = state.graph.nodes.find((n) => n.kind === "project");
      if (project) inspectNode(project.id);
      return;
    }
    const node = nodeMap().get(params.nodes[0]);
    if (!node) return;
    const toggle = node.kind === "stage" || node.kind === "topic";
    inspectNode(node.id, { toggle });
  }

  async function loadGraph(projectId, { keepView = false } = {}) {
    const prevExpanded = keepView ? new Set(state.expanded) : null;
    const prevSelected = keepView ? state.selectedId : null;
    state.graph = await api(`/console/api/projects/${projectId}/tz-graph`);
    const projectNode = state.graph.nodes.find((n) => n.kind === "project");
    if (keepView && prevExpanded) {
      state.expanded = prevExpanded;
      state.selectedId = prevSelected;
    } else {
      state.expanded = new Set(projectNode ? [projectNode.id] : []);
      state.selectedId = projectNode ? projectNode.id : null;
      if (state.network) {
        state.network.destroy();
        state.network = null;
        state.nodesDS = null;
        state.edgesDS = null;
        $("graph").innerHTML = "";
      }
    }
    renderGraph();
    const selected = nodeMap().get(state.selectedId) || projectNode;
    if (selected && selected.kind === "requirement") {
      await loadRequirement(selected.id);
    } else if (selected) {
      if (selected.kind === "project") {
        try {
          await loadProjectFiles();
        } catch (err) {
          showError(err.message);
        }
      }
      renderGroupPanel(selected);
    }
  }

  function escapeHtml(s) {
    return String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatDate(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("ru-RU");
    } catch (_) {
      return iso;
    }
  }

  function formatSize(bytes) {
    const n = Number(bytes) || 0;
    if (n < 1024) return `${n} Б`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} КБ`;
    return `${(n / (1024 * 1024)).toFixed(1)} МБ`;
  }

  function filesHtml(bundle) {
    const files = (bundle && bundle.files) || [];
    const history = (bundle && bundle.history) || [];
    const stages = (bundle && bundle.stages) || [];
    const current = (bundle && bundle.current_stage) || "";
    const stageOpts = stages
      .map(
        (s) =>
          `<option value="${escapeHtml(s.id)}" ${s.id === current ? "selected" : ""}>${escapeHtml(
            s.label
          )}</option>`
      )
      .join("");
    const rows = files
      .map((f) => {
        const src = f.source === "console" ? "консоль" : "заказчик";
        const download = f.downloadable
          ? `<button type="button" class="btn" data-file-dl="${escapeHtml(f.id)}">Скачать</button>`
          : `<span class="hint">нет файла</span>`;
        const del = f.legacy
          ? ""
          : `<button type="button" class="btn" data-file-del="${escapeHtml(f.id)}">Удалить</button>`;
        return `<li class="file-row">
          <div class="file-main">
            <span class="file-name">${escapeHtml(f.filename)}</span>
            <span class="roster-meta">${escapeHtml(f.stage_label || f.stage || "—")} · ${escapeHtml(
              formatDate(f.created_at)
            )} · ${escapeHtml(src)} · ${escapeHtml(formatSize(f.size_bytes))}</span>
          </div>
          <div class="file-actions">${download}${del}</div>
        </li>`;
      })
      .join("");
    const hist = history.length
      ? `<ul class="history">${history
          .map((h) => {
            const name = (h.payload && h.payload.filename) || "";
            const stage = (h.payload && h.payload.stage) || "";
            const stageLabel =
              (stages.find((s) => s.id === stage) || {}).label || stage || "—";
            let what = h.action;
            if (h.action === "created") what = "загружен";
            if (h.action === "deleted") what = "удалён";
            return `<li>${escapeHtml(formatDate(h.created_at))} · ${escapeHtml(
              h.actor || ""
            )} · ${escapeHtml(what)} · ${escapeHtml(name)} · ${escapeHtml(stageLabel)}</li>`;
          })
          .join("")}</ul>`
      : `<p class="hint">Пока нет записей</p>`;
    return `
      <h3>Файлы проекта</h3>
      ${files.length ? `<ul class="file-list">${rows}</ul>` : `<p class="hint">Файлов пока нет</p>`}
      <div class="form-row">
        <select id="file-stage">${stageOpts}</select>
        <input id="project-file-input" type="file" />
        <button type="button" class="btn primary" id="file-add">Добавить файл</button>
      </div>
      <h3>История файлов</h3>
      ${hist}
    `;
  }

  function topicOptions(selectedId) {
    return (state.graph.nodes || [])
      .filter((n) => n.kind === "topic")
      .map((n) => {
        const tid = n.topic_id || String(n.id).replace(/^topic:/, "");
        const sel = tid === selectedId ? "selected" : "";
        return `<option value="${escapeHtml(tid)}" ${sel}>${escapeHtml(n.label)}</option>`;
      })
      .join("");
  }

  function priorityOptions(selected) {
    const cur = selected || "should";
    return Object.entries(PRIORITY_LABELS)
      .map(
        ([k, v]) =>
          `<option value="${k}" ${k === cur ? "selected" : ""}>${escapeHtml(v)}</option>`
      )
      .join("");
  }

  function addRequirementForm(topicNodes, fixedTopicId) {
    const topicField = fixedTopicId
      ? `<input type="hidden" id="new-req-topic" value="${escapeHtml(fixedTopicId)}" />`
      : `<select id="new-req-topic"><option value="">— раздел —</option>${(topicNodes || [])
          .map((n) => {
            const tid = n.topic_id || String(n.id).replace(/^topic:/, "");
            return `<option value="${escapeHtml(tid)}">${escapeHtml(n.label)}</option>`;
          })
          .join("")}</select>`;
    return `
      <h3>Новое требование</h3>
      <div class="form-row">
        ${topicField}
        <select id="new-req-priority">${priorityOptions("should")}</select>
        <textarea id="new-req-text" rows="3" placeholder="Текст требования"></textarea>
        <button type="button" class="btn primary" id="req-add">Добавить требование</button>
      </div>
    `;
  }

  function historyHtml(history) {
    if (!history || !history.length) return "<li>Пока нет записей</li>";
    return history
      .map((h) => {
        const when = formatDate(h.created_at);
        const actor = h.actor || "";
        if (h.action === "created") {
          return `<li>${escapeHtml(when)} · ${escapeHtml(actor)} · создано</li>`;
        }
        if (h.action === "updated") {
          const fields = (h.payload && h.payload.fields) || {};
          const bits = [];
          if (fields.description) {
            bits.push(
              `текст: «${fields.description.from || ""}» → «${fields.description.to || ""}»`
            );
          }
          if (fields.topic_id) {
            bits.push(`раздел: ${fields.topic_id.from || "—"} → ${fields.topic_id.to || "—"}`);
          }
          if (fields.priority) {
            bits.push(`приоритет: ${fields.priority.from || "—"} → ${fields.priority.to || "—"}`);
          }
          return `<li>${escapeHtml(when)} · ${escapeHtml(actor)} · правка · ${escapeHtml(
            bits.join("; ") || "поля"
          )}</li>`;
        }
        const bits = [when, actor, h.action];
        if (h.from_status || h.to_status) bits.push(`${h.from_status || "—"} → ${h.to_status || "—"}`);
        if (h.reason) bits.push(h.reason);
        return `<li>${escapeHtml(bits.join(" · "))}</li>`;
      })
      .join("");
  }

  function requirementOptions(exceptId) {
    return (state.graph.nodes || [])
      .filter((n) => n.kind === "requirement" && n.id !== exceptId)
      .map(
        (n) =>
          `<option value="${escapeHtml(n.id)}">${escapeHtml(n.label)}</option>`
      )
      .join("");
  }

  function renderRequirementPanel(card) {
    const author =
      [card.author && card.author.role, card.author && card.author.id]
        .filter(Boolean)
        .join(" / ") || "—";
    const statusOpts = Object.entries(STATUS_LABELS)
      .map(
        ([k, v]) =>
          `<option value="${k}" ${k === card.status ? "selected" : ""}>${v}</option>`
      )
      .join("");
    const links = (card.links || [])
      .map((l) => {
        const kind =
          l.kind === "depends_on"
            ? "зависимость"
            : l.kind === "conflicts_with"
              ? "конфликт"
              : l.type;
        const canDel = l.kind === "depends_on" || l.kind === "conflicts_with";
        const del = canDel
          ? `<button type="button" class="btn" data-del-rel="${escapeHtml(l.id)}">Снять</button>`
          : "";
        const peer =
          l.kind === "depends_on" || l.kind === "conflicts_with"
            ? `<button type="button" class="link-peer" data-go="${escapeHtml(l.peer_id)}">${escapeHtml(
                l.peer_name || l.peer_id
              )}</button>`
            : escapeHtml(l.peer_name || l.peer_id);
        return `<li><span class="kind-tag">${escapeHtml(kind)}</span>${peer} ${del}</li>`;
      })
      .join("") || "<li>Нет связей</li>";
    const history = historyHtml(card.history);

    const reqNode = nodeMap().get(card.id);
    const parent =
      (card.topic_id && nodeMap().get(`topic:${card.topic_id}`)) ||
      (reqNode && reqNode.parent ? nodeMap().get(reqNode.parent) : null);

    showSheet(`
      <p class="kicker">${escapeHtml(KIND_RU.requirement)} · <span class="status-pill ${escapeHtml(
        card.status || "new"
      )}">${escapeHtml(STATUS_LABELS[card.status] || card.status)}</span></p>
      <h2>${escapeHtml(card.name || card.description || "Требование")}</h2>
      <div class="meta">
        <div>Дата: <b>${escapeHtml(formatDate(card.created_at))}</b></div>
        <div>Автор: <b>${escapeHtml(author)}</b></div>
        <div>Раздел: ${
          parent
            ? `<button type="button" class="link-peer" data-go="${escapeHtml(parent.id)}">${escapeHtml(
                parent.label
              )}</button>`
            : `<b>${escapeHtml(card.topic_id || "—")}</b>`
        }</div>
        ${card.reason ? `<div>Причина: <b>${escapeHtml(card.reason)}</b></div>` : ""}
      </div>
      <h3>Текст требования</h3>
      <div class="form-row">
        <select id="req-topic">${topicOptions(card.topic_id)}</select>
        <select id="req-priority">${priorityOptions(card.priority)}</select>
        <textarea id="req-description" rows="5">${escapeHtml(card.description || "")}</textarea>
        <button type="button" class="btn primary" id="req-text-save">Сохранить правку</button>
      </div>
      <h3>Связи</h3>
      <ul class="links">${links}</ul>
      <h3>История</h3>
      <ul class="history">${history}</ul>
      <h3>Статус</h3>
      <div class="form-row">
        <select id="status-select">${statusOpts}</select>
        <textarea id="status-reason" rows="2" placeholder="Причина (обязательна для «отклонено»)">${escapeHtml(
          card.reason || ""
        )}</textarea>
        <button type="button" class="btn primary" id="status-save">Сохранить статус</button>
      </div>
      <h3>Новая связь</h3>
      <div class="form-row">
        <select id="rel-type">
          <option value="depends_on">зависит от</option>
          <option value="conflicts_with">конфликт с</option>
        </select>
        <select id="rel-peer">
          <option value="">— требование —</option>
          ${requirementOptions(card.id)}
        </select>
        <button type="button" class="btn" id="rel-add">Добавить</button>
      </div>
    `);
  }

  async function loadRequirement(id) {
    const pid = $("project-select").value;
    state.selectedId = id;
    const card = await api(`/console/api/projects/${pid}/requirements/${id}`);
    renderRequirementPanel(card);
  }

  async function saveRequirementText(id) {
    const pid = $("project-select").value;
    const description = $("req-description").value;
    const topicId = $("req-topic").value;
    const priority = $("req-priority").value;
    showError("");
    try {
      await api(`/console/api/projects/${pid}/requirements/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          description,
          topic_id: topicId || null,
          priority: priority || null,
        }),
      });
      await loadGraph(pid, { keepView: true });
    } catch (err) {
      showError(err.message);
    }
  }

  async function addRequirement() {
    const pid = $("project-select").value;
    const topicEl = $("new-req-topic");
    const textEl = $("new-req-text");
    const prioEl = $("new-req-priority");
    const topicId = topicEl ? topicEl.value.trim() : "";
    const description = textEl ? textEl.value.trim() : "";
    if (!topicId) {
      showError("Выберите раздел");
      return;
    }
    if (!description) {
      showError("Введите текст требования");
      return;
    }
    showError("");
    try {
      const card = await api(`/console/api/projects/${pid}/requirements`, {
        method: "POST",
        body: JSON.stringify({
          description,
          topic_id: topicId,
          priority: prioEl ? prioEl.value : "should",
        }),
      });
      await loadGraph(pid, { keepView: true });
      const topicNode = nodeMap().get(`topic:${topicId}`);
      if (topicNode) {
        state.expanded.add(topicNode.id);
        if (topicNode.parent) state.expanded.add(topicNode.parent);
      }
      renderGraph({ animate: true });
      await inspectNode(card.id);
    } catch (err) {
      showError(err.message);
    }
  }

  async function saveStatus(id) {
    const pid = $("project-select").value;
    const status = $("status-select").value;
    const reason = $("status-reason").value.trim();
    showError("");
    try {
      await api(`/console/api/projects/${pid}/requirements/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ status, reason: reason || null }),
      });
      await loadGraph(pid, { keepView: true });
    } catch (err) {
      showError(err.message);
    }
  }

  async function addRel(id) {
    const pid = $("project-select").value;
    const type = $("rel-type").value;
    const peerId = $("rel-peer").value;
    if (!peerId) return;
    showError("");
    try {
      await api(`/console/api/projects/${pid}/requirements/${id}/relations`, {
        method: "POST",
        body: JSON.stringify({ type, peer_id: peerId }),
      });
      await loadGraph(pid, { keepView: true });
    } catch (err) {
      showError(err.message);
    }
  }

  async function delRel(relId) {
    const pid = $("project-select").value;
    showError("");
    try {
      await api(`/console/api/projects/${pid}/relations/${relId}`, { method: "DELETE" });
      await loadGraph(pid, { keepView: true });
      if (state.selectedId) await inspectNode(state.selectedId);
    } catch (err) {
      showError(err.message);
    }
  }

  async function exportTz(fmt) {
    const pid = $("project-select").value;
    if (!pid || !fmt) return;
    showError("");
    try {
      const res = await fetch(`/console/api/projects/${pid}/tz-export?format=${encodeURIComponent(fmt)}`, {
        headers: headers(),
      });
      if (res.status === 401) {
        let detail = "";
        try {
          const body = await res.json();
          detail = body.detail || "";
        } catch (_) {
          /* ignore */
        }
        throw new Error(showAuthFailure(detail));
      }
      if (!res.ok) {
        let detail = res.statusText;
        try {
          const body = await res.json();
          detail = body.detail || JSON.stringify(body);
        } catch (_) {
          /* ignore */
        }
        throw new Error(detail);
      }
      const blob = await res.blob();
      const cd = res.headers.get("Content-Disposition") || "";
      const star = cd.match(/filename\*=UTF-8''([^;]+)/i);
      const plain = cd.match(/filename="?([^";]+)"?/i);
      const name = decodeURIComponent((star && star[1]) || (plain && plain[1]) || `tz.${fmt}`);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1500);
    } catch (err) {
      showError(err.message || String(err));
    }
  }

  async function loadProjectFiles() {
    const pid = $("project-select").value;
    if (!pid) {
      state.files = { files: [], history: [], stages: [], current_stage: "" };
      return state.files;
    }
    state.files = await api(`/console/api/projects/${pid}/files`);
    return state.files;
  }

  async function addProjectFile() {
    const pid = $("project-select").value;
    const input = $("project-file-input");
    const stageEl = $("file-stage");
    if (!pid || !input || !input.files || !input.files[0]) {
      showError("Выберите файл");
      return;
    }
    showError("");
    const form = new FormData();
    form.append("file", input.files[0]);
    if (stageEl && stageEl.value) form.append("stage", stageEl.value);
    try {
      state.files = await api(`/console/api/projects/${pid}/files`, {
        method: "POST",
        body: form,
      });
      const project = state.graph.nodes.find((n) => n.kind === "project");
      if (project) renderGroupPanel(project);
    } catch (err) {
      showError(err.message);
    }
  }

  async function deleteProjectFile(fileId) {
    const pid = $("project-select").value;
    if (!pid || !fileId) return;
    if (!window.confirm("Удалить файл из проекта?")) return;
    showError("");
    try {
      state.files = await api(`/console/api/projects/${pid}/files/${fileId}`, {
        method: "DELETE",
      });
      const project = state.graph.nodes.find((n) => n.kind === "project");
      if (project) renderGroupPanel(project);
    } catch (err) {
      showError(err.message);
    }
  }

  async function downloadProjectFile(fileId) {
    const pid = $("project-select").value;
    if (!pid || !fileId) return;
    showError("");
    try {
      const res = await fetch(`/console/api/projects/${pid}/files/${fileId}/content`, {
        headers: headers(),
      });
      if (res.status === 401) {
        let detail = "";
        try {
          const body = await res.json();
          detail = body.detail || "";
        } catch (_) {
          /* ignore */
        }
        throw new Error(showAuthFailure(detail));
      }
      if (!res.ok) {
        let detail = res.statusText;
        try {
          const body = await res.json();
          detail = body.detail || JSON.stringify(body);
        } catch (_) {
          /* ignore */
        }
        throw new Error(detail);
      }
      const blob = await res.blob();
      const cd = res.headers.get("Content-Disposition") || "";
      const star = cd.match(/filename\*=UTF-8''([^;]+)/i);
      const plain = cd.match(/filename="?([^";]+)"?/i);
      const name = decodeURIComponent((star && star[1]) || (plain && plain[1]) || "file");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = name;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1500);
    } catch (err) {
      showError(err.message || String(err));
    }
  }

  function runSearch(query) {
    const q = query.trim().toLowerCase();
    if (!q || !state.graph) return;
    const hits = state.graph.nodes.filter((n) =>
      String(n.label || "").toLowerCase().includes(q)
    );
    if (!hits.length) {
      showError("Ничего не найдено");
      return;
    }
    showError("");
    inspectNode(hits[0].id, { toggle: false });
  }

  $("token-save").onclick = async () => {
    sessionStorage.setItem(TOKEN_KEY, $("console-token").value.trim());
    showError("");
    try {
      await loadProjects();
    } catch (err) {
      showError(err.message);
    }
  };

  $("project-select").onchange = async () => {
    const pid = $("project-select").value;
    showError("");
    if (!pid) return;
    try {
      await loadGraph(pid);
    } catch (err) {
      showError(err.message);
    }
  };

  $("panel-close").onclick = () => {
    const project = state.graph && state.graph.nodes.find((n) => n.kind === "project");
    if (project) inspectNode(project.id);
  };

  $("graph-search").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") runSearch(ev.target.value);
  });

  $("console-token").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") $("token-save").click();
  });
  $("console-token").value = sessionStorage.getItem(TOKEN_KEY) || "";

  async function boot() {
    loadProjects().catch((err) => showError(err.message));
    if (!window.vis || !window.vis.Network) {
      showError("Не загрузилась библиотека графа (vendor/vis-network.min.js). Обновите страницу (Ctrl+F5).");
      return;
    }
    try {
      const map = await fetch("./icons/map.json").then((res) => {
        if (!res.ok) throw new Error("icon map");
        return res.json();
      });
      state.iconMap = map;
      const names = new Set([
        ...Object.values(map.topics || {}),
        ...Object.values(map.stages || {}),
        ...Object.values(map.products || {}),
        map.fallback || "circle-dot",
      ]);
      await Promise.all(
        [...names].map(
          (name) =>
            new Promise((resolve) => {
              const img = new Image();
              img.onload = img.onerror = resolve;
              img.src = iconFile(name);
            })
        )
      );
    } catch (_) {
      /* graph still works as colored dots if icons fail */
    }
  }
  boot();
  if (window.ASFFoundry) {
    window.ASFFoundry.startField(document.getElementById("foundry-field"));
  }
})();
