/* Ask FEMA widget.
   Usage: <div id="ask-fema" class="af" data-api="https://…lambda-url…/"></div>
          <link rel="stylesheet" href="…/static/ask-fema.css"><script src="…/static/ask-fema.js" defer></script>
   data-api may be omitted when the page is served by the API itself. */
(function () {
  "use strict";
  var root = document.getElementById("ask-fema");
  if (!root) return;
  var API = (root.getAttribute("data-api") || "").replace(/\/$/, "");
  var CHART_SRC = "https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.js";
  var C = { blue: "#0071e3", green: "#14a37f", pink: "#e0598b", ink: "#1d2b3a", ink2: "#465667", line: "#e2e7ec" };
  var EXAMPLES = [
    "How many hurricane disasters has Florida had since 2010?",
    "Disasters declared in Virginia per year since 2010",
    "Which states had the most severe storm disasters in the last 5 years?",
    "How much Public Assistance was obligated for Hurricane Ian?",
    "What incident types are most common in California?",
    "How many disasters have included Fairfax County, Virginia?"
  ];
  var charts = {};

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) {
    return typeof n === "number" ? n.toLocaleString("en-US", { maximumFractionDigits: 2 }) : (n == null ? "—" : n);
  }
  function $(sel) { return root.querySelector(sel); }

  root.innerHTML =
    '<section class="af-card" aria-labelledby="af-ask-h">' +
    '  <h3 id="af-ask-h">Ask a question about U.S. disasters</h3>' +
    '  <form class="af-form" novalidate>' +
    '    <label class="af-sr" for="af-q">Your question</label>' +
    '    <input class="af-input" id="af-q" maxlength="500" autocomplete="off" placeholder="e.g. How many tornado disasters has Oklahoma had?">' +
    '    <button class="af-btn" type="submit">Ask</button>' +
    '  </form>' +
    '  <ul class="af-chips" aria-label="Example questions">' +
    EXAMPLES.map(function (q) { return '<li><button class="af-chip" type="button">' + esc(q) + "</button></li>"; }).join("") +
    "  </ul>" +
    '  <div class="af-answer" hidden aria-live="polite">' +
    '    <p class="af-answer-text"></p>' +
    '    <div class="af-tags"></div>' +
    '    <div class="af-chart af-chart-answer" hidden><canvas id="af-c-answer" role="img" aria-label="Chart of the answer data"></canvas></div>' +
    '    <details class="af-data" hidden><summary>Show the data behind this answer</summary><div class="af-table-wrap"></div></details>' +
    '    <details class="af-sql" hidden><summary>Show the SQL query</summary><pre></pre></details>' +
    "  </div>" +
    "</section>" +
    '<div class="af-stats" role="group" aria-label="Key figures">' +
    '  <div class="af-card af-stat"><div class="af-num-big" id="af-k-total">—</div><div class="af-label" id="af-k-total-l">disasters on record</div></div>' +
    '  <div class="af-card af-stat"><div class="af-num-big" id="af-k-year">—</div><div class="af-label">declared this year</div></div>' +
    '  <div class="af-card af-stat"><div class="af-num-big" id="af-k-states">—</div><div class="af-label">states &amp; territories</div></div>' +
    '  <div class="af-card af-stat"><div class="af-num-big af-num-text" id="af-k-type">—</div><div class="af-label">most common type, last 10 years</div></div>' +
    "</div>" +
    '<div class="af-grid">' +
    '  <section class="af-card"><h3>Disasters declared per year since 2000</h3><div class="af-chart"><canvas id="af-c-year" role="img" aria-label="Line chart of disasters declared per year"></canvas></div></section>' +
    '  <section class="af-card" aria-labelledby="af-eval-h"><h3 id="af-eval-h">Answer quality</h3><div id="af-evals"><p class="af-muted">Loading the latest eval run…</p></div></section>' +
    "</div>" +
    '<div class="af-grid-2">' +
    '  <section class="af-card"><h3>By incident type, last 10 years</h3><div class="af-chart"><canvas id="af-c-type" role="img" aria-label="Bar chart of disasters by incident type"></canvas></div></section>' +
    '  <section class="af-card"><h3>Top 10 states, last 10 years</h3><div class="af-chart"><canvas id="af-c-state" role="img" aria-label="Bar chart of disasters by state"></canvas></div></section>' +
    "</div>" +
    '<section class="af-card"><h3>Most recent declarations</h3><div class="af-table-wrap"><table><thead><tr>' +
    '<th scope="col">Date</th><th scope="col">Declaration</th><th scope="col">State</th><th scope="col">Incident</th><th scope="col">Title</th>' +
    '</tr></thead><tbody id="af-recent"><tr><td colspan="5" class="af-muted">Loading…</td></tr></tbody></table></div></section>' +
    '<p class="af-note" id="af-note">Data: <a href="https://www.fema.gov/about/openfema/data-sets" rel="noopener">OpenFEMA</a>. ' +
    "This product uses the FEMA OpenFEMA API but is not endorsed by FEMA. Counts are distinct disasters, not county rows. " +
    "Answers are written by an AI model from the query results shown with them, so check figures that matter. " +
    '<a href="https://github.com/cbogdewi/fema-qa-agent" rel="noopener">Source code</a>.</p>';

  // ---------- Charts ----------
  var chartReady = new Promise(function (resolve) {
    if (window.Chart) return resolve(true);
    var s = document.createElement("script");
    s.src = CHART_SRC; s.async = true;
    s.onload = function () { resolve(true); };
    s.onerror = function () { resolve(false); };
    document.head.appendChild(s);
  });

  function draw(id, type, labels, values, label, color, horizontal) {
    chartReady.then(function (ok) {
      if (!ok || !window.Chart) return;
      var Chart = window.Chart;
      Chart.defaults.font.family = getComputedStyle(root).fontFamily;
      Chart.defaults.color = C.ink2;
      if (charts[id]) charts[id].destroy();
      var line = type === "line";
      charts[id] = new Chart(document.getElementById(id), {
        type: type,
        data: { labels: labels, datasets: [{
          label: label, data: values, borderColor: color, backgroundColor: line ? color + "1f" : color,
          borderWidth: line ? 2 : 0, fill: line, tension: 0.3, cubicInterpolationMode: "monotone", pointRadius: 0, pointHoverRadius: 5,
          borderRadius: 4, borderSkipped: "start", maxBarThickness: 26
        }]},
        options: {
          maintainAspectRatio: false, indexAxis: horizontal ? "y" : "x",
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: false },
                     tooltip: { backgroundColor: C.ink, padding: 10, cornerRadius: 10, displayColors: false } },
          scales: {
            x: { grid: { display: !!horizontal, color: C.line }, border: { display: false }, ticks: { maxRotation: 0, autoSkip: true } },
            y: { grid: { display: !horizontal, color: C.line }, border: { display: false }, beginAtZero: true }
          }
        }
      });
    });
  }

  function getJSON(path, opts) {
    return fetch(API + path, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (body) {
        if (!r.ok) throw new Error(body.detail || "Request failed (" + r.status + ")");
        return body;
      });
    });
  }

  // ---------- Stats ----------
  getJSON("/api/stats").then(function (s) {
    var k = s.kpis;
    $("#af-k-total").textContent = fmt(k.total_disasters);
    $("#af-k-total-l").textContent = "disasters on record since " + String(k.first_declaration).slice(0, 4);
    $("#af-k-year").textContent = fmt(k.disasters_this_year);
    $("#af-k-states").textContent = fmt(k.states_and_territories);
    $("#af-k-type").textContent = k.top_incident_type_10y || "—";
    draw("af-c-year", "line", s.per_year.map(function (d) { return d.year; }), s.per_year.map(function (d) { return d.disasters; }), "Disasters", C.blue);
    draw("af-c-type", "bar", s.by_incident_type_10y.map(function (d) { return d.incident_type; }), s.by_incident_type_10y.map(function (d) { return d.disasters; }), "Disasters", C.green, true);
    draw("af-c-state", "bar", s.by_state_10y.map(function (d) { return d.state; }), s.by_state_10y.map(function (d) { return d.disasters; }), "Disasters", C.blue);
    $("#af-recent").innerHTML = s.recent.map(function (d) {
      return "<tr><td>" + esc(new Date(d.date + "T00:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })) +
        "</td><td>" + esc(d.id) + "</td><td>" + esc(d.state) + "</td><td>" + esc(d.incident_type) + "</td><td>" + esc(d.title) + "</td></tr>";
    }).join("");
    if (s.meta && s.meta.loaded_at) {
      $("#af-note").insertAdjacentHTML("afterbegin", "Data refreshed " +
        esc(new Date(s.meta.loaded_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })) + ". ");
    }
  }).catch(function () {
    $("#af-recent").innerHTML = '<tr><td colspan="5" class="af-muted">The data service is waking up. Refresh in a few seconds.</td></tr>';
  });

  // ---------- Evals ----------
  getJSON("/api/evals").then(function (e) {
    if (!e.available) { $("#af-evals").innerHTML = '<p class="af-muted">No eval run published yet.</p>'; return; }
    var pct = Math.round(e.pass_rate * 100), good = e.pass_rate >= e.threshold;
    var cats = Object.keys(e.by_category).map(function (k) {
      var v = e.by_category[k];
      return '<div class="af-cat"><span>' + esc(k.replace(/-/g, " ")) + '</span><span class="' + (v.passed === v.total ? "af-ok" : "af-warn") + '">' + v.passed + "/" + v.total + "</span></div>";
    }).join("");
    $("#af-evals").innerHTML =
      '<div class="af-score"><span class="af-score-big">' + pct + '%</span><span class="' + (good ? "af-ok" : "af-warn") + '">' + (good ? "✓ passing" : "below the bar") + "</span></div>" +
      '<div class="af-meter" role="img" aria-label="' + pct + ' percent of test questions answered correctly"><span style="width:' + pct + '%"></span></div>' +
      '<p class="af-muted">' + e.passed + " of " + e.total + " test questions answered correctly. Deploys are blocked below " + Math.round(e.threshold * 100) + "%.</p>" +
      '<div class="af-cats">' + cats + "</div>" +
      '<p class="af-note af-mt">Last run ' + esc(new Date(e.run_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })) +
      " · median " + fmt(e.latency_ms && e.latency_ms.median) + " ms · " + esc(e.model) + "</p>";
  }).catch(function () { $("#af-evals").innerHTML = '<p class="af-muted">Eval results unavailable.</p>'; });

  // ---------- Ask ----------
  var box = $(".af-answer"), btn = $(".af-btn"), input = $("#af-q");

  function render(res) {
    box.classList.toggle("is-refused", !!res.refused);
    $(".af-answer-text").textContent = res.answer;
    var tags = [];
    if (res.refused) tags.push('<span class="af-tag is-warn">Outside this dataset</span>');
    else if (!res.error) tags.push('<span class="af-tag is-good">✓ Based on ' + fmt(res.rows.length) + " result row" + (res.rows.length === 1 ? "" : "s") + "</span>");
    if (res.latency_ms) tags.push('<span class="af-tag">' + (res.latency_ms / 1000).toFixed(1) + " s</span>");
    if (res.model) tags.push('<span class="af-tag">' + esc(res.model) + "</span>");
    $(".af-tags").innerHTML = tags.join("");

    var hasRows = res.columns && res.columns.length && res.rows.length;
    $(".af-data").hidden = !hasRows;
    $(".af-sql").hidden = !res.sql;
    $(".af-sql pre").textContent = res.sql || "";
    if (hasRows) {
      var num = res.columns.map(function (_, i) { return res.rows.every(function (r) { return typeof r[i] === "number"; }); });
      $(".af-data .af-table-wrap").innerHTML = "<table><thead><tr>" +
        res.columns.map(function (c, i) { return '<th scope="col" class="' + (num[i] ? "af-num" : "") + '">' + esc(c) + "</th>"; }).join("") +
        "</tr></thead><tbody>" + res.rows.map(function (r) {
          return "<tr>" + r.map(function (v, i) { return '<td class="' + (num[i] ? "af-num" : "") + '">' + esc(fmt(v)) + "</td>"; }).join("") + "</tr>";
        }).join("") + "</tbody></table>";
    }
    var chartBox = $(".af-chart-answer");
    chartBox.hidden = !res.chart;
    if (res.chart) {
      draw("af-c-answer", res.chart.type, res.chart.labels, res.chart.values, res.chart.label,
        res.chart.type === "line" ? C.blue : C.green, res.chart.type === "bar" && res.chart.labels.length > 8);
    }
  }

  function ask(q) {
    btn.disabled = true;
    box.hidden = false;
    box.classList.remove("is-refused");
    $(".af-answer-text").innerHTML = '<span class="af-spinner" aria-hidden="true"></span>Querying FEMA data…';
    $(".af-tags").innerHTML = "";
    $(".af-data").hidden = true; $(".af-sql").hidden = true; $(".af-chart-answer").hidden = true;
    getJSON("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q }) })
      .then(render)
      .catch(function (e) { $(".af-answer-text").textContent = e.message || "Something went wrong. Please try again."; })
      .then(function () { btn.disabled = false; });
  }

  $(".af-chips").addEventListener("click", function (e) {
    var chip = e.target.closest(".af-chip");
    if (chip) { input.value = chip.textContent; ask(chip.textContent); }
  });
  $(".af-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim();
    if (q.length >= 3) ask(q);
  });
})();
