"use strict";

const RESEARCH_STEPS = [["research", "Research"], ["intelligence", "Analysis"], ["opportunity", "Opportunities"], ["strategy", "Strategy"]];
const PRODUCE_STEPS = [["brief", "Brief"], ["script", "Script"], ["production", "Plan"], ["thumbnail", "Thumbnails"], ["qa", "QA"]];
const VIEWS = { new: "New video", opportunities: "Opportunities", production: "Production", learning: "Learning" };
const POLL_MS = 2000;

let state = null;
let filter = "all";
let lastStatus = null;
let lastError = "";
let submitting = false;
const signatures = {};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[c]));
}

function icon(name, cls = "icon") {
  return `<svg class="${cls}" aria-hidden="true"><use href="#i-${name}"/></svg>`;
}

function fmt(value, digits = 0) {
  if (value === null || value === undefined || value === "") return "—";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { el.hidden = true; }, 4000);
}

/* Render a region only when its data changed, so open <details>, scroll
   position and keyboard focus survive the polling refresh. */
function renderIf(key, data, render) {
  const signature = JSON.stringify(data);
  if (signatures[key] === signature) return;
  signatures[key] = signature;
  render(data);
}

/* Theme */
function currentTheme() {
  return document.documentElement.dataset.theme
    || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
}

function updateThemeButton() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  const button = $("#theme-toggle");
  button.innerHTML = `${icon(next === "light" ? "sun" : "moon")}<span>${next === "light" ? "Light" : "Dark"} theme</span>`;
  button.setAttribute("aria-label", `Switch to ${next} theme`);
}

function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("overseer-theme", next); } catch (e) { /* private mode */ }
  updateThemeButton();
}

/* Routing */
function currentView() {
  const match = location.hash.match(/^#\/(\w+)/);
  return match && VIEWS[match[1]] ? match[1] : "new";
}

function showView(moveFocus) {
  const view = currentView();
  $$("[data-view]").forEach(section => { section.hidden = section.dataset.view !== view; });
  $$("[data-nav]").forEach(link => {
    if (link.dataset.nav === view) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  document.title = `${VIEWS[view]} · Overseer`;
  if (moveFocus) {
    window.scrollTo(0, 0);
    const heading = $(`[data-view="${view}"] h1`);
    if (heading) heading.focus();
  }
}

/* Run bar */
function renderRunbar(s) {
  const busy = s.status === "running";
  const job = s.job || "research";
  const badge = $("#run-status");
  const badges = {
    running: ["Running", "badge-accent"],
    failed: ["Needs attention", "badge-danger"],
    completed: ["Complete", "badge-success"],
  };
  const [label, cls] = badges[s.status] || ["Ready", ""];
  badge.className = `badge ${cls}`;
  badge.textContent = label;

  const topic = s.intent?.topic;
  let title = "Ready for a new video idea";
  if (busy) {
    title = job === "produce"
      ? "Producing brief, script, plan and thumbnails"
      : topic ? `Researching “${topic}”` : "Studying your reference channels";
  } else if (s.status === "failed") {
    title = (s.errors || []).slice(-1)[0] || "The run stopped";
  } else if (s.status === "completed") {
    title = job === "produce"
      ? "Production finished — review the QA checklist"
      : `Research complete · ${s.opportunity_count || 0} opportunities`;
  }
  $("#run-title").textContent = title;

  const meta = [];
  if (s.run_id) meta.push(`run ${s.run_id}`);
  if (s.completed_at && !busy) meta.push(new Date(s.completed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
  $("#run-meta").textContent = meta.join(" · ");

  const steps = job === "produce" ? PRODUCE_STEPS : RESEARCH_STEPS;
  const done = new Set(s.completed_steps || []);
  const failedAt = s.status === "failed" ? steps.find(([key]) => !done.has(key))?.[0] : null;
  $("#stepper").innerHTML = steps.map(([key, text], index) => {
    const classes = [];
    if (done.has(key)) classes.push("done");
    if (busy && s.current_step === key) classes.push("active");
    if (failedAt === key) classes.push("failed");
    const mark = done.has(key) ? icon("check") : failedAt === key ? icon("x") : index + 1;
    const current = classes.includes("active") ? ' aria-current="step"' : "";
    return `<li class="${classes.join(" ")}"${current}><span class="step-mark" aria-hidden="true">${mark}</span><span class="step-label">${esc(text)}</span><span class="sr-only">${done.has(key) ? "done" : classes.includes("active") ? "in progress" : ""}</span></li>`;
  }).join("");

  const runButton = $("#run-button");
  runButton.disabled = busy || submitting;
  runButton.querySelector("span").textContent = busy ? "A run is in progress…" : submitting ? "Starting…" : "Research this idea";
}

/* New video: research panel */
function intentCard(intent) {
  const facts = [
    ["Format", intent.video_format],
    ["Length", intent.target_minutes ? `about ${fmt(intent.target_minutes)} min` : ""],
    ["Tone", intent.tone],
    ["For", intent.audience],
    ["Include", (intent.must_include || []).join("; ")],
    ["Avoid", (intent.avoid || []).join("; ")],
  ].filter(([, value]) => value);
  return `
    <article class="card">
      <div class="card-head"><h2>${icon("spark")}Your brief</h2>${intent.error ? '<span class="badge badge-warning">Read without AI</span>' : ""}</div>
      <h3>${esc(intent.topic)}</h3>
      ${intent.summary && intent.summary !== intent.prompt ? `<p class="muted">${esc(intent.summary)}</p>` : ""}
      ${facts.length ? `<dl class="facts">${facts.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>` : ""}
      ${(intent.search_queries || []).length ? `<p class="label">Searched YouTube for</p><div class="tags">${intent.search_queries.map(q => `<span class="tag">${esc(q)}</span>`).join("")}</div>` : ""}
    </article>`;
}

function territoryCard(territory, intent) {
  const confidence = territory.confidence || "unrated";
  const tone = { high: "badge-success", medium: "badge-warning", low: "", unrated: "" }[confidence] || "";
  const subs = (territory.sub_territories || []).map(t => `<span class="tag">${esc(t)}</span>`).join("");
  const evidence = (territory.evidence || []).map(e => `<li>${esc(e)}</li>`).join("");
  return `
    <article class="card">
      <div class="card-head"><h2>${icon("search")}${intent ? "Topic landscape" : "Research territory"}</h2><span class="badge ${tone}">${esc(confidence)} confidence</span></div>
      <h3>${esc(territory.label)}</h3>
      ${subs ? `<div class="tags">${subs}</div>` : ""}
      ${territory.audience ? `<p class="small muted"><strong>Audience:</strong> ${esc(territory.audience)}</p>` : ""}
      ${evidence ? `<details class="evidence"><summary>Why Overseer thinks this</summary><ul>${evidence}</ul></details>` : ""}
    </article>`;
}

function renderResearchPanel(s) {
  const panel = $("#research-panel");
  const profiles = s.channel_profiles || [];
  if (!s.intent && !s.research_territory && !profiles.length) {
    panel.innerHTML = `
      <div class="empty">
        ${icon("search")}
        <h2>Your research appears here</h2>
        <ol class="steps">
          <li>Overseer reads your idea and searches YouTube for related videos.</li>
          <li>It maps the topic: what's covered, what performs, what's missing.</li>
          <li>It proposes angles, ranked by evidence. Pick one to produce a brief, script, plan and thumbnails.</li>
        </ol>
      </div>`;
    return;
  }

  const parts = [];
  if (s.intent) parts.push(intentCard(s.intent));
  if (s.research_territory) parts.push(territoryCard(s.research_territory, s.intent));
  if (s.research_count || profiles.length) {
    parts.push(`
      <article class="card">
        <div class="card-head"><h2>${icon("users")}Evidence</h2><span class="card-sub">${fmt(s.research_count)} videos</span></div>
        ${s.research_source ? `<p class="small muted">${esc(s.research_source)}</p>` : ""}
        ${profiles.length ? `<div class="profiles">${profiles.map(p => `<div class="profile"><strong>${esc(p.title || "Untitled channel")}</strong><span>${fmt(p.subscriber_count)} subs</span></div>`).join("")}</div>` : ""}
      </article>`);
  }
  if ((s.warnings || []).length) {
    parts.push(`<div class="callout callout-warning">${icon("alert")}<div><strong>${s.warnings.length} warning${s.warnings.length === 1 ? "" : "s"}</strong><ul>${s.warnings.map(w => `<li>${esc(w)}</li>`).join("")}</ul></div></div>`);
  }
  if (s.opportunity_count && s.status !== "running") {
    parts.push(`<a class="btn btn-primary" href="#/opportunities">See ${s.opportunity_count} ${s.intent ? "angles" : "opportunities"} ${icon("arrow")}</a>`);
  }
  panel.innerHTML = parts.join("");
}

/* Opportunities */
function meter(label, value) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0));
  return `<div class="meter"><div class="meter-label"><span>${label}</span><b>${pct}</b></div><div class="bar" aria-hidden="true"><i style="width:${pct}%"></i></div></div>`;
}

function opportunityCard(item, index, busy) {
  const validated = item.tier === "validated";
  const tier = validated
    ? `<span class="badge badge-success">${icon("shield")}Validated · ${item.evidence_count} video${item.evidence_count === 1 ? "" : "s"}</span>`
    : `<span class="badge badge-warning">${icon("flask")}Hypothesis · needs validation</span>`;
  const history = item.history && item.history.retention
    ? `<span class="badge badge-info">${icon("clock")}Your history · ${fmt(item.history.retention.mean)}% viewed</span>`
    : "";
  const evidence = (item.evidence || []).map(e => `<li>${esc(e)}</li>`).join("");
  return `
    <article class="opp ${index === 0 ? "top" : ""}" aria-labelledby="opp-${index}">
      <div class="score" aria-label="Score ${item.score} out of 100"><strong aria-hidden="true">${item.score}</strong><span aria-hidden="true">/ 100</span></div>
      <div class="opp-body">
        <div class="tags">${tier}${history}</div>
        <h2 id="opp-${index}">${esc(item.topic)}</h2>
        ${item.angle ? `<p class="angle">${esc(item.angle)}</p>` : ""}
        <div class="meters">${meter("Demand", item.demand)}${meter("Audience fit", item.audience_fit)}${meter("Gap", item.competition_gap)}${meter("Intent", item.business_intent)}</div>
        ${evidence ? `<details class="evidence"><summary>Evidence and scoring</summary><ul>${evidence}</ul><p class="rationale">${esc(item.rationale)}</p></details>` : ""}
      </div>
      <div class="opp-actions">
        <button class="btn btn-secondary" type="button" data-produce="${index}" ${busy ? "disabled" : ""}>${icon("play")}<span>Produce</span></button>
      </div>
    </article>`;
}

function renderOpportunities(data) {
  const { items, intent, territory, busy } = data;
  const counts = {
    all: items.length,
    validated: items.filter(i => i.tier === "validated").length,
    hypothesis: items.filter(i => i.tier !== "validated").length,
  };
  $$("[data-filter-count]").forEach(el => { el.textContent = counts[el.dataset.filterCount]; });
  $$("[data-filter]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.filter === data.filter)));

  $("#opps-title").textContent = intent ? "Angles for your video" : "Opportunities";
  $("#opps-lede").textContent = intent
    ? `For “${intent.topic}”. Ranked by the evidence Overseer collected; scores are relative, not predictions.`
    : territory
      ? `In “${territory.label}”. Ranked by the evidence Overseer collected; scores are relative, not predictions.`
      : "Ranked by the evidence collected in the latest run. Scores are relative, not predictions.";

  const list = $("#opp-list");
  if (!items.length) {
    list.innerHTML = `<div class="empty">${icon("list")}<h2>No opportunities yet</h2><p>Describe a video idea or add reference channels, then run the research.</p><a class="btn btn-primary" href="#/new">${icon("spark")}<span>Start a new video</span></a></div>`;
    return;
  }
  const visible = items
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => data.filter === "all" || (data.filter === "validated" ? item.tier === "validated" : item.tier !== "validated"));
  list.innerHTML = visible.length
    ? visible.map(({ item, index }) => opportunityCard(item, index, busy)).join("")
    : `<div class="empty"><p>No ${data.filter === "validated" ? "validated opportunities" : "hypotheses"} in this run.</p></div>`;
}

/* Production */
function copyRow(text) {
  return `<div class="cmd"><code>${esc(text)}</code><button class="icon-btn" type="button" data-copy="${esc(text)}" aria-label="Copy ${esc(text)}">${icon("copy")}</button></div>`;
}

function renderProduction(data) {
  const { production: p, producing } = data;
  const root = $("#production-root");
  if (!p) {
    root.innerHTML = `
      <div class="view-head"><p class="eyebrow">Production</p><h1 id="prod-title" tabindex="-1">Production</h1></div>
      <div class="empty">
        ${icon("film")}
        <h2>${producing ? "Producing your video package…" : "Nothing in production yet"}</h2>
        <p>${producing ? "Writing the brief, script, production plan and thumbnail concepts. This usually takes a minute or two." : "Pick an opportunity and press Produce to get a brief, script, production plan, thumbnail concepts and a QA checklist."}</p>
        ${producing ? "" : `<a class="btn btn-primary" href="#/opportunities">${icon("list")}<span>Choose an opportunity</span></a>`}
      </div>`;
    return;
  }

  const openItems = (p.failed_checks || []).length + (p.open_claims || 0);
  const status = openItems === 0
    ? `<span class="badge badge-success">${icon("check")}Ready to publish</span>`
    : `<span class="badge badge-warning">${icon("alert")}${openItems} item${openItems === 1 ? "" : "s"} to review</span>`;
  const outline = (p.outline || []).map(o => `<li>${esc(o)}</li>`).join("");
  const alternatives = (p.alternative_titles || []).map(t => `<li>${esc(t)}</li>`).join("");
  const sections = (p.sections || []).map(s => `<li><div><strong>${esc(s.heading)}</strong>${s.preview ? `<p>${esc(s.preview)}${s.preview.length >= 220 ? "…" : ""}</p>` : ""}</div></li>`).join("");
  const thumbs = (p.thumbnails || []).map(t => `<div class="thumb"><strong>${esc(t.text || "—")}</strong><span>${esc(t.name)}</span></div>`).join("");
  const checks = (p.checks || []).map(c => `<li class="${c.passed ? "pass" : "fail"}">${icon(c.passed ? "check" : "x")}<div>${esc(c.name)}${c.detail ? `<small>${esc(c.detail)}</small>` : ""}</div></li>`).join("");
  const claims = (p.claims || []).map(c => {
    const ok = c.verified && String(c.source || "").trim();
    return `<li class="${ok ? "pass" : "open"}">${icon(ok ? "check" : "alert")}<div>${esc(c.claim)}<small>${ok ? `Source: ${esc(c.source)}` : "Needs a source"}</small></div></li>`;
  }).join("");

  root.innerHTML = `
    <div class="prod-head">
      <div>
        <p class="eyebrow">Production · run ${esc(p.run_id)}</p>
        <h1 id="prod-title" tabindex="-1">${esc(p.working_title || p.topic)}</h1>
        <p class="muted">Opportunity: ${esc(p.topic)}</p>
      </div>
      ${status}
    </div>
    ${producing ? `<div class="callout callout-info">${icon("info")}<p>Producing a new package. This page updates when it finishes.</p></div>` : ""}
    ${(p.fallbacks || []).length ? `<div class="callout callout-warning">${icon("alert")}<p>The ${p.fallbacks.join(", ")} used a non-AI fallback, so they are placeholders. Check that <code>ANTHROPIC_API_KEY</code> is set and see the run warnings.</p></div>` : ""}
    <div class="grid-2">
      <div class="stack">
        <article class="card">
          <div class="card-head"><h2>${icon("spark")}Brief</h2></div>
          ${p.viewer_promise ? `<p class="label">Viewer promise</p><p>${esc(p.viewer_promise)}</p>` : ""}
          ${p.opening_hook ? `<p class="label">Opening hook</p><blockquote class="hook">${esc(p.opening_hook)}</blockquote>` : ""}
          ${outline ? `<p class="label">Outline</p><ol>${outline}</ol>` : ""}
          ${alternatives ? `<p class="label">Alternative titles</p><ul>${alternatives}</ul>` : ""}
          ${p.cta ? `<p class="label">Call to action</p><p>${esc(p.cta)}</p>` : ""}
          ${!p.viewer_promise && !p.opening_hook && !outline ? '<p class="muted">The brief is empty.</p>' : ""}
        </article>
        <article class="card">
          <div class="card-head"><h2>${icon("film")}Script</h2><span class="card-sub">${p.estimated_minutes ? `~${fmt(p.estimated_minutes)} min · ` : ""}${(p.sections || []).length} sections</span></div>
          ${sections ? `<ol class="sections">${sections}</ol>` : '<p class="muted">No script sections were written.</p>'}
        </article>
      </div>
      <div class="stack">
        <article class="card">
          <div class="card-head"><h2>${icon("shield")}QA checklist</h2></div>
          ${checks ? `<ul class="checklist">${checks}</ul>` : '<p class="muted">No checks ran.</p>'}
          ${claims ? `<p class="label">Claims to verify</p><ul class="checklist">${claims}</ul>` : '<p class="small muted">No factual claims were flagged.</p>'}
        </article>
        ${thumbs ? `<article class="card"><div class="card-head"><h2>${icon("spark")}Thumbnail concepts</h2></div><div class="thumbs">${thumbs}</div></article>` : ""}
        <article class="card">
          <div class="card-head"><h2>${icon("arrow")}Next steps</h2></div>
          <ol class="steps">
            <li>Mark each claim <code>verified</code> with a <code>source</code> in:${copyRow(`${p.run_path}/qa_report.json`)}</li>
            <li>Record the voiceover, edit and publish the video on YouTube.</li>
            <li>Link it so Overseer can learn from its performance:${copyRow("python main.py --record-published VIDEO_ID")}</li>
          </ol>
        </article>
      </div>
    </div>`;
}

/* Learning */
function signalRows(rows, unit) {
  if (!rows || !rows.length) return '<p class="small muted">Not enough data yet.</p>';
  const max = Math.max(...rows.map(r => r.mean || 0), 1);
  return `<div class="rows">${rows.map(r => `
    <div class="row"><span>${esc(r.name)} <small>· ${r.count} video${r.count === 1 ? "" : "s"}</small></span><b>${fmt(r.mean, 1)}${unit}</b>
    <div class="bar" aria-hidden="true"><i style="width:${Math.round((r.mean || 0) / max * 100)}%"></i></div></div>`).join("")}</div>`;
}

function renderLearning(data) {
  const { analytics: a, memory: m } = data;
  const root = $("#learning-root");
  if (!a && !(m && m.videos_analyzed)) {
    $("#learn-lede").textContent = "Performance of your own published videos, fed back into future opportunities.";
    root.innerHTML = `
      <div class="empty">
        ${icon("chart")}
        <h2>No channel data yet</h2>
        <ol class="steps">
          <li>Publish a video you produced here and link it:${copyRow("python main.py --record-published VIDEO_ID")}</li>
          <li>After it has some views, pull your analytics (needs <code>YOUTUBE_ACCESS_TOKEN</code>):${copyRow("python main.py --learn --analytics-start 2026-09-01 --analytics-end 2026-09-30")}</li>
          <li>Optional: add thumbnail CTR from a YouTube Studio export with <code>--ctr-csv "Table data.csv"</code>.</li>
        </ol>
      </div>`;
    return;
  }

  $("#learn-lede").textContent = a
    ? `${a.start_date} to ${a.end_date} · ${fmt(a.videos)} videos analysed.`
    : `${fmt(m.videos_analyzed)} videos analysed.`;
  const ctrMissing = !a || a.average_ctr === null || a.average_ctr === undefined;
  const kpis = a ? `
    <div class="kpis">
      <div class="kpi"><span>Views</span><strong>${fmt(a.total_views)}</strong><em>YouTube Analytics</em></div>
      <div class="kpi"><span>Thumbnail CTR</span><strong>${ctrMissing ? "—" : `${fmt(a.average_ctr, 1)}%`}</strong><em>${ctrMissing ? "Import with --ctr-csv" : "From CSV import"}</em></div>
      <div class="kpi"><span>Avg. % viewed</span><strong>${a.average_percentage_viewed == null ? "—" : `${fmt(a.average_percentage_viewed, 1)}%`}</strong><em>YouTube Analytics</em></div>
      <div class="kpi"><span>Subscribers gained</span><strong>${fmt(a.subscribers_gained)}</strong><em>YouTube Analytics</em></div>
    </div>` : "";
  const top = (a && a.top_videos) || [];
  const table = top.length ? `
    <article class="card">
      <div class="card-head"><h2>${icon("chart")}Top videos</h2></div>
      <div class="table-wrap"><table>
        <thead><tr><th scope="col">Video</th><th scope="col" class="num">Views</th><th scope="col" class="num">% viewed</th><th scope="col" class="num">CTR</th></tr></thead>
        <tbody>${top.map(v => `<tr><td>${esc(v.title || v.video_id)}</td><td class="num">${fmt(v.views)}</td><td class="num">${v.retention == null ? "—" : `${fmt(v.retention, 1)}%`}</td><td class="num">${v.ctr == null ? "—" : `${fmt(v.ctr, 1)}%`}</td></tr>`).join("")}</tbody>
      </table></div>
    </article>` : "";
  const titleUnit = m && m.title_metric === "ctr" ? "%" : "";
  const learned = m ? `
    <article class="card">
      <div class="card-head"><h2>${icon("clock")}What Overseer learned</h2>${m.updated_at ? `<span class="card-sub">Updated ${new Date(m.updated_at).toLocaleDateString()}</span>` : ""}</div>
      <p class="label">Topics · % viewed</p>${signalRows(m.top_topics, "%")}
      <p class="label">Title patterns · ${m.title_metric === "ctr" ? "CTR" : "views"}</p>${signalRows(m.top_titles, titleUnit)}
      <p class="label">Video length · % viewed</p>${signalRows(m.top_formats, "%")}
      ${(m.notes || []).length ? `<div class="callout callout-info">${icon("info")}<ul>${m.notes.map(n => `<li>${esc(n)}</li>`).join("")}</ul></div>` : ""}
    </article>` : "";
  const cards = [table, learned].filter(Boolean);
  root.innerHTML = `<div class="stack">${kpis}${cards.length === 2 ? `<div class="grid-2">${cards.join("")}</div>` : cards.join("")}</div>`;
}

/* Composer */
function composerValues() {
  const form = $("#brief-form");
  return {
    prompt: $("#prompt").value.trim(),
    channels: $("#channels").value.split(/\r?\n/).map(v => v.trim()).filter(Boolean),
    // namedItem, because form.elements.length is the number of controls.
    format: form.elements.namedItem("format").value,
    length: form.elements.namedItem("length").value,
  };
}

function updateComposer() {
  const { prompt, channels } = composerValues();
  $("#prompt-count").textContent = `${$("#prompt").value.length} / 2000`;
  const hint = !prompt && !channels.length
    ? "Describe an idea, add reference channels, or both."
    : prompt && channels.length
      ? "Your idea sets the topic; the channels add evidence about style and audience."
      : prompt
        ? "Overseer will search YouTube for your topic, then propose evidence-backed angles."
        : "Overseer will infer what these channels cover, then look for gaps across YouTube.";
  $("#mode-hint span").textContent = hint;
}

function showFormError(message) {
  const el = $("#form-error");
  el.textContent = message;
  el.hidden = !message;
  $("#prompt").setAttribute("aria-invalid", message ? "true" : "false");
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data = {};
  try { data = await response.json(); } catch (e) { /* empty body */ }
  if (!response.ok) throw new Error(data.message || `Request failed (${response.status})`);
  return data;
}

async function submitBrief(event) {
  event.preventDefault();
  const values = composerValues();
  if (!values.prompt && !values.channels.length) {
    showFormError("Describe the video you want to make, or add at least one reference channel.");
    $("#prompt").focus();
    return;
  }
  if (values.channels.length > 10) {
    showFormError("Use at most 10 reference channels.");
    $("#channels-disclosure").open = true;
    $("#channels").focus();
    return;
  }
  showFormError("");
  submitting = true;
  if (state) renderRunbar(state);
  try {
    await postJson("/api/run", values);
    toast(values.prompt ? "Researching your idea…" : "Studying your reference channels…");
    await refresh();
  } catch (error) {
    showFormError(error.message);
  } finally {
    submitting = false;
    if (state) renderRunbar(state);
  }
}

async function produce(index, button) {
  button.disabled = true;
  try {
    await postJson("/api/produce", { opportunity: index });
    toast("Producing brief, script, plan and thumbnails…");
    location.hash = "#/production";
    await refresh();
  } catch (error) {
    button.disabled = false;
    toast(error.message);
  }
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied");
  } catch (e) {
    toast("Copy failed; select the text instead");
  }
}

/* State */
function render(s) {
  const busy = s.status === "running";
  renderRunbar(s);
  $("#channel-name").textContent = s.channel ? `Channel: ${s.channel}` : "";
  $$("[data-count='opportunities']").forEach(el => {
    el.textContent = s.opportunity_count || "";
    el.hidden = !s.opportunity_count;
  });
  renderIf("panel", {
    intent: s.intent, territory: s.research_territory, profiles: s.channel_profiles,
    count: s.research_count, source: s.research_source, warnings: s.warnings,
    opps: s.opportunity_count, status: s.status,
  }, () => renderResearchPanel(s));
  renderIf("opps", {
    items: s.opportunities || [], intent: s.intent, territory: s.research_territory, busy, filter,
  }, renderOpportunities);
  renderIf("production", {
    production: s.production, producing: busy && s.job === "produce",
  }, renderProduction);
  renderIf("learning", { analytics: s.analytics, memory: s.memory }, renderLearning);

  if (lastStatus === "running" && s.status === "completed") {
    toast(s.job === "produce" ? "Production finished — review the QA checklist" : `Research complete: ${s.opportunity_count || 0} opportunities`);
  }
  const error = s.status === "failed" ? (s.errors || []).slice(-1)[0] || "" : "";
  if (error && error !== lastError) toast(error);
  lastError = error;
  lastStatus = s.status;
}

async function refresh() {
  const runtime = $("#runtime-status");
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) throw new Error(`status ${response.status}`);
    state = await response.json();
    render(state);
    runtime.className = "runtime online";
    runtime.lastElementChild.textContent = "Local runtime online";
  } catch (error) {
    runtime.className = "runtime offline";
    runtime.lastElementChild.textContent = "Local runtime offline";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  updateThemeButton();
  $("#theme-toggle").addEventListener("click", toggleTheme);
  window.addEventListener("hashchange", () => showView(true));
  showView(false);

  const form = $("#brief-form");
  form.addEventListener("submit", submitBrief);
  form.addEventListener("input", () => { updateComposer(); if (!$("#form-error").hidden) showFormError(""); });
  $("#prompt").addEventListener("keydown", event => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) form.requestSubmit();
  });
  $$("[data-example]").forEach(button => button.addEventListener("click", () => {
    $("#prompt").value = button.dataset.example;
    updateComposer();
    showFormError("");
    $("#prompt").focus();
  }));
  updateComposer();

  $("#tier-filter").addEventListener("click", event => {
    const button = event.target.closest("[data-filter]");
    if (!button) return;
    filter = button.dataset.filter;
    if (state) render(state);
  });
  document.addEventListener("click", event => {
    const produceButton = event.target.closest("[data-produce]");
    if (produceButton) produce(Number(produceButton.dataset.produce), produceButton);
    const copyButton = event.target.closest("[data-copy]");
    if (copyButton) copyText(copyButton.dataset.copy);
  });

  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, POLL_MS);
});
