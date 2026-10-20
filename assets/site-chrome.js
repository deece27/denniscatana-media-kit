/* Sitewide header nav toggle + ultra-wide ambient reel wallpaper. */
(function () {
  function wireNav() {
    const header = document.querySelector(".site-header");
    const toggle = document.querySelector(".nav-toggle");
    const nav = document.getElementById("site-nav");
    if (!header || !toggle || !nav) return;

    const setOpen = (open) => {
      header.classList.toggle("is-nav-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    };

    toggle.addEventListener("click", (e) => {
      e.stopPropagation();
      setOpen(!header.classList.contains("is-nav-open"));
    });

    document.addEventListener("click", (e) => {
      if (!header.classList.contains("is-nav-open")) return;
      if (e.target.closest(".site-header")) return;
      setOpen(false);
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") setOpen(false);
    });

    nav.querySelectorAll("a").forEach((a) => {
      a.addEventListener("click", () => setOpen(false));
    });
  }

  const ICONS = {
    ig: `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="17.5" cy="6.5" r="1.2" fill="currentColor"/></svg>`,
    tiktok: `<img class="plat-logo-img" src="assets/tiktok-icon.png" alt="" width="24" height="24" />`,
    youtube: `<img class="plat-logo-img" src="assets/youtube-icon.png" alt="" width="24" height="24" />`,
    youtubeShorts: `<img class="plat-logo-img" src="assets/youtube-shorts-icon.png" alt="" width="24" height="24" />`,
  };

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fmt(n) {
    if (n == null || n === "") return "—";
    const x = Number(n);
    if (!Number.isFinite(x)) return "—";
    if (x >= 1_000_000) return (x / 1_000_000).toFixed(x >= 10_000_000 ? 1 : 2).replace(/\.0$/, "") + "M";
    if (x >= 10_000) return Math.round(x / 1000) + "K";
    if (x >= 1000) return (x / 1000).toFixed(1).replace(/\.0$/, "") + "K";
    return String(Math.round(x));
  }

  function thumbSrc(url) {
    if (!url) return "";
    if (/\.heic(\?|$)/i.test(url)) {
      return `https://wsrv.nl/?url=${encodeURIComponent(url)}&output=jpg`;
    }
    return url;
  }

  function isLandscapeFilm(post) {
    if (!post || post.platform !== "YouTube") return false;
    const t = post.title || "";
    if (/urge to cycle|so you have the urge/i.test(t)) return true;
    const durRaw = post.duration;
    let dur = null;
    if (durRaw != null && durRaw !== "") {
      if (typeof durRaw === "number") dur = durRaw;
      else if (/^\d+(\.\d+)?$/.test(String(durRaw).trim())) dur = Number(durRaw);
    }
    const typedLong = (post.type || "").toLowerCase() === "long";
    if (dur != null && dur >= 90 && typedLong && !/\bDay\s*\d+/i.test(t)) return true;
    return false;
  }

  function platClass(platform) {
    if (platform === "TikTok") return "plat-tiktok";
    if (platform === "YouTube") return "plat-youtube";
    return "plat-ig";
  }

  function platLogo(post) {
    if (post.platform === "YouTube") {
      if (isLandscapeFilm(post)) return ICONS.youtube;
      return ICONS.youtubeShorts;
    }
    if (post.platform === "TikTok") return ICONS.tiktok;
    return ICONS.ig;
  }

  function renderCard(post) {
    const src = thumbSrc(post.thumbnail);
    if (!src || !post.url) return "";
    return `
      <a class="ambient-card ${platClass(post.platform)}" href="${escapeHtml(post.url)}" target="_blank" rel="noopener" title="${escapeHtml(post.title || post.platform)}">
        <span class="ambient-card-frame">
          <img src="${escapeHtml(src)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" />
          <span class="ambient-card-plat" aria-hidden="true">${platLogo(post)}</span>
          <span class="ambient-card-views" aria-hidden="true">${fmt(post.views)}</span>
        </span>
      </a>`;
  }

  function fillLane(laneEl, posts) {
    if (!laneEl || !posts.length) return;
    const need = Math.min(14, Math.max(8, posts.length));
    const seq = [];
    for (let i = 0; i < need; i++) seq.push(posts[i % posts.length]);
    const track = seq.map(renderCard).join("");
    laneEl.innerHTML = `<div class="ambient-track">${track}${track}</div>`;
  }

  async function paintAmbient() {
    const root = document.getElementById("site-ambient");
    if (!root) return;
    try {
      const res = await fetch("assets/projects-data.json", { cache: "no-cache" });
      if (!res.ok) throw new Error("no projects data");
      const data = await res.json();
      const seen = new Set();
      const pool = [];
      for (const project of data.projects || []) {
        for (const post of project.posts || []) {
          if (!post?.url || !post?.thumbnail) continue;
          if (isLandscapeFilm(post)) continue;
          const key = post.permalinkId || post.url;
          if (seen.has(key)) continue;
          seen.add(key);
          pool.push(post);
        }
      }
      pool.sort((a, b) => (Number(b.views) || 0) - (Number(a.views) || 0));
      if (pool.length < 8) {
        root.hidden = true;
        return;
      }
      const lanes = [[], [], [], []];
      pool.forEach((post, i) => lanes[i % 4].push(post));
      root.querySelectorAll(".ambient-lane").forEach((laneEl) => {
        const idx = Number(laneEl.dataset.lane) || 0;
        fillLane(laneEl, lanes[idx].length ? lanes[idx] : pool);
      });
      root.hidden = false;
    } catch (_) {
      root.hidden = true;
    }
  }

  wireNav();
  paintAmbient();
})();
