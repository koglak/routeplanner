"use strict";

const STALE_DAYS = 90;
const HOURS_PER_DAY = 6;

const CATEGORY = {
  art: "Sanat", history: "Tarih", archaeology: "Arkeoloji", architecture: "Mimari",
  science: "Bilim", natural_history: "Doğa tarihi", design: "Tasarım", photography: "Fotoğraf",
  religion: "Din", military: "Askerî", technology: "Teknoloji", music: "Müzik",
  ethnography: "Etnografya", contemporary: "Çağdaş", modern: "Modern", children: "Çocuk",
};
const SOURCE = {
  google: "Google", tripadvisor: "Tripadvisor", reddit: "Reddit", blog: "Blog",
  official: "Resmî site", wikidata: "Wikidata", osm: "OpenStreetMap",
};
const CONFIDENCE = [
  ["high", "Yüksek güven"], ["medium", "Orta güven"], ["low", "Düşük güven"], [null, "Veri yok"],
];
const TICKET = {
  required: "Şart", strongly_recommended: "Şiddetle önerilir",
  recommended: "Önerilir", not_needed: "Gerekmiyor",
};
const TICKET_FLAG = new Set(["required", "strongly_recommended"]);

const regionNames = new Intl.DisplayNames(["tr"], { type: "region" });
const dateFmt = new Intl.DateTimeFormat("tr", { day: "numeric", month: "long", year: "numeric" });
const collator = new Intl.Collator("tr");

const state = {
  cities: [],
  cityCache: new Map(),
  city: null,
  categories: new Set(),
  sort: "rank",
  query: "",
  lastSlug: null,
};

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const icon = (id, cls = "icon") => `<svg class="${cls}" aria-hidden="true"><use href="#i-${id}"/></svg>`;

// ---------- formatting ----------

function hours(x) {
  return String(+x.toFixed(2)).replace(".", ",");
}

function durationText(d) {
  if (!d || d.typical_min_h == null) return null;
  if (d.typical_max_h == null) return `${hours(d.typical_min_h)}+`;
  if (d.typical_min_h === d.typical_max_h) return hours(d.typical_min_h);
  return `${hours(d.typical_min_h)}–${hours(d.typical_max_h)}`;
}

function countryName(code) {
  if (!code) return "Ülke belirtilmemiş";
  try { return regionNames.of(code); } catch { return code; }
}

function flag(code) {
  if (!code || !/^[A-Z]{2}$/.test(code)) return "";
  return String.fromCodePoint(...[...code].map((c) => 0x1f1a5 + c.charCodeAt(0)));
}

function formatDate(iso) {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : dateFmt.format(d);
}

function daysSince(iso) {
  return Math.floor((Date.now() - new Date(`${iso}T00:00:00`).getTime()) / 864e5);
}

function categoryLabel(c) {
  return CATEGORY[c] ?? c.charAt(0).toLocaleUpperCase("tr") + c.slice(1).replace(/_/g, " ");
}

function midpoint(m) {
  const d = m.duration;
  if (!d || d.typical_min_h == null) return Infinity;
  return (d.typical_min_h + (d.typical_max_h ?? d.typical_min_h)) / 2;
}

// ---------- data ----------

async function getJSON(url) {
  const resp = await fetch(url);
  const body = await resp.json();
  if (!resp.ok) throw new Error(body.error || resp.statusText);
  return body;
}

async function loadCity(slug) {
  if (!state.cityCache.has(slug)) state.cityCache.set(slug, await getJSON(`/api/cities/${encodeURIComponent(slug)}`));
  return state.cityCache.get(slug);
}

// ---------- routing: #/<slug>[/<museum-id>] ----------

function parseHash() {
  const [slug, museumId] = location.hash.replace(/^#\/?/, "").split("/").map(decodeURIComponent);
  return { slug: slug || null, museumId: museumId || null };
}

function go(slug, museumId) {
  location.hash = museumId ? `#/${slug}/${museumId}` : `#/${slug}`;
}

async function route() {
  let { slug, museumId } = parseHash();
  if (!slug && state.cities.length) {
    history.replaceState(null, "", `#/${state.cities[0].slug}`);
    slug = state.cities[0].slug;
  }
  closeDrawer();
  renderNav(slug);
  if (!slug) return renderNoCities();

  if (slug !== state.lastSlug) {
    try {
      state.city = await loadCity(slug);
    } catch (e) {
      state.city = null;
      state.lastSlug = null;
      renderSheet(null);
      return renderError(slug, e.message);
    }
    state.categories.clear();
    state.lastSlug = slug;
    renderCity(true);
  } else {
    renderRows(false);
  }
  renderSheet(state.city.museums.find((m) => m.id === museumId) ?? null);
}

// ---------- drawer ----------

function renderNav(activeSlug) {
  const q = state.query.trim().toLocaleLowerCase("tr");
  const groups = new Map();
  for (const c of state.cities) {
    const country = countryName(c.country);
    const hay = `${c.name} ${c.slug} ${country}`.toLocaleLowerCase("tr");
    if (q && !hay.includes(q)) continue;
    if (!groups.has(c.country)) groups.set(c.country, { country, cities: [] });
    groups.get(c.country).cities.push(c);
  }
  const ordered = [...groups.entries()].sort((a, b) => collator.compare(a[1].country, b[1].country));

  $("#city-nav").innerHTML = ordered.length
    ? ordered.map(([code, g]) => `
      <section class="country">
        <div class="country-head"><span class="flag" aria-hidden="true">${flag(code)}</span>${esc(g.country)}</div>
        ${g.cities.sort((a, b) => collator.compare(a.name, b.name)).map((c) => `
          <a class="city-link stateful" href="#/${esc(c.slug)}" ${c.slug === activeSlug ? 'aria-current="page"' : ""}>
            ${esc(c.name)}<span class="count" aria-label="${c.museum_count} müze">${c.museum_count}</span>
          </a>`).join("")}
      </section>`).join("")
    : `<p class="nav-empty">${state.cities.length ? "Eşleşen şehir yok." : "Henüz şehir yok."}</p>`;

  const countries = new Set(state.cities.map((c) => c.country)).size;
  const museums = state.cities.reduce((n, c) => n + c.museum_count, 0);
  $("#drawer-foot").innerHTML = state.cities.length
    ? `${countries} ülke · ${state.cities.length} şehir · ${museums} müze<br>Yeni şehir: <code>/muze &lt;şehir&gt;</code>`
    : "";
}

function openDrawer() {
  $("#drawer").classList.add("open");
  $(".scrim").hidden = false;
  $("#city-search").focus();
}

function closeDrawer() {
  $("#drawer").classList.remove("open");
  $(".scrim").hidden = true;
}

// ---------- city view ----------

function visibleMuseums() {
  const list = state.city.museums.filter(
    (m) => !state.categories.size || m.category.some((c) => state.categories.has(c)),
  );
  const byRank = (a, b) => (a.popularity_rank ?? 1e9) - (b.popularity_rank ?? 1e9);
  return list.sort(state.sort === "duration" ? (a, b) => midpoint(a) - midpoint(b) || byRank(a, b) : byRank);
}

function renderCity(reveal) {
  const { city, museums } = state.city;
  $("#topbar-title").textContent = city.name;
  document.title = `${city.name} · Müze Süreleri`;

  const cats = new Map();
  for (const m of museums) for (const c of m.category) cats.set(c, (cats.get(c) ?? 0) + 1);
  const catChips = [...cats.entries()].sort((a, b) => b[1] - a[1] || collator.compare(a[0], b[0]));

  $("#view").innerHTML = `
    <div class="view-inner">
      <header class="city-head">
        <div>
          <div class="city-country"><span aria-hidden="true">${flag(city.country)}</span>${esc(countryName(city.country))}</div>
          <h1 class="city-name">${esc(city.name)}</h1>
          <div class="city-meta">
            ${museums.length} müze · ${esc(formatDate(city.queried_at))} tarihinde araştırıldı
            ${city.wikidata_id ? ` · <a href="https://www.wikidata.org/wiki/${esc(city.wikidata_id)}" target="_blank" rel="noopener">Wikidata</a>` : ""}
          </div>
        </div>
        <div class="plan-card" id="plan-card"></div>
      </header>

      <div class="toolbar">
        <div class="chips" role="group" aria-label="Kategori filtresi">
          ${catChips.map(([c, n]) => `
            <button class="chip stateful" data-cat="${esc(c)}" aria-pressed="false">
              ${icon("check", "icon sm")}${esc(categoryLabel(c))}<span class="n">${n}</span>
            </button>`).join("")}
        </div>
        <div class="segmented" role="group" aria-label="Sıralama">
          <button class="stateful" data-sort="rank" aria-pressed="true">${icon("check", "icon sm")}Popülerlik</button>
          <button class="stateful" data-sort="duration" aria-pressed="false">${icon("check", "icon sm")}Süre</button>
        </div>
      </div>

      <section class="timeline" aria-label="Ziyaret süreleri">
        <div class="axis" id="axis"></div>
        <ol class="rows" id="rows"></ol>
        <div class="key">
          <span><i class="sw c-high"></i>Tipik süre</span>
          <span><i class="sw-whisker"></i>Hızlı–detaylı ziyaret aralığı</span>
          <span><i class="sw c-medium"></i>Orta güven</span>
          <span><i class="sw c-low"></i>Düşük güven</span>
          <span>${icon("ticket")}Önceden bilet alın</span>
        </div>
      </section>
    </div>`;
  renderRows(reveal);
}

function renderRows(reveal) {
  const list = visibleMuseums();
  const { museumId } = parseHash();
  const scaleMax = Math.max(
    4,
    ...state.city.museums.map((m) => {
      const d = m.duration ?? {};
      return Math.ceil(Math.max(d.thorough_h ?? 0, d.typical_max_h ?? 0, (d.typical_min_h ?? 0) + 1));
    }),
  );
  const pct = (h) => `${(h / scaleMax) * 100}%`;
  const step = scaleMax > 8 ? 2 : 1;

  $("#axis").innerHTML = `
    <span></span><span class="axis-label">Müze</span>
    <div class="axis-scale" style="--hours:${scaleMax}">
      ${Array.from({ length: Math.floor(scaleMax / step) + 1 }, (_, i) => i * step)
        .map((h) => `<span style="left:${pct(h)}">${h}</span>`).join("")}
    </div>
    <span class="axis-unit">saat</span>`;

  $("#rows").innerHTML = list.length ? list.map((m, i) => {
    const d = m.duration;
    const text = durationText(d);
    const conf = d?.confidence ?? "none";
    const ticket = m.planning?.advance_ticket?.value;
    let bars = "";
    if (d && d.fast_h != null && d.thorough_h != null && d.thorough_h > d.fast_h) {
      bars += `<span class="whisker" style="left:${pct(d.fast_h)};width:${pct(d.thorough_h - d.fast_h)}"></span>`;
    }
    if (text) {
      const open = d.typical_max_h == null;
      const hi = open ? Math.min(scaleMax, d.typical_min_h + 1) : d.typical_max_h;
      const lo = d.typical_min_h;
      bars += `<span class="bar c-${conf}${open ? " open" : ""}" style="left:${pct(lo)};width:${pct(hi - lo)};--i:${i}${hi === lo ? ";margin-left:-10px" : ""}"></span>`;
    }
    const sub = [
      m.name_local && m.name_local !== m.name ? esc(m.name_local) : m.category.map(categoryLabel).join(", "),
    ];
    return `
      <li>
        <button class="row stateful" data-museum="${esc(m.id)}" ${m.id === museumId ? 'aria-current="true"' : ""}>
          <span class="rank">${m.popularity_rank ?? "–"}</span>
          <span class="m-text">
            <span class="m-name">${esc(m.name)}</span>
            <span class="m-sub">${TICKET_FLAG.has(ticket) ? `${icon("ticket")}<span class="sr">Önceden bilet: ${TICKET[ticket]} · </span>` : ""}<span class="t">${sub}</span></span>
          </span>
          <span class="track" style="--hours:${scaleMax}" aria-hidden="true">${bars}</span>
          <span class="dur${text ? "" : " none"}">${text ? `${text} sa` : "veri yok"}</span>
        </button>
      </li>`;
  }).join("") : `<li class="empty">Bu filtreyle eşleşen müze yok.<br><button class="text-btn" data-clear-filters>Filtreleri temizle</button></li>`;

  $(".timeline").classList.toggle("reveal", reveal);
  renderPlanCard(list);
}

function renderPlanCard(list) {
  const known = list.filter((m) => m.duration?.typical_min_h != null);
  const lo = known.reduce((s, m) => s + m.duration.typical_min_h, 0);
  const hi = known.reduce((s, m) => s + (m.duration.typical_max_h ?? m.duration.typical_min_h), 0);
  const open = known.some((m) => m.duration.typical_max_h == null);
  const days = Math.ceil(hi / HOURS_PER_DAY);
  const filtered = state.categories.size > 0;

  const counts = CONFIDENCE.map(([level, label]) => [
    level ?? "none", label, list.filter((m) => (m.duration?.confidence ?? null) === level).length,
  ]).filter(([, , n]) => n);

  $("#plan-card").innerHTML = `
    <div class="plan-label">${filtered ? `Seçili ${list.length} müzenin` : `${list.length} müzenin`} tamamı için</div>
    <div class="plan-value">${known.length ? `${hours(lo)}${hi !== lo ? `–${hours(hi)}` : ""}${open ? "+" : ""}<small>saat</small>` : "—"}</div>
    <div class="plan-hint">${known.length ? `Günde ${HOURS_PER_DAY} saat müzeyle yaklaşık ${days} gün` : "Süre verisi yok"}</div>
    <div class="conf-meter" role="img" aria-label="${counts.map(([, l, n]) => `${n} ${l.toLocaleLowerCase("tr")}`).join(", ")}">
      ${counts.map(([lvl, , n]) => `<span class="c-${lvl}" style="flex:${n}"></span>`).join("")}
    </div>
    <div class="conf-legend">${counts.map(([lvl, l, n]) => `<span><i class="c-${lvl}"></i>${n} ${l.toLocaleLowerCase("tr")}</span>`).join("")}</div>`;
}

// ---------- detail sheet ----------

function fieldRow(label, fv, format = (v) => esc(v)) {
  if (!fv || fv.value == null) return `<dt>${label}</dt><dd class="muted">Bilinmiyor</dd>`;
  const age = fv.checked ? daysSince(fv.checked) : null;
  const stale = age != null && age > STALE_DAYS;
  const src = [fv.source && (SOURCE[fv.source] ?? fv.source), fv.checked && formatDate(fv.checked)].filter(Boolean).join(" · ");
  return `<dt>${label}</dt><dd>${format(fv.value)}
    <span class="src${stale ? " stale" : ""}">${esc(src)}${stale ? " · güncellenmeli" : ""}</span></dd>`;
}

function renderSheet(m) {
  const app = $(".app");
  const sheet = $("#sheet");
  document.querySelectorAll(".row[aria-current]").forEach((r) => r.removeAttribute("aria-current"));
  if (!m) {
    sheet.hidden = true;
    $(".sheet-scrim").hidden = true;
    app.classList.remove("has-sheet");
    return;
  }
  const row = document.querySelector(`.row[data-museum="${CSS.escape(m.id)}"]`);
  row?.setAttribute("aria-current", "true");

  const d = m.duration;
  const text = durationText(d);
  const conf = CONFIDENCE.find(([lvl]) => lvl === (d?.confidence ?? null))[1];
  const p = m.planning ?? {};
  const v = m.volatile ?? {};
  const mapUrl = m.coords
    ? `https://www.openstreetmap.org/?mlat=${m.coords[0]}&mlon=${m.coords[1]}#map=17/${m.coords[0]}/${m.coords[1]}`
    : null;

  $("#sheet-body").innerHTML = `
    <h2>${esc(m.name)}</h2>
    ${m.name_local && m.name_local !== m.name ? `<p class="local">${esc(m.name_local)}</p>` : ""}
    <div class="tags">${m.category.map((c) => `<span class="tag">${esc(categoryLabel(c))}</span>`).join("")}</div>

    <div class="dur-hero">
      <div class="big">${text ?? "—"}<small>${text ? "saat" : "süre verisi yok"}</small></div>
      <dl>
        <div><dt>Hızlı</dt><dd>${d?.fast_h != null ? `${hours(d.fast_h)} sa` : "—"}</dd></div>
        <div><dt>Detaylı</dt><dd>${d?.thorough_h != null ? `${hours(d.thorough_h)} sa` : "—"}</dd></div>
        <div><dt>Güven</dt><dd>${conf}</dd></div>
      </dl>
    </div>

    ${d?.notes?.length || m.user_notes?.length ? `
      <section class="sec"><h3>Notlar</h3>
        <ul class="notes">${[...(m.user_notes ?? []), ...(d?.notes ?? [])].map((n) => `<li>${esc(n)}</li>`).join("")}</ul>
      </section>` : ""}

    <section class="sec"><h3>Planlama</h3>
      <dl class="facts">
        ${fieldRow("Önceden bilet", p.advance_ticket, (val) => esc(TICKET[val] ?? val))}
        ${fieldRow("En kalabalık", p.busiest)}
        ${fieldRow("Kuyruk", p.queue_min, (val) => `${esc(val)} dk`)}
        ${fieldRow("Ücret", v.price)}
        ${fieldRow("Saatler", v.hours)}
      </dl>
    </section>

    ${d?.signals?.length ? `
      <section class="sec"><h3>Kaynaklar <span class="muted">(${d.signals.length})</span></h3>
        <ul class="signals">${d.signals.map((s) => `
          <li class="signal">
            <q>${esc(s.value)}</q>
            <div class="signal-meta">
              <span class="src-name">${esc(SOURCE[s.source] ?? s.source)}</span>
              <span>${esc(formatDate(s.checked))}</span>
              ${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">Kaynağa git ${icon("ext", "icon sm")}</a>` : ""}
            </div>
          </li>`).join("")}
        </ul>
      </section>` : ""}

    <section class="sec"><h3>Konum</h3>
      <p class="address">${m.address ? esc(m.address) : '<span class="muted">Adres yok</span>'}</p>
      <div class="links">
        ${mapUrl ? `<a class="tonal-btn stateful" href="${mapUrl}" target="_blank" rel="noopener">${icon("place", "icon sm")}Haritada aç</a>` : ""}
        ${m.website ? `<a class="tonal-btn stateful" href="${esc(m.website)}" target="_blank" rel="noopener">${icon("ext", "icon sm")}Web sitesi</a>` : ""}
      </div>
    </section>`;

  const wasHidden = sheet.hidden;
  sheet.hidden = false;
  $(".sheet-scrim").hidden = false;
  app.classList.add("has-sheet");
  sheet.scrollTop = 0;
  if (wasHidden) sheet.querySelector("[data-close-sheet]").focus({ preventScroll: true });
}

function closeSheet() {
  const { slug, museumId } = parseHash();
  if (museumId) {
    go(slug);
    document.querySelector(`.row[data-museum="${CSS.escape(museumId)}"]`)?.focus();
  }
}

// ---------- empty / error ----------

function renderNoCities() {
  $("#view").innerHTML = `
    <div class="view-inner empty">
      <h2>Henüz şehir yok</h2>
      <p>İlk şehri eklemek için Claude Code'da <code>/muze roma</code> gibi bir komut çalıştır, sonra bu sayfayı yenile.</p>
    </div>`;
}

function renderError(slug, message) {
  $("#view").innerHTML = `
    <div class="view-inner empty">
      <h2>“${esc(slug)}” açılamadı</h2>
      <p>${esc(message)}</p>
      ${state.cities.length ? `<a class="text-btn" href="#/${esc(state.cities[0].slug)}">${esc(state.cities[0].name)} şehrine dön</a>` : ""}
    </div>`;
}

// ---------- events ----------

document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-museum],[data-cat],[data-sort],[data-clear-filters],[data-close-sheet],[data-open-drawer],[data-close-drawer]");
  if (!t) return;
  if (t.dataset.museum) {
    const { slug, museumId } = parseHash();
    if (museumId === t.dataset.museum) go(slug); else go(slug, t.dataset.museum);
  } else if (t.dataset.cat) {
    const c = t.dataset.cat;
    state.categories.has(c) ? state.categories.delete(c) : state.categories.add(c);
    t.setAttribute("aria-pressed", state.categories.has(c));
    renderRows(false);
  } else if (t.dataset.sort) {
    state.sort = t.dataset.sort;
    document.querySelectorAll("[data-sort]").forEach((b) => b.setAttribute("aria-pressed", b === t));
    renderRows(false);
  } else if ("clearFilters" in t.dataset) {
    state.categories.clear();
    document.querySelectorAll("[data-cat]").forEach((b) => b.setAttribute("aria-pressed", "false"));
    renderRows(false);
  } else if ("closeSheet" in t.dataset) {
    closeSheet();
  } else if ("openDrawer" in t.dataset) {
    openDrawer();
  } else if ("closeDrawer" in t.dataset) {
    closeDrawer();
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if ($("#drawer").classList.contains("open")) closeDrawer();
  else closeSheet();
});

$("#city-search").addEventListener("input", (e) => {
  state.query = e.target.value;
  renderNav(parseHash().slug);
});

window.addEventListener("hashchange", route);

(async function init() {
  try {
    state.cities = await getJSON("/api/cities");
  } catch (e) {
    $("#view").innerHTML = `<div class="view-inner empty"><h2>Veri yüklenemedi</h2><p>${esc(e.message)}</p></div>`;
    return;
  }
  route();
})();
