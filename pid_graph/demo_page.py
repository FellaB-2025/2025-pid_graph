"""Render the scenario demonstrator page from pid_graph.demo.build() data. One self-contained file, no libraries.

© 2026 Alan Bowden — Bowden Simulators. All rights reserved.

render(data, standalone=True)  a complete HTML document (reports/demo_U-100.html, opens from disk)
render(data, standalone=False) the same page without <html>/<head>/<body>, for publishing as a claude.ai artifact
House style: Arial, navy / teal / amber, forced light colour scheme, copyright footer.
"""
from __future__ import annotations

import json

from .situation import SITUATION_JS

STYLE = r"""
<title>__UNIT__ Scenario Explorer</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* Layout: navy masthead; picker strip; two columns (walk-through left, graph + inspector right); tabs for findings, scorecard, documents, method. */
:root{
  --navy:#1f3a5f; --navy-2:#2c4d78; --teal:#127c7c; --teal-soft:#e3f2f1; --amber:#c98a0b; --amber-soft:#fbf1dc;
  --ink:#1c2633; --muted:#5a6878; --paper:#f5f7f9; --card:#ffffff; --line:#d6dee6;
  --stop:#b42318; --stop-soft:#fdecea; --warn:#9a5b00; --warn-soft:#fff4e0; --ok:#2f7d4f; --ok-soft:#e8f5ec; --info:#3f5d7d; --info-soft:#eaf0f6;
  --c-instrument:#127c7c; --c-alarm:#c98a0b; --c-sif:#9b2c3a; --c-scenario:#6b4c9a; --c-equipment:#5a6878; --c-document:#1f3a5f; --c-moc:#7a4b12;
  --font:Arial, "Helvetica Neue", Helvetica, sans-serif; --mono:Consolas, "Cascadia Mono", "Courier New", monospace;
  color-scheme:light;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.5 var(--font)}
.wrap{padding-left:max(16px, env(safe-area-inset-left, 0px));padding-right:max(16px, env(safe-area-inset-right, 0px));max-width:1500px;margin:0 auto}
header.mast{background:var(--navy);color:#fff}
header.mast .wrap{padding-block:14px 12px;display:flex;flex-wrap:wrap;gap:6px 24px;align-items:baseline;justify-content:space-between}
header.mast h1{margin:0;font-size:20px;letter-spacing:.01em}
header.mast p{margin:0;color:#c9d6e6;font-size:13px}
nav.tabs{background:var(--navy-2)}
nav.tabs .wrap{display:flex;gap:2px;overflow-x:auto}
nav.tabs button{background:none;border:0;color:#d6e2f0;font:600 13px var(--font);padding:10px 14px;cursor:pointer;border-bottom:3px solid transparent;white-space:nowrap}
nav.tabs button[aria-selected="true"]{color:#fff;border-bottom-color:var(--amber)}
nav.tabs button:focus-visible,button:focus-visible,select:focus-visible,.node:focus-visible{outline:2px solid var(--amber);outline-offset:2px}
main .wrap{padding-block:16px 32px}
.picker{display:grid;gap:10px;margin-bottom:16px}
.kinds{display:flex;flex-wrap:wrap;gap:6px}
.kind{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:16px;padding:5px 12px;font:13px var(--font);cursor:pointer}
.kind[aria-pressed="true"]{background:var(--teal);border-color:var(--teal);color:#fff}
.kind small{color:inherit;opacity:.75;margin-left:4px}
.row{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
label.lbl{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
select{font:14px var(--font);padding:6px 8px;border:1px solid var(--line);border-radius:4px;background:var(--card);color:var(--ink);max-width:100%}
.show{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.show button{border:0;background:var(--amber-soft);color:var(--ink);border-radius:4px;padding:4px 9px;font:12px var(--font);cursor:pointer}
.show button.on{background:var(--amber);color:#fff}
.show b{font-family:var(--mono);margin-right:4px}
.grid{display:grid;grid-template-columns:minmax(0, 5fr) minmax(0, 7fr);gap:16px}
@media (max-width:980px){.grid{grid-template-columns:minmax(0, 1fr)}}
.panel{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:14px 16px;min-width:0}
.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:var(--teal);font-weight:700}
h2{margin:4px 0 6px;font-size:19px;text-wrap:balance}
h3{margin:0 0 8px;font-size:14px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.ask{margin:0 0 10px;color:var(--muted);max-width:65ch}
.stats{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;color:var(--muted);margin-bottom:12px;font-variant-numeric:tabular-nums}
.stats b{color:var(--ink);font-size:15px}
.ctl{display:flex;gap:6px;margin:6px 0 10px;flex-wrap:wrap}
.ctl button{font:13px var(--font);padding:5px 10px;border:1px solid var(--line);background:var(--card);border-radius:4px;cursor:pointer;color:var(--ink)}
.ctl button.primary{background:var(--navy);color:#fff;border-color:var(--navy)}
.ctl button:disabled{opacity:.4;cursor:default}
ol.steps{list-style:none;margin:0;padding:0;display:grid;gap:8px;counter-reset:st}
ol.steps li{border:1px solid var(--line);border-left:4px solid var(--line);border-radius:4px;padding:8px 10px;cursor:pointer;counter-increment:st;background:var(--card)}
ol.steps li.cur{border-left-color:var(--teal);background:var(--teal-soft)}
ol.steps li.later{opacity:.45}
ol.steps li .t{font-weight:700}
ol.steps li .t::before{content:counter(st) ". ";color:var(--teal)}
ol.steps li p{margin:4px 0 6px;max-width:75ch}
.chips{display:flex;flex-wrap:wrap;gap:4px}
.chip{font:11px var(--mono);background:var(--info-soft);color:var(--navy);border-radius:3px;padding:1px 6px;white-space:nowrap}
.verdict{margin-top:12px;border-radius:5px;padding:10px 12px;border-left:5px solid}
.verdict .v{font-weight:700;text-transform:uppercase;letter-spacing:.05em;font-size:12px}
.lv-stop{background:var(--stop-soft);border-color:var(--stop)} .lv-stop .v{color:var(--stop)}
.lv-warn{background:var(--warn-soft);border-color:var(--warn)} .lv-warn .v{color:var(--warn)}
.lv-ok{background:var(--ok-soft);border-color:var(--ok)} .lv-ok .v{color:var(--ok)}
.lv-info{background:var(--info-soft);border-color:var(--info)} .lv-info .v{color:var(--info)}
.gbox{overflow:auto;border:1px solid var(--line);border-radius:4px;background:#fbfcfd;max-height:640px}
svg text{font-family:var(--font)}
.node{cursor:pointer}
.node rect{stroke-width:1.5}
.node.dim{opacity:.35}
.node.sel rect{stroke:var(--amber)!important;stroke-width:3}
.edge{fill:none}
.legend{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:12px;color:var(--muted);margin-top:8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.inspect{margin-top:12px;font-size:13px}
.inspect table{border-collapse:collapse;width:100%}
.inspect td{border-top:1px solid var(--line);padding:3px 6px;vertical-align:top;word-break:break-word}
.inspect td:first-child{color:var(--muted);white-space:nowrap;width:1%}
.findings{display:grid;gap:8px}
.f{border:1px solid var(--line);border-left:5px solid var(--info);border-radius:4px;padding:8px 10px;background:var(--card)}
.f.stop{border-left-color:var(--stop)} .f.warn{border-left-color:var(--warn)} .f.ok{border-left-color:var(--ok)}
.f .h{display:flex;flex-wrap:wrap;gap:6px;align-items:baseline}
.code{font:700 12px var(--mono);color:#fff;background:var(--info);border-radius:3px;padding:1px 6px}
.f.stop .code{background:var(--stop)} .f.warn .code{background:var(--warn)}
.f .src{font-size:12px;color:var(--muted)}
.f p{margin:4px 0 0}
.tw{overflow-x:auto}
table.list{border-collapse:collapse;width:100%;font-size:13px;background:var(--card)}
table.list th{text-align:left;background:var(--navy);color:#fff;padding:6px 8px;font-weight:600;white-space:nowrap}
table.list td{border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top}
table.list tr.click{cursor:pointer}
table.list tr.click:hover td{background:var(--teal-soft)}
.yes{color:var(--ok);font-weight:700} .no{color:var(--stop);font-weight:700}
.big{font-size:34px;font-weight:700;color:var(--navy);font-variant-numeric:tabular-nums}
.prose{max-width:75ch}
.prose code{font-family:var(--mono);background:var(--info-soft);padding:0 4px;border-radius:3px}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
footer{border-top:1px solid var(--line);color:var(--muted);font-size:12px}
footer .wrap{padding-block:12px 18px;display:flex;flex-wrap:wrap;gap:6px 24px;justify-content:space-between}
.tog{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:4px;padding:4px 9px;font:13px var(--mono);cursor:pointer}
.tog[aria-pressed="true"]{background:var(--stop);border-color:var(--stop);color:#fff}
.grp{margin-bottom:12px}
.grp .lbl{display:block;margin-bottom:5px}
.togs{display:flex;flex-wrap:wrap;gap:5px}
.pill{display:inline-block;border-radius:10px;padding:1px 9px;font-size:12px;font-weight:700;color:#fff;white-space:nowrap}
.pill.ok{background:var(--ok)} .pill.warn{background:var(--warn)} .pill.stop{background:var(--stop)}
.card{border:1px solid var(--line);border-left:5px solid var(--ok);border-radius:4px;padding:9px 11px;background:var(--card)}
.card.warn{border-left-color:var(--warn)} .card.stop{border-left-color:var(--stop)}
.card h4{margin:0 0 4px;font-size:14px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.card p{margin:3px 0}
.card ul{margin:4px 0 4px 18px;padding:0}
.card .q{color:var(--muted);font-style:italic}
.layer{display:inline-block;border-radius:3px;padding:1px 7px;margin:2px 4px 2px 0;font-size:12px;border:1px solid}
.layer.ok{background:var(--ok-soft);border-color:var(--ok);color:var(--ok)}
.layer.degraded{background:var(--warn-soft);border-color:var(--warn);color:var(--warn)}
.layer.lost{background:var(--stop-soft);border-color:var(--stop);color:var(--stop);text-decoration:line-through}
.cards{display:grid;gap:8px}
[hidden]{display:none!important}
@media (prefers-reduced-motion:no-preference){ol.steps li,.node{transition:opacity .2s, background .2s}}
</style>
"""

BODY = r"""
<header class="mast"><div class="wrap">
  <h1>__UNIT__ Scenario Explorer</h1>
  <p id="sub"></p>
</div></header>
<nav class="tabs" aria-label="Views"><div class="wrap" role="tablist">
  <button role="tab" data-tab="scen" aria-selected="true">Scenarios</button>
  <button role="tab" data-tab="sit" aria-selected="false">Build a situation</button>
  <button role="tab" data-tab="find" aria-selected="false">All findings</button>
  <button role="tab" data-tab="score" aria-selected="false">Scorecard</button>
  <button role="tab" data-tab="docs" aria-selected="false">Documents</button>
  <button role="tab" data-tab="how" aria-selected="false">How it works</button>
</div></nav>
<main><div class="wrap">
  <section id="tab-scen">
    <div class="picker">
      <div class="show" id="showcase" aria-label="Demonstration order"></div>
      <div class="kinds" id="kinds" aria-label="Scenario type"></div>
      <div class="row"><label class="lbl" for="el">Element</label><select id="el"></select></div>
    </div>
    <div class="grid">
      <div class="panel" id="walk"></div>
      <div class="panel">
        <h3>The graph walked</h3>
        <div class="gbox" id="gbox"></div>
        <div class="legend" id="legend"></div>
        <div class="inspect" id="inspect"><p class="src">Select a node to see its properties and the document each fact came from.</p></div>
      </div>
    </div>
    <div class="panel" style="margin-top:16px"><h3>Findings on what this scenario touched</h3><div class="findings" id="sfind"></div></div>
  </section>
  <section id="tab-sit" hidden>
    <div class="grid">
      <div class="panel">
        <div class="eyebrow">Build a situation · Q7</div>
        <h2>Take several things out of service together</h2>
        <p class="ask">Tick anything that is bypassed, shelved, isolated or disabled. The starting point is the plant as configured at the export, with the findings already open against it.</p>
        <div class="ctl"><button id="sit-found" class="primary">As found at the export</button><button id="sit-none">Nothing out</button></div>
        <div id="sit-pick"></div>
      </div>
      <div class="panel"><div id="sit-res"></div></div>
    </div>
  </section>
  <section id="tab-find" hidden></section>
  <section id="tab-score" hidden></section>
  <section id="tab-docs" hidden></section>
  <section id="tab-how" hidden></section>
</div></main>
<footer><div class="wrap">
  <span>© 2026 Alan Bowden — Bowden Simulators. All rights reserved.</span>
  <span>Unit __UNIT__ is synthetic: dummy documents with planted discrepancies, not a real facility.</span>
</div></footer>
<script type="application/json" id="data">__DATA__</script>
<script>
__SITUATION_JS__
(function(){
const D = JSON.parse(document.getElementById('data').textContent);
const S = {}; D.scenarios.forEach(s => S[s.id] = s);
const N = {}; D.graph.nodes.forEach(n => N[n.id] = n);
const R = {}; D.graph.rels.forEach(r => R[r.id] = r);
const F = {}; D.findings.forEach(f => F[f.key] = f);
const KINDS = ['bypass','shelve','moc','closeout','sif_out','trip','where_used','doc_revised','now'];
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const slug = id => id.replace(/[^A-Za-z0-9]+/g, '-');
const bySlug = {}; D.scenarios.forEach(s => bySlug[slug(s.id)] = s.id);
const LV = {stop:'Stop', warn:'Caution', ok:'Clear', info:'Information'};
let cur = D.showcase[0], step = -1, sel = null, kind = S[cur].kind;

document.getElementById('sub').textContent = `${D.counts.nodes} nodes · ${D.counts.rels} relationships · ${D.documents.length} documents · configuration exported ${D.export_time}`;

// ---------------- picker
function picker(){
  document.getElementById('showcase').innerHTML = '<span class="lbl">Demonstration order</span>' + D.showcase.map((id, i) =>
    `<button data-sid="${esc(id)}" class="${id === cur ? 'on' : ''}"><b>${i + 1}</b>${esc(S[id].kind_title)}: ${esc(label(S[id]))}</button>`).join('');
  document.getElementById('kinds').innerHTML = KINDS.filter(k => D.scenarios.some(s => s.kind === k)).map(k => {
    const any = D.scenarios.find(s => s.kind === k), n = D.scenarios.filter(s => s.kind === k).length;
    return `<button class="kind" data-kind="${k}" aria-pressed="${k === kind}">${esc(any.kind_title)}<small>${esc(any.question)}</small></button>`; }).join('');
  const opts = D.scenarios.filter(s => s.kind === kind).sort((a, b) => label(a).localeCompare(label(b)));
  document.getElementById('el').innerHTML = opts.map(s => `<option value="${esc(s.id)}" ${s.id === cur ? 'selected' : ''}>${esc(label(s))}${s.verdict ? ' (' + LV[s.verdict.level] + ')' : ''}</option>`).join('');
}
function label(s){ const n = N['Alarm:' + s.element]; return n ? n.caption : s.element; }
document.getElementById('showcase').addEventListener('click', e => { const b = e.target.closest('button[data-sid]'); if (b) go(b.dataset.sid); });
document.getElementById('kinds').addEventListener('click', e => { const b = e.target.closest('button[data-kind]'); if (!b) return;
  kind = b.dataset.kind; const first = D.showcase.find(id => S[id].kind === kind) || D.scenarios.find(s => s.kind === kind).id; go(first); });
document.getElementById('el').addEventListener('change', e => go(e.target.value));

function go(id, keepStep){
  cur = id; kind = S[id].kind; if (!keepStep) step = -1; sel = null;
  if (location.hash.slice(1) !== slug(id)) { try { history.replaceState(null, '', '#' + slug(id)); } catch (err) { location.hash = slug(id); } }
  picker(); walk(); graph(); sfind(); inspect();
}

// ---------------- walk-through
function walk(){
  const s = S[cur], st = s.steps, last = st.length - 1;
  const showAll = step < 0;
  let h = `<div class="eyebrow">${esc(s.kind_title)} · ${esc(s.question)}</div><h2>${esc(s.title)}</h2><p class="ask">${esc(s.ask)}</p>`;
  h += `<div class="stats"><span><b>${s.documents.length}</b> documents consulted</span><span><b>${s.relationships_followed}</b> relationships followed</span><span><b>${s.findings.length}</b> findings</span></div>`;
  h += `<div class="ctl"><button class="primary" id="b-step">${showAll ? 'Step through' : 'Show all steps'}</button>
        <button id="b-prev" ${showAll || step === 0 ? 'disabled' : ''}>Previous</button><button id="b-next" ${showAll || step === last ? 'disabled' : ''}>Next</button></div>`;
  h += '<ol class="steps">' + st.map((x, i) => `<li data-i="${i}" class="${!showAll && i === step ? 'cur' : ''} ${!showAll && i > step ? 'later' : ''}">
        <div class="t">${esc(x.title)}</div><p>${esc(x.text)}</p>${x.docs.length ? '<div class="chips">' + x.docs.map(d => `<span class="chip" title="${esc(docTitle(d))}">${esc(d)}</span>`).join('') + '</div>' : ''}</li>`).join('') + '</ol>';
  if (s.verdict && (showAll || step === last)) h += `<div class="verdict lv-${s.verdict.level}"><div class="v">${LV[s.verdict.level]}</div>${esc(s.verdict.text)}</div>`;
  const w = document.getElementById('walk'); w.innerHTML = h;
  w.querySelector('#b-step').onclick = () => { step = showAll ? 0 : -1; walk(); graph(); };
  w.querySelector('#b-prev').onclick = () => { if (step > 0) { step--; walk(); graph(); } };
  w.querySelector('#b-next').onclick = () => { if (step < last) { step++; walk(); graph(); } };
  w.querySelectorAll('ol.steps li').forEach(li => li.onclick = () => { step = +li.dataset.i; walk(); graph(); });
}
function docTitle(d){ const n = N['Document:' + d]; return n ? `${n.props.doc_type || ''} ${n.props.title || ''}` : d; }

// ---------------- graph drawing: one column per kind of node, documents on the right
const COLS = [['MOC', 'Change'], ['Instrument', 'Instruments'], ['Alarm', 'Alarms'], ['SIF', 'Safety functions'], ['Hazard', 'Hazard and equipment'], ['Document', 'Documents']];
const COLOR = {Instrument:'var(--c-instrument)', Alarm:'var(--c-alarm)', SIF:'var(--c-sif)', Scenario:'var(--c-scenario)', Equipment:'var(--c-equipment)', Line:'var(--c-equipment)', Document:'var(--c-document)', MOC:'var(--c-moc)'};
const EDGE = {SHOWN_ON:'#b8c4d0', INITIATES:'#127c7c', ACTUATES:'#9b2c3a', GENERATES:'#c98a0b', COMPENSATES_FOR:'#2f7d4f', CREDITS:'#6b4c9a', PROTECTS:'#9b2c3a', THREATENS:'#6b4c9a', MEASURES:'#5a6878', INSTALLED_ON:'#5a6878', RAISES:'#b42318', FEEDS:'#8a96a3'};
function col(n){ if (n.label === 'Document') return n.caption.startsWith('MOC-') ? 'MOC' : 'Document'; return ['Line', 'Equipment', 'Scenario'].includes(n.label) ? 'Hazard' : n.label; }
function hue(n){ return n.label === 'Document' ? col(n) : n.label; }
function graph(){
  const s = S[cur], upto = step < 0 ? s.steps.length - 1 : step;
  const nodes = new Set(), rels = new Set(), now = new Set(step < 0 ? [] : s.steps[step].nodes), nowR = new Set(step < 0 ? [] : s.steps[step].rels);
  s.steps.slice(0, upto + 1).forEach(x => { x.nodes.forEach(n => N[n] && nodes.add(n)); x.rels.forEach(r => R[r] && rels.add(r)); x.docs.forEach(d => N['Document:' + d] && nodes.add('Document:' + d)); });
  const groups = COLS.map(([k]) => [...nodes].filter(n => col(N[n]) === k).sort((a, b) => N[a].caption.localeCompare(N[b].caption)));
  const used = COLS.map((c, i) => [c, groups[i]]).filter(x => x[1].length);
  const W = 128, GAP = 38, H = 26, VG = 10, TOP = 34;
  const width = Math.max(used.length * (W + GAP) - GAP + 20, 300), rows = Math.max(1, ...used.map(x => x[1].length));
  const height = TOP + rows * (H + VG) + 10, pos = {};
  used.forEach(([c, ns], ci) => ns.forEach((n, ri) => pos[n] = {x: 10 + ci * (W + GAP), y: TOP + ri * (H + VG)}));
  let svg = `<svg style="width:100%;min-width:${Math.min(width, 760)}px;height:auto;display:block" viewBox="0 0 ${width} ${height}" role="img" aria-label="Nodes and relationships this scenario walked">`;
  used.forEach(([c], ci) => svg += `<text x="${10 + ci * (W + GAP)}" y="18" font-size="11" fill="#5a6878" font-weight="700" letter-spacing=".06em">${esc(c[1].toUpperCase())}</text>`);
  const drawn = new Set();
  [...rels].forEach(id => { const r = R[id]; if (!pos[r.from] || !pos[r.to]) return; const k = r.from + '>' + r.to + '>' + r.type; if (drawn.has(k)) return; drawn.add(k);
    const a = pos[r.from], b = pos[r.to], fwd = a.x <= b.x;
    const x1 = fwd ? a.x + W : a.x, x2 = fwd ? b.x : b.x + W, y1 = a.y + H / 2, y2 = b.y + H / 2, dx = Math.max(30, Math.abs(x2 - x1) / 2) * (fwd ? 1 : -1);
    const same = a.x === b.x, d = same ? `M${a.x + W} ${y1} C${a.x + W + 40} ${y1} ${b.x + W + 40} ${y2} ${b.x + W} ${y2}` : `M${x1} ${y1} C${x1 + dx} ${y1} ${x2 - dx} ${y2} ${x2} ${y2}`;
    const hot = nowR.has(id), dim = step >= 0 && !hot;
    svg += `<path class="edge" d="${d}" stroke="${EDGE[r.type] || '#8a96a3'}" stroke-width="${hot ? 2.6 : r.type === 'SHOWN_ON' ? 1 : 1.6}" ${r.type === 'SHOWN_ON' ? 'stroke-dasharray="3 3"' : ''} opacity="${dim ? .25 : 1}"><title>${esc(r.type)} (${esc(r.props.source_doc || '')})</title></path>`; });
  Object.entries(pos).forEach(([id, p]) => { const n = N[id], c = COLOR[hue(n)] || 'var(--c-equipment)', dim = step >= 0 && !now.has(id);
    const cap = n.caption.length > 17 ? n.caption.slice(0, 16) + '…' : n.caption;
    svg += `<g class="node ${dim ? 'dim' : ''} ${sel === id ? 'sel' : ''}" data-id="${esc(id)}" tabindex="0" role="button" aria-label="${esc(n.label + ' ' + n.caption)}">
      <rect x="${p.x}" y="${p.y}" width="${W}" height="${H}" rx="4" fill="#fff" stroke="${c}" ${n.stub ? 'stroke-dasharray="4 3"' : ''}></rect>
      <rect x="${p.x}" y="${p.y}" width="5" height="${H}" rx="2" fill="${c}" stroke="none"></rect>
      <text x="${p.x + 11}" y="${p.y + 17}" font-size="12" fill="#1c2633">${esc(cap)}</text><title>${esc(n.label + ': ' + n.caption + (n.stub ? ' (not in the index)' : ''))}</title></g>`; });
  svg += '</svg>';
  const box = document.getElementById('gbox'); box.innerHTML = svg;
  box.querySelectorAll('.node').forEach(g => { const f = () => { sel = g.dataset.id; inspect(); graph(); }; g.onclick = f; g.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); f(); } }; });
  document.getElementById('legend').innerHTML = Object.entries({Instrument:'Instrument', Alarm:'Alarm', SIF:'SIF', Scenario:'LOPA scenario', Equipment:'Equipment / line', Document:'Document', MOC:'MOC'})
    .map(([k, v]) => `<span><i style="background:${COLOR[k]}"></i>${v}</span>`).join('') + '<span>dashed outline: not in the instrument index</span><span>dotted line: shown on a document</span>';
}

// ---------------- inspector
function inspect(){
  const el = document.getElementById('inspect');
  if (!sel || !N[sel]) { el.innerHTML = '<p class="src">Select a node to see its properties and the document each fact came from.</p>'; return; }
  const n = N[sel], p = n.props, prov = ['source_doc', 'source_rev', 'source_sheet', 'source_ref', 'extracted_by'];
  const rows = Object.entries(p).filter(([k]) => !prov.includes(k) && k !== 'stub').map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(Array.isArray(v) ? v.join('; ') : v)}</td></tr>`).join('');
  const docs = D.graph.rels.filter(r => r.type === 'SHOWN_ON' && r.from === sel).map(r => r.to.slice(9));
  const states = [...new Set(D.graph.rels.filter(r => r.type !== 'SHOWN_ON' && (r.from === sel || r.to === sel)).map(r => r.props.source_doc))];
  el.innerHTML = `<h3>${esc(n.label)}: ${esc(n.caption)}${n.stub ? ' · not in the index' : ''}</h3><div class="tw"><table>${rows}
    <tr><td>shown on</td><td>${esc(docs.join(', ') || '-')}</td></tr><tr><td>facts stated by</td><td>${esc(states.join(', ') || '-')}</td></tr>
    <tr><td>last written by</td><td>${esc((p.source_doc || '') + ' rev ' + (p.source_rev || '') + ' ' + (p.source_ref || ''))}</td></tr></table></div>`;
}

// ---------------- findings
function fcard(f){ return `<div class="f ${f.level}"><div class="h"><span class="code">${esc(f.code)}</span><b>${esc(f.title)}</b><span class="src">${esc(f.id)}</span></div>
  <p>${esc(f.detail)}</p><div class="src">${esc(f.sources)}${f.refs ? ' · ' + esc(f.refs) : ''}</div></div>`; }
const ORDER = {stop:0, warn:1, info:2, ok:3};
function sfind(){
  const fs = S[cur].findings.map(k => F[k]).sort((a, b) => ORDER[a.level] - ORDER[b.level] || a.code.localeCompare(b.code, undefined, {numeric:true}));
  document.getElementById('sfind').innerHTML = fs.length ? fs.map(fcard).join('') : '<p class="src">No finding concerns the elements this scenario walked.</p>';
}
let ffilter = 'all';
function allFind(){
  const fs = D.findings.filter(f => ffilter === 'all' || f.level === ffilter || (ffilter === 'ops' && f.code[0] === 'C') || (ffilter === 'design' && f.code[0] === 'X'))
    .sort((a, b) => a.code[0].localeCompare(b.code[0]) || a.code.localeCompare(b.code, undefined, {numeric:true}) || a.id.localeCompare(b.id));
  const btn = (k, t) => `<button class="kind" data-f="${k}" aria-pressed="${ffilter === k}">${t}</button>`;
  const el = document.getElementById('tab-find');
  el.innerHTML = `<div class="panel"><div class="eyebrow">Rules engines</div><h2>Every finding (${D.findings.length})</h2>
    <p class="ask">C-codes compare the operations documents (MADB, configuration export, SIL verification, MOC register) with the design. X-codes are the design reconciliation (index, P&IDs, C&E, SRS, LOPA). Both run over the whole graph; a scenario shows the ones on the elements it walked.</p>
    <div class="filters">${btn('all', 'All')}${btn('stop', 'Stop')}${btn('warn', 'Caution')}${btn('info', 'Information')}${btn('ops', 'Operations (C)')}${btn('design', 'Design (X)')}</div>
    <div class="findings">${fs.map(fcard).join('')}</div></div>`;
  el.querySelectorAll('[data-f]').forEach(b => b.onclick = () => { ffilter = b.dataset.f; allFind(); });
}

// ---------------- scorecard
function score(){
  const sc = D.scorecard, el = document.getElementById('tab-score');
  if (!sc) { el.innerHTML = '<div class="panel">No answer key loaded.</div>'; return; }
  el.innerHTML = `<div class="panel"><div class="eyebrow">Concept test</div><h2>Planted problems the graph surfaced</h2>
    <div class="row"><span class="big">${sc.found} of ${sc.planted}</span><span class="ask" style="margin:0">Batch 1 of the test documents carries ${sc.planted} deliberate discrepancies, listed in an answer key written before the checks.
    A problem counts as found when a check of the matching kind fires on one of its tags. The checks were written knowing what was planted, so this proves the method works end to end, not that it finds unknown problems. The next batch will be a blind test.</span></div>
    <div class="tw" style="margin-top:12px"><table class="list"><tr><th>Item</th><th>Questions</th><th>Found</th><th>Found by</th><th>What was planted</th></tr>
    ${sc.items.map(i => `<tr><td>${esc(i.id)}</td><td>${esc(i.questions.join(', '))}</td><td class="${i.found ? 'yes' : 'no'}">${i.found ? 'Yes' : 'No'}</td><td>${esc(i.by.join('; '))}</td><td>${esc(D.answer_key[i.id].finding)}</td></tr>`).join('')}
    </table></div><p class="src">Findings not tied to a planted item (${sc.other_findings.length}): ${esc(sc.other_findings.join(', '))}. Each is a real consequence of the test data; read them in All findings.</p></div>`;
}

// ---------------- documents
function docs(){
  const cnt = {}; D.graph.rels.forEach(r => { if (r.type === 'SHOWN_ON') { const d = r.to.slice(9); cnt[d] = (cnt[d] || 0) + 1; } });
  const el = document.getElementById('tab-docs');
  el.innerHTML = `<div class="panel"><div class="eyebrow">Sources</div><h2>The ${D.documents.length} documents in the graph</h2>
    <p class="ask">Every node and relationship carries the document, revision, sheet and row it came from. Select a row to see what depends on that document.</p>
    <div class="tw"><table class="list"><tr><th>Document</th><th>Rev</th><th>Type</th><th>Title</th><th>Elements shown on it</th></tr>
    ${D.documents.map(d => `<tr class="${S['doc_revised:' + d.doc_no] ? 'click' : ''}" data-d="${esc(d.doc_no)}"><td>${esc(d.doc_no)}</td><td>${esc(d.rev)}</td><td>${esc(d.doc_type)}</td><td>${esc(d.title)}</td><td>${cnt[d.doc_no] || 0}</td></tr>`).join('')}
    </table></div></div>`;
  el.querySelectorAll('tr[data-d]').forEach(tr => tr.onclick = () => { const id = 'doc_revised:' + tr.dataset.d; if (S[id]) { tab('scen'); go(id); } });
}

// ---------------- method
function how(){
  const c = D.counts, el = document.getElementById('tab-how');
  el.innerHTML = `<div class="panel prose"><div class="eyebrow">Method</div><h2>How the explorer answers</h2>
  <p>Every document of unit ${esc(D.unit)} is loaded into one property graph: the instrument index, the P&IDs where supplied, the cause and effect chart, the SRS, the LOPA, the curated compensating-measures register, and the operations documents (master alarm database, DCS/SIS configuration export, SIL verification, MOC register, document register). One tag is one node however many documents mention it. A fact two documents state differently is kept twice, each with its source, never silently resolved.</p>
  <p>The graph holds ${c.nodes} nodes and ${c.rels} relationships: ${esc(Object.entries(c.by_label).map(([k, v]) => v + ' ' + k).join(', '))}.</p>
  <p>Each scenario is a fixed template: the same steps run for every element it applies to, which is why you can pick any initiator, alarm, SIF, MOC or document. A template follows named relationships (INITIATES, PROTECTS, CREDITS, COMPENSATES_FOR, GENERATES, SHOWN_ON) and reads the properties each document put on a node. Nothing is generated by a language model, and only facts from registers, curated entries or engineer-accepted extraction are used.</p>
  <h3 style="margin-top:16px">Cross-document checks</h3><div class="tw"><table class="list"><tr><th>Code</th><th>Rule</th><th>Fired</th></tr>
  ${Object.entries(D.titles).map(([k, v]) => `<tr><td>${k}</td><td>${esc(v)}</td><td>${D.ops_by_code[k] || 0}</td></tr>`).join('')}</table></div>
  <h3 style="margin-top:16px">What a change reaches (MOC impact)</h3>
  <p>I1: if the MOC names alarms, the alarms are what change; otherwise every element it names is affected. I2: an affected instrument's alarms are affected. I3: an affected alarm reaches the documents that credit it (LOPA), rely on it as a compensating measure (curated register) or name it in a bypass condition (SRS). I4: an alarm on a SIF initiator reaches that SIF's SRS, for the margin to the trip. I5: an affected element reaches every document it is shown on or that states a fact about it.</p>
  <h3 style="margin-top:16px">Rebuild</h3><p><code>.venv\\Scripts\\python -m pid_graph.demo</code> regenerates this page from the documents in <code>data\\</code>.</p></div>`;
}

// ---------------- build a situation
const M = D.situation; let outSet = new Set(M.presets.as_found);
const STAT = {normal:['Normal', 'ok'], degraded:['Degraded', 'warn'], lost:['Cannot trip', 'stop'], out:['Out of service', 'stop'], undefined:['Not defined', 'stop']};
const ASTATE = {ok:'counts', impaired:'in question', shelved:'shelved', source_out:'its transmitter is out', unavailable:'not available', unknown:'unknown'};
const UNAV = {not_in_any_register:'not in any alarm register', not_configured:'rationalised but not configured', disabled:'disabled in the configuration'};
const acap = a => (M.alarms[a] || {}).caption || a;
function violation(v, s){
  const it = v.items.map(acap).join(', ');
  return {multiple_channels:`More than one initiator is out (${it}). The configuration and the SIL verification define one channel at a time only.`,
    no_override:`No maintenance override is configured on ${it}: the bypass would have to be forced, and the vote that results is not defined.`,
    silv_mismatch:`The SIL verification assumed ${v.items[0]} with one channel out; the configured override gives ${v.items[1]}.`,
    srs_alarm_unavailable:`The SRS bypass conditions name ${it}, which ${v.items.length > 1 ? 'do' : 'does'} not count at present.`,
    no_valid_cm: s.cms.length ? 'No compensating alarm counts.' : 'No compensating alarm is curated for this function.'}[v.code] || v.code;
}
function whyAlarm(a, state){
  const al = M.alarms[a]; if (!al) return '';
  if (state === 'unavailable') return al.unavailable.map(u => UNAV[u] || u).join('; ');
  if (state === 'impaired') return al.impaired.map(i => i.code + ': ' + i.detail).join(' ');
  if (state === 'source_out') return al.source + ' is out';
  return '';
}
function sit(){
  const res = evaluateSituation(M, [...outSet]);
  const groups = [...new Set(M.elements.map(e => e.group))];
  document.getElementById('sit-pick').innerHTML = groups.map(g => `<div class="grp"><span class="lbl">${esc(g)}</span><div class="togs">` +
    M.elements.filter(e => e.group === g).map(e => `<button class="tog" data-e="${esc(e.id)}" aria-pressed="${outSet.has(e.id)}" title="${esc(e.note)}">${esc(e.caption)}</button>`).join('') + '</div></div>').join('');
  const model = {}; M.sifs.forEach(s => model[s.id] = s);
  const lost = res.sifs.filter(s => ['lost', 'out', 'undefined'].includes(s.status)).length;
  const degBad = res.sifs.filter(s => s.status === 'degraded' && s.level === 'stop').length, degOk = res.sifs.filter(s => s.status === 'degraded' && s.level === 'warn').length;
  const scLost = res.scenarios.filter(s => s.level === 'stop').length, scQ = res.scenarios.filter(s => s.level === 'warn').length;
  const fn = n => `${n} safety function${n > 1 ? 's' : ''}`, sc = n => `${n} LOPA scenario${n > 1 ? 's' : ''}`;
  const head = res.level === 'ok' ? 'Every safety function and every credited layer is as designed.' :
    [lost ? `${fn(lost)} cannot be relied on` : '', degBad ? `${fn(degBad)} degraded outside what the SRS and SIL verification allow` : '',
     degOk ? `${fn(degOk)} degraded but compensated` : '', scLost ? `${sc(scLost)} ${scLost > 1 ? 'have' : 'has'} lost a credited layer` : '',
     scQ ? `${sc(scQ)} ${scQ > 1 ? 'have' : 'has'} a layer in question` : ''].filter(Boolean).join('; ') + '.';
  let h = `<div class="verdict lv-${res.level}" style="margin-top:0"><div class="v">${LV[res.level]}</div><b>${res.out.length ? esc(res.out.map(acap).join(', ')) + ' out of service.' : 'Nothing out of service.'}</b> ${esc(head)}</div>`;
  h += '<h3 style="margin-top:14px">Safety functions</h3><div class="cards">' + res.sifs.map(s => { const m = model[s.id], st = STAT[s.status];
    const sw = g => { const i = m.initiators.find(x => x.tag === g); return i && i.override ? i.override.switch : ''; };
    const sens = s.sensor.state === 'normal' ? `Initiators ${m.initiators.map(i => i.tag).join(', ')} voting ${m.voting.text || 'all'} (${m.voting.source}).` :
      s.sensor.state === 'degraded' ? `${s.sensor.out.join(', ')} out: running ${s.sensor.effective} on ${s.sensor.remaining.join(', ')} (override ${sw(s.sensor.out[0])}).` :
      s.sensor.state === 'lost' ? 'Every initiator is out.' : `${s.sensor.out.join(', ')} out; ${s.sensor.remaining.join(', ')} still measuring, but the vote is not defined.`;
    const fes = m.final_elements.map(f => f.tag + (f.action ? ' ' + f.action.toLowerCase() : '')).join(', ');
    const fe = s.fe.state === 'normal' ? `Final elements: ${fes}${m.fe ? ' (' + m.fe.text + ' per the SRS)' : ''}.` :
      s.fe.state === 'degraded' ? `${s.fe.out.join(', ')} out: the safe state now rests on ${s.fe.remaining.join(', ')} (${s.fe.effective}).` : `${s.fe.out.join(', ')} out: the safe state cannot be reached.`;
    const cms = s.cms.length ? s.cms.map(c => `<span class="layer ${c.state === 'ok' ? 'ok' : c.state === 'impaired' ? 'degraded' : 'lost'}" title="${esc(whyAlarm(c.alarm, c.state))}">${esc(c.caption)}: ${ASTATE[c.state]}</span>`).join('') : '<span class="src">none curated</span>';
    const why = s.status !== 'normal' ? s.cms.filter(c => c.state !== 'ok' && whyAlarm(c.alarm, c.state)).map(c => `<p class="src">${esc(c.caption)}: ${esc(whyAlarm(c.alarm, c.state))}</p>`).join('') : '';
    return `<div class="card ${s.level}"><h4>${esc(s.id)} <span class="pill ${st[1]}">${st[0]}</span><span class="src">protects ${esc(m.protects.join(', '))}</span></h4>
      <p class="src">${esc(m.description)}</p><p>${esc(s.status === 'out' ? 'The whole function is out of service.' : sens)}</p><p>${esc(fe)}</p>
      ${s.violations.length ? '<ul>' + s.violations.map(v => `<li>${esc(violation(v, s))}</li>`).join('') + '</ul>' : ''}
      <p>Compensating alarms: ${cms}</p>${why}${s.status !== 'normal' && m.bypass_conditions ? `<p class="q">SRS: “${esc(m.bypass_conditions)}”</p>` : ''}</div>`; }).join('') + '</div>';
  h += '<h3 style="margin-top:14px">LOPA scenarios</h3><div class="cards">' + res.scenarios.map(sc => { const m = M.scenarios.find(x => x.id === sc.id);
    return `<div class="card ${sc.level}"><h4>${esc(sc.id)} <span class="src">${sc.ok} of ${sc.total} credited layers fully available</span></h4><p class="src">${esc(m.consequence)}</p>
      <p>${sc.layers.map(l => `<span class="layer ${l.state}">${esc(l.caption)}${l.pfd != null ? ' · PFD ' + l.pfd : ''}${l.state === 'degraded' ? ' · in question' : l.state === 'lost' ? ' · lost' : ''}</span>`).join('')}</p></div>`; }).join('') + '</div>';
  h += '<h3 style="margin-top:14px">Protected equipment</h3><div class="cards">' + res.equipment.map(e => `<div class="card ${e.level}"><h4>${esc(e.tag)}</h4>
      <p>${e.sifs.map(x => `${esc(x.id)} <span class="pill ${STAT[x.status][1]}">${STAT[x.status][0]}</span>`).join(' &nbsp; ')}</p></div>`).join('') + '</div>';
  h += '<p class="src" style="margin-top:10px">States are what the documents define, not a risk calculation: nothing is recalculated when a layer is degraded. Hover a compensating alarm to see why it does not count.</p>';
  document.getElementById('sit-res').innerHTML = h;
  document.querySelectorAll('#sit-pick .tog').forEach(b => b.onclick = () => { outSet.has(b.dataset.e) ? outSet.delete(b.dataset.e) : outSet.add(b.dataset.e); sit(); });
}
document.getElementById('sit-found').onclick = () => { outSet = new Set(M.presets.as_found); sit(); };
document.getElementById('sit-none').onclick = () => { outSet = new Set(); sit(); };

// ---------------- tabs and start
function tab(t){ document.querySelectorAll('nav.tabs button').forEach(b => b.setAttribute('aria-selected', b.dataset.tab === t));
  ['scen', 'sit', 'find', 'score', 'docs', 'how'].forEach(k => document.getElementById('tab-' + k).hidden = k !== t); }
document.querySelectorAll('nav.tabs button').forEach(b => b.onclick = () => tab(b.dataset.tab));
allFind(); score(); docs(); how(); sit();
const start = bySlug[location.hash.slice(1)];
go(start || cur);
window.addEventListener('hashchange', () => { const id = bySlug[location.hash.slice(1)]; if (id && id !== cur) { tab('scen'); go(id); } });
})();
</script>
"""


def render(data: dict, standalone: bool = True) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/")
    unit = str(data.get("unit", ""))
    style = STYLE.replace("__UNIT__", unit)
    body = BODY.replace("__UNIT__", unit).replace("__SITUATION_JS__", SITUATION_JS).replace("__DATA__", payload)
    if not standalone:
        return style + body
    head = ('<!doctype html><html lang="en-GB"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">')
    return head + style + "</head><body>" + body + "</body></html>"
