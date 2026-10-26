/* Shared behaviour for the three design mockups: kit shirts, the pitch (with an animated switch
   between "Your XI" and "Best XI"), the deadline countdown, expanding panels and count-ups.
   Data comes from data.js, a real snapshot from the API (2026-10-26, GW9). */

// Club kits as flat colours: body, sleeves, and an optional stripe colour. No crests or logos.
const KITS = {
  ARS: ["#e2231a", "#ffffff"], AVL: ["#670e36", "#95bfe5"], BOU: ["#d8231c", "#111111", "#111111"],
  BRE: ["#e30613", "#ffffff", "#ffffff"], BHA: ["#0057b8", "#0057b8", "#ffffff"], CHE: ["#034694", "#034694"],
  COV: ["#62b5e5", "#ffffff"], CRY: ["#1b458f", "#c4122e", "#c4122e"], EVE: ["#003399", "#003399"],
  FUL: ["#ffffff", "#111111"], HUL: ["#f18a01", "#111111", "#111111"], IPS: ["#3a64a3", "#ffffff"],
  LEE: ["#ffffff", "#1d428a"], LIV: ["#c8102e", "#c8102e"], MCI: ["#6cabdd", "#6cabdd"],
  MUN: ["#da291c", "#da291c"], NEW: ["#ffffff", "#111111", "#111111"], NFO: ["#dd0000", "#ffffff"],
  SUN: ["#eb172b", "#eb172b", "#ffffff"], TOT: ["#ffffff", "#132257"],
};

let shirtSeq = 0;
function shirt(team, size = 34) {
  const [body, sleeve, stripe] = KITS[team] || ["#888888", "#666666"];
  const id = `s${shirtSeq++}`;
  const edge = body.toLowerCase() === "#ffffff" ? "#cfcfcf" : "rgba(0,0,0,.18)";
  const stripes = stripe
    ? `<clipPath id="${id}"><path d="M14 8h20v34H14z"/></clipPath><g clip-path="url(#${id})">${[16.5, 24, 31.5]
        .map((x) => `<rect x="${x - 2}" y="8" width="4" height="34" fill="${stripe}"/>`).join("")}</g>`
    : "";
  return `<svg class="shirt" width="${size}" height="${size}" viewBox="0 0 48 48" aria-hidden="true">
    <path d="M14 6l-10 7 4 9 6-3v23h20V19l6 3 4-9-10-7c-1.5 3-4 4.5-10 4.5S15.5 9 14 6z" fill="${body}" stroke="${edge}" stroke-width="1"/>
    <path d="M14 6l-10 7 4 9 6-3zM34 6l10 7-4 9-6-3z" fill="${sleeve}"/>${stripes}
  </svg>`;
}

const money = (tenths) => `£${(tenths / 10).toFixed(1)}m`;
const one = (n) => (Math.round(n * 10) / 10).toFixed(1);
const reduced = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---- Pitch ------------------------------------------------------------------------------ */
const ROW_Y = { GKP: 86, DEF: 64, MID: 40, FWD: 16 }; // percent from the top, attacking upwards

function layout(players, rowY = ROW_Y, spread = false) {
  const rows = {};
  for (const p of players) (rows[p.pos] ||= []).push(p);
  const out = {};
  for (const [pos, list] of Object.entries(rows)) {
    const n = list.length;
    // spread: centre each player in an equal share of the width (cards need the room)
    list.forEach((p, i) => (out[p.id] = { x: spread ? ((i + 0.5) / n) * 100 : ((i + 1) / (n + 1)) * 100, y: rowY[pos] }));
  }
  return out;
}

// An FPL-style player card: the shirt on top, then a name bar and an info bar.
// The name bar takes the chance-of-playing colour, as on the FPL site.
function cardTemplate(p, { captain, vice }) {
  const chance = p.status === "a" ? "" : ` c${p.chance ?? 0}`;
  const badge = p.id === captain ? '<span class="armband">C</span>' : p.id === vice ? '<span class="armband vice">V</span>' : "";
  const pts = p.xp * (p.id === captain ? 2 : 1);
  return `${badge}<span class="pxp">${one(pts)}</span><span class="kit">${shirt(p.team, 44)}</span>
    <span class="info"><span class="pname${chance}">${p.name}</span><span class="pfix">${p.fixture.split(",")[0] || "No game"}</span></span>`;
}

function makePitch(root, { onPick, template, rowY, spread = false } = {}) {
  const field = root.querySelector(".field");
  const nodes = new Map();

  function render(players, captain, vice) {
    const pos = layout(players, rowY, spread);
    const keep = new Set(players.map((p) => p.id));
    for (const [id, el] of nodes) {
      if (!keep.has(id)) {
        el.classList.add("leaving");
        nodes.delete(id);
        setTimeout(() => el.remove(), reduced() ? 0 : 260);
      }
    }
    players.forEach((p, i) => {
      let el = nodes.get(p.id);
      const fresh = !el;
      if (fresh) {
        el = document.createElement("button");
        el.className = "player entering";
        el.type = "button";
        field.appendChild(el);
        nodes.set(p.id, el);
        el.addEventListener("click", () => onPick && onPick(el._p, el));
      }
      el._p = p;
      el.style.left = pos[p.id].x + "%";
      el.style.top = pos[p.id].y + "%";
      el.setAttribute("aria-label", `${p.name}, ${p.team}, ${one(p.xp)} expected points${p.id === captain ? ", captain" : ""}`);
      if (template) {
        el.innerHTML = template(p, { captain, vice });
      } else {
        const badge = p.id === captain ? '<span class="armband">C</span>' : p.id === vice ? '<span class="armband vice">V</span>' : "";
        const flag = p.status !== "a" ? `<span class="flag" title="${p.news}">${p.chance ?? 0}%</span>` : "";
        el.innerHTML = `${shirt(p.team)}${badge}${flag}<span class="pname">${p.name}</span><span class="pxp">${one(p.xp * (p.id === captain ? 2 : 1))}</span>`;
      }
      if (fresh) {
        el.style.transitionDelay = reduced() ? "0ms" : `${i * 28}ms`;
        requestAnimationFrame(() => requestAnimationFrame(() => el.classList.remove("entering")));
        setTimeout(() => (el.style.transitionDelay = ""), 700);
      }
    });
  }
  return { render };
}

/* ---- Deadline countdown -------------------------------------------------------------------- */
function countdown(el, iso) {
  const end = new Date(iso).getTime();
  const tick = () => {
    let s = Math.max(0, Math.floor((end - Date.now()) / 1000));
    const d = Math.floor(s / 86400); s -= d * 86400;
    const h = Math.floor(s / 3600); s -= h * 3600;
    const m = Math.floor(s / 60); s -= m * 60;
    el.textContent = d > 0 ? `${d}d ${String(h).padStart(2, "0")}h ${String(m).padStart(2, "0")}m` : `${h}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
  };
  tick();
  setInterval(tick, 1000);
}

/* ---- Expanding panels: <button data-expand="id"> toggles <div id="id" class="expand"> --------- */
function wireExpanders(scope = document) {
  scope.querySelectorAll("[data-expand]").forEach((btn) => {
    const panel = document.getElementById(btn.dataset.expand);
    btn.setAttribute("aria-controls", panel.id);
    btn.setAttribute("aria-expanded", "false");
    btn.addEventListener("click", () => {
      const open = btn.getAttribute("aria-expanded") !== "true";
      btn.setAttribute("aria-expanded", String(open));
      panel.classList.toggle("open", open);
      btn.closest("[data-card]")?.classList.toggle("is-open", open);
    });
  });
}

/* ---- Numbers that count up once when they first appear -------------------------------------- */
function countUp(el, to, decimals = 1, ms = 700) {
  if (reduced()) return (el.textContent = to.toFixed(decimals));
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / ms);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = (to * eased).toFixed(decimals);
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* ---- Player detail sheet (a small popover anchored to the tapped player) --------------------- */
function playerSheet(sheet) {
  return (p, anchor) => {
    sheet.innerHTML = `<div class="sheet-head">${shirt(p.team, 28)}<div><strong>${p.name}</strong><span>${p.team} · ${p.pos} · ${money(p.price)}</span></div></div>
      <dl><div><dt>Next fixture</dt><dd>${p.fixture || "No fixture"}</dd></div>
      <div><dt>Expected points</dt><dd class="num">${one(p.xp)}</dd></div>
      <div><dt>Owned by</dt><dd class="num">${one(p.own)}%</dd></div>
      ${p.status !== "a" ? `<div><dt>Status</dt><dd>${p.news}</dd></div>` : ""}</dl>`;
    const r = anchor.getBoundingClientRect();
    const host = sheet.offsetParent.getBoundingClientRect();
    const left = Math.min(Math.max(8, r.left - host.left + r.width / 2 - 120), host.width - 248);
    sheet.style.left = left + "px";
    sheet.style.top = r.bottom - host.top + 6 + "px";
    sheet.classList.add("show");
    const close = (e) => {
      if (!sheet.contains(e.target) && e.target !== anchor && !anchor.contains(e.target)) {
        sheet.classList.remove("show");
        document.removeEventListener("pointerdown", close);
      }
    };
    setTimeout(() => document.addEventListener("pointerdown", close), 0);
  };
}
