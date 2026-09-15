const KEY_ALIASES = {
  ArrowUp: "ArrowUp",
  ArrowDown: "ArrowDown",
  ArrowLeft: "ArrowLeft",
  ArrowRight: "ArrowRight",
  w: "ArrowUp",
  W: "ArrowUp",
  s: "ArrowDown",
  S: "ArrowDown",
  a: "ArrowLeft",
  A: "ArrowLeft",
  d: "ArrowRight",
  D: "ArrowRight",
};

const DEFAULT_LABEL = {
  ArrowUp: "↑",
  ArrowDown: "↓",
  ArrowLeft: "←",
  ArrowRight: "→",
};

const el = {
  clip: document.getElementById("clip"),
  fallback: document.getElementById("fallback"),
  fallbackTitle: document.getElementById("fallback-title"),
  fallbackSub: document.getElementById("fallback-sub"),
  prompt: document.getElementById("prompt"),
  title: document.getElementById("title"),
  status: document.getElementById("status"),
  flash: document.getElementById("flash"),
};

/** @type {any} */
let adventure = null;
let checkpointId = null;
let nodeId = null;
let nodeStartedAt = 0;
let promptArmed = false;
let promptResolved = false;
let awaitingAdvance = false;
/** @type {number | null} */
let raf = null;
/** @type {ReturnType<typeof setTimeout> | null} */
let fallbackTimer = null;

function adventureUrl() {
  const params = new URLSearchParams(location.search);
  return params.get("adventure") || "../examples/placeholder/adventure.json";
}

function resolveClip(path) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  const base = adventure.assetsBase || ".";
  const adventureDir = new URL(adventureUrl(), location.href);
  const assets = new URL(base.endsWith("/") ? base : `${base}/`, adventureDir);
  return new URL(path, assets).href;
}

function setStatus(text) {
  el.status.textContent = text;
}

function showFlash(kind) {
  el.flash.hidden = false;
  el.flash.className = kind;
  setTimeout(() => {
    el.flash.hidden = true;
    el.flash.className = "";
  }, 180);
}

function hidePrompt() {
  el.prompt.hidden = true;
  el.prompt.className = "";
  el.prompt.textContent = "";
}

function showPrompt(prompt) {
  el.prompt.hidden = false;
  el.prompt.className = "";
  el.prompt.textContent = prompt.label || DEFAULT_LABEL[prompt.input] || "?";
}

function clearTimers() {
  if (raf != null) cancelAnimationFrame(raf);
  raf = null;
  if (fallbackTimer != null) clearTimeout(fallbackTimer);
  fallbackTimer = null;
  el.clip.onended = null;
  el.clip.pause();
}

function go(nextId) {
  if (!nextId || !adventure.nodes[nextId]) {
    setStatus(`Missing node: ${nextId || "(empty)"}`);
    return;
  }
  playNode(nextId);
}

function lastCheckpoint() {
  return checkpointId || adventure.start;
}

async function playNode(id) {
  clearTimers();
  hidePrompt();
  promptArmed = false;
  promptResolved = false;
  awaitingAdvance = false;
  nodeId = id;

  const node = adventure.nodes[id];
  if (node.checkpoint) checkpointId = id;

  setStatus(node.kind === "death" ? `Death · ${id}` : id);
  nodeStartedAt = performance.now();

  const clipUrl = resolveClip(node.clip);
  let usedVideo = false;

  if (clipUrl) {
    try {
      el.clip.hidden = false;
      el.fallback.hidden = true;
      el.clip.src = clipUrl;
      await el.clip.play();
      usedVideo = true;
    } catch {
      usedVideo = false;
    }
  }

  if (!usedVideo) {
    el.clip.removeAttribute("src");
    el.clip.load();
    el.clip.hidden = true;
    el.fallback.hidden = false;
    const fb = node.fallback || {};
    el.fallback.style.background = fb.bg || "#1a1a1a";
    el.fallbackTitle.textContent = fb.title || id;
    el.fallbackSub.textContent = fb.subtitle || "";
  }

  const durationMs =
    (usedVideo && el.clip.duration && Number.isFinite(el.clip.duration)
      ? el.clip.duration * 1000
      : null) ||
    node.durationMs ||
    3000;

  if (node.prompt && node.kind !== "death") {
    tickPrompt(node, durationMs, usedVideo);
  } else {
    scheduleComplete(node, durationMs, usedVideo);
  }
}

function scheduleComplete(node, durationMs, usedVideo) {
  const finish = () => {
    if (awaitingAdvance || promptResolved) return;
    awaitingAdvance = true;
    const next =
      node.kind === "death"
        ? node.onComplete || lastCheckpoint()
        : node.onComplete || adventure.start;
    go(next);
  };

  if (usedVideo) {
    el.clip.onended = finish;
  } else {
    fallbackTimer = setTimeout(finish, durationMs);
  }
}

function tickPrompt(node, durationMs, usedVideo) {
  const prompt = node.prompt;

  const loop = () => {
    if (promptResolved) return;
    const elapsed = performance.now() - nodeStartedAt;

    if (!promptArmed && elapsed >= prompt.atMs) {
      promptArmed = true;
      showPrompt(prompt);
    }

    if (promptArmed && elapsed >= prompt.atMs + prompt.windowMs) {
      resolvePrompt("timeout", node);
      return;
    }

    if (!usedVideo && elapsed >= durationMs && !promptArmed) {
      // No prompt ever armed (mis-authored); fall through.
      awaitingAdvance = true;
      go(node.onComplete || adventure.start);
      return;
    }

    raf = requestAnimationFrame(loop);
  };

  raf = requestAnimationFrame(loop);

  if (usedVideo) {
    el.clip.onended = () => {
      if (!promptResolved) resolvePrompt("timeout", node);
    };
  }
}

function resolvePrompt(result, node) {
  if (promptResolved) return;
  promptResolved = true;
  clearTimers();

  const ok = result === "success";
  if (promptArmed) {
    el.prompt.className = ok ? "ok" : "fail";
  }
  showFlash(ok ? "ok" : "fail");
  setStatus(ok ? "Clear!" : result === "timeout" ? "Too slow!" : "Wrong!");

  const next = ok
    ? node.onSuccess
    : result === "timeout"
      ? node.onTimeout || node.onFail
      : node.onFail;

  setTimeout(() => go(next || lastCheckpoint()), 220);
}

function onKeyDown(event) {
  const mapped = KEY_ALIASES[event.key];
  if (!mapped || !nodeId || promptResolved) return;

  const node = adventure.nodes[nodeId];
  if (!node?.prompt || node.kind === "death") return;
  if (!promptArmed) return;

  event.preventDefault();
  if (mapped === node.prompt.input) {
    resolvePrompt("success", node);
  } else {
    resolvePrompt("fail", node);
  }
}

async function main() {
  const url = adventureUrl();
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load adventure: ${url}`);
  adventure = await res.json();

  if (adventure.version !== 1) {
    throw new Error(`Unsupported adventure version: ${adventure.version}`);
  }
  if (!adventure.nodes?.[adventure.start]) {
    throw new Error(`Missing start node: ${adventure.start}`);
  }

  el.title.textContent = adventure.title;
  document.title = `${adventure.title} · FMV Game Maker`;
  checkpointId = adventure.start;
  window.addEventListener("keydown", onKeyDown);
  playNode(adventure.start);
}

main().catch((err) => {
  console.error(err);
  setStatus(String(err.message || err));
  el.fallback.hidden = false;
  el.fallback.style.background = "#3a1010";
  el.fallbackTitle.textContent = "Failed to load adventure";
  el.fallbackSub.textContent = String(err.message || err);
});
