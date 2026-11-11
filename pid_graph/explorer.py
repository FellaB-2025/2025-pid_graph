"""Standalone interactive explorer for the graph: one self-contained HTML file.

    python -m pid_graph.explorer                 -> reports/explorer_U-100.html (from Neo4j)
    python -m pid_graph.explorer --backend memory   (rebuilds the unit from data/ instead)

No external libraries, no database login: the nodes and relationships are embedded in
the page, drawn with a small force layout in SVG. Captions are the canonical keys
(tag / line_no / alarm_id / sif_id / doc_no rev), arrows carry their relationship type,
stubs are dashed, and clicking anything shows its properties and provenance.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

COLORS = {"Instrument": "#2f7fb8", "Equipment": "#b8672f", "Line": "#6b6b6b", "SIF": "#c0392b",
          "Alarm": "#d8a400", "State": "#8e44ad", "Document": "#2e8b57", "Scenario": "#16a085",
          "Segment": "#95a5a6", "InlineItem": "#e67e22", "ControlLoop": "#5d6dce"}      # v1.3 vision layer

TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>pid_graph explorer - __UNIT__</title>
<style>
 body{margin:0;font:13px system-ui,Segoe UI,Arial;background:#fafafa;color:#222;display:flex;height:100vh}
 #side{width:330px;min-width:330px;border-right:1px solid #ddd;background:#fff;overflow:auto;padding:12px;box-sizing:border-box}
 #side.collapsed{display:none}
 #toggle{position:absolute;top:8px;left:8px;z-index:2;padding:3px 8px;background:#fff;border:1px solid #ccc;border-radius:4px;cursor:pointer}
 #main{flex:1;position:relative}
 svg{width:100%;height:100%;display:block;cursor:grab}
 h1{font-size:15px;margin:0 0 8px}
 h2{font-size:12px;margin:14px 0 4px;text-transform:uppercase;letter-spacing:.04em;color:#666}
 .pill{display:inline-flex;align-items:center;gap:5px;margin:2px 4px 2px 0;padding:2px 8px;border-radius:12px;border:1px solid #ccc;cursor:pointer;user-select:none;background:#fff}
 .pill.off{opacity:.35}
 .sw{width:10px;height:10px;border-radius:50%;display:inline-block}
 input[type=text]{width:100%;box-sizing:border-box;padding:6px;border:1px solid #ccc;border-radius:4px}
 #props{font-family:Consolas,monospace;font-size:12px;white-space:pre-wrap;background:#f4f4f4;padding:8px;border-radius:4px;max-height:40vh;overflow:auto}
 #doclink{margin-top:6px;font-size:12px}
 #docs div{padding:3px 0;border-bottom:1px solid #eee;font-size:12px}
 #docs .t{display:inline-block;min-width:34px;font-size:10px;color:#fff;background:#888;border-radius:3px;padding:0 4px;text-align:center;margin-right:4px}
 #docs a,#doclink a{color:#1a5fb4}
 .edge{stroke:#999;stroke-width:1.4;fill:none;marker-end:url(#arrow)}
 .edge.dim,.node.dim,.elabel.dim{opacity:.08}
 .edge.hi{stroke:#e74c3c;stroke-width:2.4}
 .hit{stroke:transparent;stroke-width:14;fill:none;cursor:pointer;pointer-events:stroke}
 .elabel{font-size:9px;fill:#777;pointer-events:none}
 .node circle{stroke:#fff;stroke-width:1.5;cursor:pointer}
 .node.stub circle{stroke-dasharray:3 2;stroke:#333;fill-opacity:.55}
 .node text{font-size:11px;pointer-events:none;paint-order:stroke;stroke:#fff;stroke-width:3px;fill:#111}
 .node.sel circle{stroke:#e74c3c;stroke-width:3}
 .node.oos circle{stroke:#e74c3c;stroke-width:3.5;stroke-dasharray:none}
 .node.oos text.badge{font-size:9px;fill:#e74c3c;font-weight:700;stroke:none}
 #oos div{padding:3px 0;border-bottom:1px solid #eee;font-size:12px;cursor:pointer}
 #oos .k{display:inline-block;min-width:44px;font-size:10px;color:#fff;background:#e74c3c;border-radius:3px;padding:0 4px;text-align:center;margin-right:4px}
 #oos .exp{color:#b00020;font-weight:600}
 #hint{position:absolute;bottom:8px;left:12px;color:#888;font-size:11px}
 button{padding:4px 8px;margin-right:4px}
 #report{position:fixed;inset:0;background:#fff;overflow:auto;z-index:10}
 #reportbar{position:sticky;top:0;background:#eee;padding:8px 16px;border-bottom:1px solid #ccc}
 #reportbody{max-width:900px;margin:0 auto;padding:24px 32px 60px;font-size:13px;line-height:1.45}
 #reportbody h1{font-size:20px;margin:0 0 4px}#reportbody h2{font-size:15px;margin:22px 0 6px;border-bottom:1px solid #ddd;padding-bottom:3px;text-transform:none;letter-spacing:0;color:#222}#reportbody h3{font-size:13px;margin:14px 0 4px}
 #reportbody table{border-collapse:collapse;width:100%;margin:6px 0 10px}#reportbody th,#reportbody td{border:1px solid #ccc;padding:4px 6px;text-align:left;vertical-align:top;font-size:12px}#reportbody th{background:#f0f0f0}
 .bad{color:#b00020;font-weight:600}.ok{color:#1b7a3e;font-weight:600}.muted{color:#777}
 @media print{#side,#main,#reportbar{display:none!important}#report{position:static;overflow:visible}body{display:block}}
</style></head><body>
<div id="side">
 <h1>pid_graph explorer - __UNIT__</h1>
 <div style="color:#666">__NODES__ nodes, __EDGES__ relationships, ontology v1.3, load __LOADRUN__</div>
 <div style="color:#888;margin-top:4px">SHOWN_ON (provenance) relationships start hidden; click its pill or the Documents preset to see them.</div>
 <h2>Find</h2><input id="q" type="text" placeholder="tag, alarm id, SIF id, drawing... (Enter to select)">
 <h2>Labels</h2><div id="labels"></div>
 <h2>Relationships</h2><div id="rels"></div>
 <h2>Presets</h2>
 <div><button data-p="all">Everything</button><button data-p="sis">Safety layer</button><button data-p="flow">Process flow</button><button data-p="docs">Documents</button><button data-p="stubs">Stubs only</button></div>
 <h2>Out of service now</h2><div id="oos"></div>
 <h2>Selected</h2><div id="props">Click a node or a relationship.</div><div id="doclink"></div>
 <h2>Source documents</h2><div id="docs"></div>
 <h2>Routine assessments (for the selected node)</h2>
 <div><button id="btnBypass" disabled title="select an instrument">Bypass assessment</button><button id="btnMOS" disabled title="select a SIF initiator">MOS assessment</button></div>
 <div style="margin-top:4px"><button id="btnShelve" disabled title="select an alarm">Alarm shelving impact</button></div>
 <div style="margin-top:4px"><button id="btnMOC" disabled title="select any node">MOC impact analysis</button>
   <label style="font-size:11px;color:#666">hops <select id="mocHops"><option>1</option><option>2</option><option selected>3</option><option>4</option><option>5</option></select></label></div>
 <div style="margin-top:4px"><input id="mocRef" type="text" placeholder="MOC reference / title (optional)" style="width:100%"></div>
 <div style="margin-top:4px"><button id="btnTrip" disabled title="select a SIF">Trip investigation pack</button><button id="btnDesign" disabled title="select a SIF">SIF design basis (SRS + LOPA)</button></div>
 <h2>Unit reports</h2>
 <div><button id="btnHandover">Shift handover protection status</button></div>
 <div style="margin-top:4px"><button id="btnRegister">Compensating measures register</button></div>
 <div style="color:#888;margin-top:4px">Each opens a printable page: use the browser's Print, then Save as PDF. Bypass, MOS and shelving are the same question - what protection is lost, what remains, what compensates.</div>
</div>
<div id="report" hidden><div id="reportbar"><button id="rClose">back to graph</button><button id="rPrint">print / save as PDF</button></div><div id="reportbody"></div></div>
<div id="main"><button id="toggle" title="show / hide the panel">panel</button><svg id="svg"><defs><marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#999"/></marker></defs><g id="view"></g></svg>
<div id="hint">drag nodes to arrange - wheel to zoom - drag background to pan - click a node or a relationship for its properties - dashed = stub (referenced, not yet loaded)</div></div>
<script>
const DATA = __DATA__;
const COLORS = __COLORS__;
const svg = document.getElementById('svg'), view = document.getElementById('view');
const N = DATA.nodes, E = DATA.edges;
const byId = {}; N.forEach(n => byId[n.id] = n);
const labels = [...new Set(N.map(n => n.label))], rels = [...new Set(E.map(e => e.type))];
const on = {label: Object.fromEntries(labels.map(l => [l, true])), rel: Object.fromEntries(rels.map(r => [r, r !== 'SHOWN_ON']))};
document.getElementById('toggle').onclick = () => { const s = document.getElementById('side'); s.classList.toggle('collapsed'); setTimeout(render, 50); };
let W = svg.clientWidth, H = svg.clientHeight, tx = 0, ty = 0, k = 1, sel = null;
N.forEach((n, i) => { const a = i / N.length * Math.PI * 2, r = Math.min(W, H) * 0.35; n.x = W / 2 + r * Math.cos(a); n.y = H / 2 + r * Math.sin(a); n.vx = 0; n.vy = 0; });
function visibleNode(n) { return on.label[n.label] && (!presetStubs || n.stub); }
function visibleEdge(e) { return on.rel[e.type] && visibleNode(byId[e.s]) && visibleNode(byId[e.t]); }
let presetStubs = false;
// ---- pills ----
function pills(host, items, kind) {
  host.innerHTML = '';
  items.forEach(it => { const d = document.createElement('span'); d.className = 'pill'; d.dataset.k = it;
    d.innerHTML = (kind === 'label' ? `<span class="sw" style="background:${COLORS[it] || '#888'}"></span>` : '') + it + ` <span style="color:#999">${kind === 'label' ? N.filter(n => n.label === it).length : E.filter(e => e.type === it).length}</span>`;
    d.onclick = () => { on[kind][it] = !on[kind][it]; d.classList.toggle('off', !on[kind][it]); render(); }; host.appendChild(d); });
}
pills(document.getElementById('labels'), labels, 'label'); pills(document.getElementById('rels'), rels, 'rel');
function syncPills() { document.querySelectorAll('#labels .pill').forEach(p => p.classList.toggle('off', !on.label[p.dataset.k])); document.querySelectorAll('#rels .pill').forEach(p => p.classList.toggle('off', !on.rel[p.dataset.k])); }
document.querySelectorAll('button[data-p]').forEach(b => b.onclick = () => {
  const p = b.dataset.p; presetStubs = p === 'stubs';
  labels.forEach(l => on.label[l] = true); rels.forEach(r => on.rel[r] = true);
  if (p === 'sis') { on.label.Document = false; on.label.Line = false; ['SHOWN_ON', 'FEEDS', 'MEASURES', 'INSTALLED_ON'].forEach(r => on.rel[r] = false); }
  if (p === 'flow') { labels.forEach(l => on.label[l] = ['Line', 'Equipment', 'Instrument', 'Segment', 'InlineItem'].includes(l)); rels.forEach(r => on.rel[r] = ['FEEDS', 'INSTALLED_ON', 'MEASURES', 'FLOWS_TO', 'SEGMENT_OF'].includes(r)); }
  if (p === 'docs') { rels.forEach(r => on.rel[r] = r === 'SHOWN_ON'); }
  syncPills(); render(); });
// ---- drawing ----
const edgeEls = [], hitEls = [], labelEls = [], nodeEls = [];
E.forEach((e, i) => { const p = document.createElementNS('http://www.w3.org/2000/svg', 'path'); p.setAttribute('class', 'edge'); view.appendChild(p); edgeEls.push(p);
  const h = document.createElementNS('http://www.w3.org/2000/svg', 'path'); h.setAttribute('class', 'hit'); h.addEventListener('click', ev => { ev.stopPropagation(); select(e, 'edge'); }); view.appendChild(h); hitEls.push(h);
  const t = document.createElementNS('http://www.w3.org/2000/svg', 'text'); t.setAttribute('class', 'elabel'); t.textContent = e.type; view.appendChild(t); labelEls.push(t); });
N.forEach(n => { const g = document.createElementNS('http://www.w3.org/2000/svg', 'g'); g.setAttribute('class', 'node' + (n.stub ? ' stub' : '') + (n.props.oos_id ? ' oos' : ''));
  const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle'); c.setAttribute('r', n.label === 'SIF' ? 14 : n.label === 'Document' ? 12 : 10); c.setAttribute('fill', COLORS[n.label] || '#888');
  const t = document.createElementNS('http://www.w3.org/2000/svg', 'text'); t.setAttribute('dy', 24); t.setAttribute('text-anchor', 'middle'); t.textContent = n.caption;
  g.appendChild(c); g.appendChild(t);
  if (n.props.oos_id) { const b = document.createElementNS('http://www.w3.org/2000/svg', 'text'); b.setAttribute('class', 'badge'); b.setAttribute('dy', 35); b.setAttribute('text-anchor', 'middle'); b.textContent = ({bypass: 'BYPASSED', mos: 'MOS', shelve: 'SHELVED', interlock_bypass: 'INTERLOCK BYPASS'})[n.props.oos_kind] || 'OUT'; g.appendChild(b); }
  view.appendChild(g); nodeEls.push(g);
  let drag = false; g.addEventListener('mousedown', ev => { drag = true; n.fixed = true; ev.stopPropagation(); const mv = e2 => { n.x = (e2.clientX - svg.getBoundingClientRect().left - tx) / k; n.y = (e2.clientY - svg.getBoundingClientRect().top - ty) / k; alpha = Math.max(alpha, .3); }; const up = () => { drag = false; window.removeEventListener('mousemove', mv); window.removeEventListener('mouseup', up); }; window.addEventListener('mousemove', mv); window.addEventListener('mouseup', up); });
  g.addEventListener('click', ev => { ev.stopPropagation(); select(n, 'node'); }); });
// ---- source documents ----
const DOCS = DATA.documents || [];
const docByKey = {}; DOCS.forEach(d => { docByKey[d.doc_no + '|' + d.rev] = d; if (d.kind === 'extraction') docByKey[d.file] = d; });
const TYPE_COLORS = {PID: '#2e8b57', CE: '#c0392b', IDX: '#2f7fb8', CUR: '#8e44ad', SRS: '#b8672f', LOPA: '#16a085', EXTRACTION: '#6b6b6b'};
function docLink(d, text) { if (!d) return ''; return d.href ? `<a href="${d.href}" target="_blank" title="${d.file}${d.pages ? ' page ' + d.pages[0] : ''}">${text || 'open'}</a>` : `<span class="muted" title="file not found under data/">${text || 'file not available'}</span>`; }
(function () { const host = document.getElementById('docs'); DOCS.forEach(d => { const row = document.createElement('div');
  row.innerHTML = `<span class="t" style="background:${TYPE_COLORS[d.doc_type] || '#888'}">${d.doc_type}</span><b>${d.doc_no}</b>${d.rev ? ' rev ' + d.rev : ''}${d.transmittal ? ' <span class="muted">' + d.transmittal + '</span>' : ''}<br><span class="muted">${d.title || ''}</span> ${docLink(d, d.pages ? 'open page ' + d.pages[0] : 'open')}`;
  host.appendChild(row); }); })();
function sourceLinks(props) { const d = docByKey[(props.source_doc || '') + '|' + (props.source_rev || '')]; const x = props.source_file ? docByKey[props.source_file] : null;
  const parts = []; if (d) parts.push('source: ' + docLink(d, d.doc_no + ' rev ' + d.rev + (d.pages ? ' (page ' + d.pages[0] + ')' : '')));
  if (x) parts.push('extraction: ' + docLink(x, x.file)); if (props.source_ref) parts.push('<span class="muted">' + props.source_ref + '</span>'); return parts.join(' &middot; '); }
function select(obj, kind) { sel = {obj, kind}; const P = document.getElementById('props');
  const DL = document.getElementById('doclink');
  if (kind === 'node' && obj.label === 'Document') { const d = docByKey[obj.caption.replace(' rev ', '|')]; DL.innerHTML = d ? 'this document: ' + docLink(d, d.file + (d.pages ? ' page ' + d.pages[0] : '')) : ''; }
  else { DL.innerHTML = sourceLinks(obj.props || {}); }
  if (kind === 'node') { const es = E.filter(e => e.s === obj.id || e.t === obj.id).map(e => (e.s === obj.id ? '  -> ' : '  <- ') + e.type + ' ' + (e.s === obj.id ? byId[e.t].caption : byId[e.s].caption) + '   [' + (e.props.source_doc || '') + ' / ' + (e.props.extracted_by || '') + ']');
    P.textContent = obj.label + '  ' + obj.caption + (obj.stub ? '   (STUB)' : '') + '\n' + Object.entries(obj.props).map(([a, b]) => a + ': ' + b).join('\n') + '\n\nrelationships (' + es.length + '):\n' + es.join('\n'); }
  else { P.textContent = obj.type + '\n' + byId[obj.s].caption + ' -> ' + byId[obj.t].caption + '\n' + Object.entries(obj.props).map(([a, b]) => a + ': ' + b).join('\n'); }
  render(); }
svg.addEventListener('click', () => { sel = null; document.getElementById('props').textContent = 'Click a node or a relationship.'; document.getElementById('doclink').innerHTML = ''; render(); });
document.getElementById('q').addEventListener('input', render);
document.getElementById('q').addEventListener('keydown', ev => { if (ev.key === 'Enter') { const q = ev.target.value.trim().toUpperCase(); const n = N.find(x => x.caption.toUpperCase() === q) || N.find(x => x.caption.toUpperCase().includes(q)); if (n) { select(n, 'node'); tx = W / 2 - n.x * k; ty = H / 2 - n.y * k; } } });
// pan / zoom
let panning = false, px = 0, py = 0;
svg.addEventListener('mousedown', ev => { panning = true; px = ev.clientX - tx; py = ev.clientY - ty; });
window.addEventListener('mousemove', ev => { if (panning) { tx = ev.clientX - px; ty = ev.clientY - py; } });
window.addEventListener('mouseup', () => panning = false);
svg.addEventListener('wheel', ev => { ev.preventDefault(); const f = ev.deltaY < 0 ? 1.1 : 0.9; const mx = ev.clientX - svg.getBoundingClientRect().left, my = ev.clientY - svg.getBoundingClientRect().top; tx = mx - (mx - tx) * f; ty = my - (my - ty) * f; k *= f; }, {passive: false});
// ---- force layout ----
let alpha = 1;
function tick() {
  const vis = N.filter(visibleNode), ve = E.filter(visibleEdge);
  if (alpha > 0.005) {
    for (const a of vis) { for (const b of vis) { if (a === b) continue; let dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy + 0.01, d = Math.sqrt(d2); const f = 2600 / d2; a.vx += dx / d * f * alpha; a.vy += dy / d * f * alpha; } }
    for (const e of ve) { const a = byId[e.s], b = byId[e.t]; let dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) + 0.01; const f = (d - 110) * 0.02 * alpha; a.vx += dx / d * f; a.vy += dy / d * f; b.vx -= dx / d * f; b.vy -= dy / d * f; }
    for (const n of vis) { n.vx += (W / 2 - n.x) * 0.002 * alpha; n.vy += (H / 2 - n.y) * 0.002 * alpha; if (!n.fixed) { n.x += n.vx; n.y += n.vy; } n.vx *= 0.6; n.vy *= 0.6; }
    alpha *= 0.985;
  }
  render(); requestAnimationFrame(tick);
}
function render() {
  W = svg.clientWidth; H = svg.clientHeight; view.setAttribute('transform', `translate(${tx},${ty}) scale(${k})`);
  const q = document.getElementById('q').value.trim().toUpperCase();
  const selId = sel && sel.kind === 'node' ? sel.obj.id : null;
  const neigh = new Set(); if (selId !== null) E.forEach(e => { if (e.s === selId) neigh.add(e.t); if (e.t === selId) neigh.add(e.s); });
  E.forEach((e, i) => { const p = edgeEls[i], h = hitEls[i], t = labelEls[i]; const v = visibleEdge(e); p.style.display = h.style.display = t.style.display = v ? '' : 'none'; if (!v) return;
    const a = byId[e.s], b = byId[e.t]; const dx = b.x - a.x, dy = b.y - a.y, d = Math.sqrt(dx * dx + dy * dy) || 1, rb = 11; const x2 = b.x - dx / d * rb, y2 = b.y - dy / d * rb;
    const dd = `M${a.x},${a.y} L${x2},${y2}`; p.setAttribute('d', dd); h.setAttribute('d', dd); t.setAttribute('x', (a.x + b.x) / 2); t.setAttribute('y', (a.y + b.y) / 2 - 3);
    const touching = selId !== null && (e.s === selId || e.t === selId); const isSel = sel && sel.kind === 'edge' && sel.obj === e;
    p.classList.toggle('hi', touching || isSel); const dim = (selId !== null && !touching) || (q && !(a.caption.toUpperCase().includes(q) || b.caption.toUpperCase().includes(q))); p.classList.toggle('dim', dim); t.classList.toggle('dim', dim); });
  N.forEach((n, i) => { const g = nodeEls[i]; const v = visibleNode(n); g.style.display = v ? '' : 'none'; if (!v) return; g.setAttribute('transform', `translate(${n.x},${n.y})`);
    g.classList.toggle('sel', n.id === selId); g.classList.toggle('dim', (selId !== null && n.id !== selId && !neigh.has(n.id)) || (q && !n.caption.toUpperCase().includes(q))); });
}
tick();
// ---- reports (built from the embedded data; same logic as pid_graph/report.py) ----
const esc = s => String(s ?? '').replace(/[&<>]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]));
const outE = (id, t) => E.filter(e => e.s === id && e.type === t), inE = (id, t) => E.filter(e => e.t === id && e.type === t);
const cap = id => byId[id].caption;
const needed = v => { const m = /(\d+)\s*oo\s*(\d+)/i.exec(v || ''); return m ? +m[1] : 1; };
const tbl = (hdr, rows) => `<table><tr>${hdr.map(h => `<th>${esc(h)}</th>`).join('')}</tr>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</table>`;
const today = () => new Date().toISOString().slice(0, 10);
const docsLine = () => N.filter(n => n.label === 'Document').map(n => `${esc(n.caption)} (${esc(n.props.doc_type)})`).join(', ');
function sifInfo(sid) {
  const s = byId[sid];
  const inits = inE(sid, 'INITIATES').map(e => ({tag: cap(e.s), n: byId[e.s], p: e.props}));
  const fes = outE(sid, 'ACTUATES').map(e => ({tag: cap(e.t), n: byId[e.t], p: e.props}));
  const prot = outE(sid, 'PROTECTS').map(e => cap(e.t));
  const raises = outE(sid, 'RAISES').map(e => ({alarm: cap(e.t), stub: byId[e.t].stub}));
  const cms = inE(sid, 'COMPENSATES_FOR').map(e => { const a = byId[e.s]; const src = inE(e.s, 'GENERATES')[0]; return {alarm: a.caption, a, src: src ? byId[src.s] : null, p: e.props}; }).sort((x, y) => (x.p.rank || 99) - (y.p.rank || 99));
  return {s, inits, fes, prot, raises, cms};
}
// ---- live out-of-service register (node properties oos_*) ----
const OOS = N.filter(n => n.props.oos_id);
const outSet = new Set(OOS.map(n => n.id));
const hoursTo = s => { const d = new Date((s || '').replace(' ', 'T')); return isNaN(d) ? null : (d - Date.now()) / 36e5; };
const kindWord = k => ({bypass: 'bypass', mos: 'MOS', shelve: 'shelved', interlock_bypass: 'interlock bypass'})[k] || k;
(function () { const host = document.getElementById('oos'); if (!OOS.length) { host.innerHTML = '<div class="muted">nothing recorded in the register</div>'; return; }
  OOS.sort((a, b) => (a.props.oos_expiry || '').localeCompare(b.props.oos_expiry || '')).forEach(n => { const h = hoursTo(n.props.oos_expiry); const row = document.createElement('div');
    row.innerHTML = `<span class="k">${esc(kindWord(n.props.oos_kind))}</span><b>${esc(n.caption)}</b> <span class="muted">${esc(n.props.oos_id)}</span><br><span class="${h !== null && h < 0 ? 'exp' : (h !== null && h <= 24 ? 'exp' : 'muted')}">${h === null ? 'no expiry' : h < 0 ? 'EXPIRED ' + esc(n.props.oos_expiry) : 'expires ' + esc(n.props.oos_expiry) + ' (' + h.toFixed(1) + ' h)'}</span>${n.props.oos_cm_confirmed ? '' : ' <span class="bad">CM not confirmed</span>'}`;
    row.onclick = () => { select(n, 'node'); tx = W / 2 - n.x * k; ty = H / 2 - n.y * k; }; host.appendChild(row); }); })();
function cmBlock(cms, extraOut) {
  // extraOut: ids of elements out of service for this assessment (the register plus the new request)
  const out = extraOut || outSet;
  if (!cms.length) return `<p class="bad">No curated compensating measure for this SIF. A measure or an alternative safeguard must be defined before the bypass is authorised.</p>`;
  return `<p>Curated compensating measures (engineering judgement):</p><ul>` + cms.map(m => {
    let v = '<span class="ok">valid</span>';
    if (m.a.props.oos_id) v = `<span class="bad">INVALID NOW: this alarm is shelved (${esc(m.a.props.oos_id)})</span>`;
    else if (m.src && out.has(m.src.id)) v = `<span class="bad">INVALID NOW: generated by ${esc(m.src.caption)}, which is out of service</span>`;
    return `<li><b>${m.p.rank || '-'}. ${esc(m.alarm)}</b> (${esc(m.p.basis)}) ${v}<br>` +
      `<span class="muted">Source ${esc(m.src ? m.src.caption : '?')} (${esc(m.src ? m.src.props.system : '?')}), setpoint ${esc(m.a.props.setpoint)}, priority ${esc(m.a.props.priority)}. Conditions: ${esc(m.p.conditions || '-')}. Curated by ${esc(m.p.curated_by)} ${esc(m.p.curated_on || '')}.</span></li>`; }).join('') + `</ul>`;
}
function srsBypassLine(s) { return s.props.bypass_conditions ? `<p><b>SRS bypass conditions for ${esc(s.caption)}:</b> ${esc(s.props.bypass_conditions)} <span class="muted">(SRS ${esc(s.props.srs_ref || '')})</span></p>` : ''; }
function alreadyOutBlock(exclude) {
  const others = OOS.filter(n => n.id !== exclude);
  if (!others.length) return `<p class="muted">Nothing else is recorded as out of service; this assessment considers the request alone.</p>`;
  return `<p><b>Already out of service (register), included in this assessment:</b></p>` + tbl(['Element', 'Kind', 'Ref', 'Expiry', 'Authorised by', 'CM confirmed'], others.map(n => [esc(n.caption), esc(kindWord(n.props.oos_kind)), esc(n.props.oos_id), esc(n.props.oos_expiry || ''), esc(n.props.oos_authorised_by || ''), n.props.oos_cm_confirmed ? 'yes' : '<span class="bad">NO</span>']));
}
function bypassReport(n, mode) {
  mode = mode || 'Bypass';
  const out = new Set([...outSet, n.id]);
  const asInit = outE(n.id, 'INITIATES').map(e => ({sif: e.t, voting: e.props.voting, sp: e.props.setpoint, src: e.props.source_doc}));
  const asFE = inE(n.id, 'ACTUATES').map(e => ({sif: e.s, action: e.props.action}));
  let worst = 'UNAFFECTED'; const secs = [];
  for (const r of asInit) { const i = sifInfo(r.sif); const grp = i.inits.filter(x => (x.p.voting || '') === (r.voting || '')); const rem = grp.filter(x => !out.has(x.n.id)).map(x => x.tag); const alsoOut = grp.filter(x => out.has(x.n.id) && x.n.id !== n.id).map(x => x.tag); const need = needed(r.voting);
    const remFE = i.fes.filter(x => !out.has(x.n.id)).map(x => x.tag + ' ' + (x.p.action || ''));
    const st = rem.length >= need && (remFE.length || !i.fes.length) ? 'DEGRADED' : 'DEFEATED - CANNOT TRIP'; worst = st.startsWith('DEFEATED') ? 'DEFEATED' : (worst === 'DEFEATED' ? worst : 'DEGRADED');
    secs.push(`<h2>${esc(i.s.caption)} - <span class="${st.startsWith('DEFEATED') ? 'bad' : 'ok'}">${st}</span></h2><p>${esc(i.s.props.description)} (SIL ${esc(i.s.props.sil)}). ${esc(n.caption)} is an initiator, voting ${esc(r.voting || '1oo1')} @ ${esc(r.sp || '?')} (${esc(r.src)}).<br>Remaining initiators: ${esc(rem.join(', ') || 'NONE')} (needs ${need})${alsoOut.length ? ' - <span class="bad">' + esc(alsoOut.join(', ')) + ' already out (register)</span>' : ''}. Final elements in service: ${esc(remFE.join(', ') || 'NONE')}. Protects: ${esc(i.prot.join(', ') || '?')}.</p>` + srsBypassLine(i.s) + cmBlock(i.cms, out)); }
  for (const r of asFE) { const i = sifInfo(r.sif); const rem = i.fes.filter(x => !out.has(x.n.id)).map(x => x.tag + ' ' + (x.p.action || '')); const alsoOut = i.fes.filter(x => out.has(x.n.id) && x.n.id !== n.id).map(x => x.tag);
    const initOk = [...new Set(i.inits.map(x => x.p.voting || ''))].every(v => i.inits.filter(x => (x.p.voting || '') === v && !out.has(x.n.id)).length >= needed(v));
    const st = rem.length && initOk ? 'DEGRADED' : (rem.length ? 'DEFEATED - CANNOT TRIP (initiators out)' : 'DEFEATED - NO FINAL ELEMENT LEFT'); worst = st.startsWith('DEFEATED') ? 'DEFEATED' : (worst === 'DEFEATED' ? worst : 'DEGRADED');
    secs.push(`<h2>${esc(i.s.caption)} - <span class="${st.startsWith('DEFEATED') ? 'bad' : 'ok'}">${st}</span></h2><p>${esc(i.s.props.description)} (SIL ${esc(i.s.props.sil)}). ${esc(n.caption)} is a final element (${esc(r.action || '')}).<br>Remaining final elements: ${esc(rem.join(', ') || 'NONE')}${alsoOut.length ? ' - <span class="bad">' + esc(alsoOut.join(', ')) + ' already out (register)</span>' : ''}. Protects: ${esc(i.prot.join(', ') || '?')}.</p>` + srsBypassLine(i.s) + cmBlock(i.cms, out)); }
  const own = outE(n.id, 'GENERATES').map(e => byId[e.t]);
  const actions = ['Confirm the bypass is authorised at the level the site bypass procedure requires and logged in the bypass register.', 'Brief the panel operator: which SIF(s) are degraded or defeated, which compensating alarms or readings to watch, and the manual response.', 'Confirm the compensating alarms are not shelved or suppressed and are at the required priority.', 'Define the field round interval for any manual-only measure and record readings.', 'Limit the bypass to the authorised duration; extend only by re-assessment.', 'On removal: restore the SIF, confirm no forces or overrides remain, proof test where required, close the register entry.'];
  if (worst === 'DEFEATED') actions.unshift('A SIF is DEFEATED while this element is out of service: obtain the higher authorisation level your procedure requires and confirm the process can stay within its operating envelope with the measures listed, or bring it to a safe state.');
  const title = mode === 'MOS' ? `Maintenance Override (MOS) Assessment - ${esc(n.caption)}` : `SIS Bypass Assessment - ${esc(n.caption)}`;
  const intro = mode === 'MOS' ? `<p>A maintenance override switch applied to ${esc(n.caption)} removes it as an initiator at the logic solver input: the SIF sees the channel as healthy and cannot trip on it. The assessment below is the initiator-side view of the out-of-service question.</p>` : '';
  return `<h1>${title}</h1><p class="muted">${esc(n.props.service || '')} | generated ${today()} from the pid_graph knowledge graph (load ${esc(n.props.load_run)}) | DRAFT - requires authorisation per the site ${mode === 'MOS' ? 'override' : 'bypass'} procedure</p>` + intro +
    (n.props.oos_id ? `<p class="bad">${esc(n.caption)} is ALREADY out of service: ${esc(kindWord(n.props.oos_kind))} ${esc(n.props.oos_id)} until ${esc(n.props.oos_expiry)}.</p>` : '') +
    `<p><b>Summary:</b> ${asInit.length + asFE.length} SIF(s) affected; worst case <span class="${worst === 'DEFEATED' ? 'bad' : 'ok'}">${worst}</span> (combined with everything in the register).</p>` + alreadyOutBlock(n.id) + (secs.join('') || '<p>No SIF uses this element.</p>') +
    (own.length ? `<h2>Alarms lost with the element</h2><ul>${own.map(a => `<li>${esc(a.caption)} @ ${esc(a.props.setpoint)} (${esc(a.props.priority)})</li>`).join('')}</ul>` : '') +
    `<h2>Required actions</h2><ol>${actions.map(a => `<li>${esc(a)}</li>`).join('')}</ol><p class="muted"><i>IEC 61511-1 clause 11 (design) and clause 16 (operation and maintenance) require compensating measures while a SIF is bypassed, authorisation, time limits and operator awareness. Confirm sub-clause references against the edition in force on the project.</i></p><p class="muted">Sources: ${docsLine()}</p>`;
}
function registerReport() {
  const sifs = N.filter(n => n.label === 'SIF' && !n.stub).sort((a, b) => a.caption.localeCompare(b.caption));
  let h = `<h1>Compensating Measures Register - ${esc(DATA.unit || '')}</h1><p class="muted">Generated ${today()} from the pid_graph knowledge graph. Compensating measures are engineering judgement (curated register), never inferred. Every fact carries its source document and revision.</p>`;
  h += `<h2>Source documents</h2>` + tbl(['Document', 'Rev', 'Type', 'Title', 'Transmittal', 'File'], DOCS.map(d => [esc(d.doc_no), esc(d.rev), esc(d.doc_type), esc(d.title || ''), esc(d.transmittal || ''), docLink(d, esc(d.file) + (d.pages ? ' p.' + d.pages[0] : ''))]));
  h += `<h2>Summary</h2>` + tbl(['SIF', 'SIL', 'Function', 'Initiators', 'Final elements', 'Curated compensating alarms'], sifs.map(s => { const i = sifInfo(s.id); return [esc(s.caption), esc(s.props.sil), esc(s.props.description), esc(i.inits.map(x => x.tag).join(', ')), esc(i.fes.map(f => f.tag + ' ' + (f.p.action || '')).join(', ')), i.cms.length ? esc(i.cms.map(m => m.alarm).join(', ')) : '<span class="bad">NONE - see gap</span>']; }));
  for (const s of sifs) { const i = sifInfo(s.id);
    h += `<h2>${esc(s.caption)} - ${esc(s.props.description)}</h2><p class="muted">SIL ${esc(s.props.sil)} | logic solver ${esc(s.props.logic_solver || '?')} | protects ${esc(i.prot.join(', ') || '?')} | source ${esc(s.props.source_doc)} rev ${esc(s.props.source_rev)}</p><h3>Trip function</h3>`;
    h += tbl(['Initiator', 'Service', 'System', 'Voting', 'Setpoint', 'Measures', 'Cause'], i.inits.map(x => [esc(x.tag) + (x.n.stub ? ' <span class="bad">(NOT IN INDEX)</span>' : ''), esc(x.n.props.service || ''), esc(x.n.props.system || ''), esc(x.p.voting || ''), esc(x.p.setpoint || ''), esc(outE(x.n.id, 'MEASURES').map(e => cap(e.t)).join(', ') || '?'), esc(x.p.cause_description || '')]));
    const votes = [...new Set(i.inits.map(x => x.p.voting).filter(Boolean))];
    for (const v of votes) { const m = /(\d+)\s*oo\s*(\d+)/i.exec(v); const listed = i.inits.filter(x => x.p.voting === v).length; if (m && +m[2] !== listed) h += `<p class="bad">Voting mismatch: ${esc(v)} implies ${m[2]} initiators; the C&amp;E lists ${listed} (register X10).</p>`; }
    h += tbl(['Final element', 'Action', 'Service'], i.fes.map(f => [esc(f.tag), esc(f.p.action || ''), esc(f.n.props.service || '')]));
    if (i.raises.length) h += `<p>Trip announced by: ${i.raises.map(r => esc(r.alarm) + (r.stub ? ' <span class="bad">(not in alarm register)</span>' : '')).join(', ')}</p>`;
    h += `<h3>Design basis (SRS)</h3>` + srsBlock(s) + `<h3>LOPA scenarios crediting this SIF</h3>` + lopaBlock(s);
    h += `<h3>Compensating measures (curated)</h3>`;
    if (i.cms.length) for (const m of i.cms) h += `<p><b>${m.p.rank || '-'}. ${esc(m.alarm)}</b> (${esc(m.a.props.alarm_tag || '')}) - ${esc(m.a.props.description || '')}</p><ul><li>Source: ${esc(m.src ? m.src.caption : '?')} (${esc(m.src ? m.src.props.system : '?')}), setpoint ${esc(m.a.props.setpoint || '?')}, priority ${esc(m.a.props.priority || '?')}</li><li>Basis: ${esc(m.p.basis)}</li><li>Conditions: ${esc(m.p.conditions || '-')}</li><li>Rationale: ${esc(m.p.rationale || '-')}</li><li>Curated by ${esc(m.p.curated_by)} on ${esc(m.p.curated_on || '?')} (${esc(m.p.source_doc)} rev ${esc(m.p.source_rev)})</li></ul>`;
    else h += `<p class="bad">NONE CURATED.</p><p class="muted">Check the exception register (X14) for the recorded gap rationale.</p>`;
  }
  return h;
}
// ---- alarm shelving impact (CQ4) ----
const IMPACT_RELS = new Set(['MEASURES', 'INSTALLED_ON', 'FEEDS', 'INITIATES', 'ACTUATES', 'PROTECTS', 'GENERATES', 'RAISES', 'CASCADES_TO']);
function neighboursVia(id, types) { const out = []; E.forEach(e => { if (!types.has(e.type)) return; if (e.s === id) out.push({id: e.t, e}); else if (e.t === id) out.push({id: e.s, e}); }); return out; }
function within(startIds, hops, types) { const dist = {}; let frontier = []; startIds.forEach(i => { dist[i] = 0; frontier.push(i); });
  for (let h = 1; h <= hops; h++) { const next = []; for (const id of frontier) for (const nb of neighboursVia(id, types)) if (!(nb.id in dist)) { dist[nb.id] = h; next.push(nb.id); } frontier = next; } return dist; }
function shelveReport(a) {
  const src = inE(a.id, 'GENERATES').map(e => byId[e.s])[0];
  const measures = src ? outE(src.id, 'MEASURES').map(e => byId[e.t]) : [];
  const sifsOnSensor = src ? outE(src.id, 'INITIATES').map(e => byId[e.t]) : [];
  const compFor = outE(a.id, 'COMPENSATES_FOR').map(e => ({s: byId[e.t], p: e.props}));
  const announces = inE(a.id, 'RAISES').map(e => byId[e.s]);
  const states = outE(a.id, 'VALID_IN').map(e => byId[e.t]);
  const near = within(measures.map(m => m.id), 2, new Set(['FEEDS']));
  const variable = src ? (src.props.type || '')[0] : '';
  const cover = [];
  Object.keys(near).forEach(locId => { inE(+locId, 'MEASURES').forEach(e => { const o = byId[e.s]; if (!src || o.id === src.id || (o.props.type || '')[0] !== variable || o.stub) return;
    const al = outE(o.id, 'GENERATES').map(x => byId[x.t]); const sifs = outE(o.id, 'INITIATES').map(x => cap(x.t));
    cover.push({o, at: cap(+locId), rel: near[locId] === 0 ? 'same location' : `within ${near[locId]} process hop(s)`, al, sifs}); }); });
  const risk = compFor.length ? 'HIGH - this alarm is a curated compensating measure' : (cover.some(c => c.al.length) ? 'MEDIUM - other alarms cover the variable' : 'REVIEW - no other alarm on this variable nearby');
  let h = `<h1>Alarm Shelving Impact - ${esc(a.caption)}</h1><p class="muted">${esc(a.props.alarm_tag || '')} ${esc(a.props.description || '')} | setpoint ${esc(a.props.setpoint || '?')} | priority ${esc(a.props.priority || '?')} | generated ${today()} from the pid_graph knowledge graph | DRAFT</p>`;
  h += `<p><b>Assessment:</b> <span class="${risk.startsWith('HIGH') ? 'bad' : 'ok'}">${esc(risk)}</span></p>`;
  h += `<h2>Hazard indication lost</h2><p>${esc(a.props.alarm_type || a.caption)} from ${esc(src ? src.caption : '?')} (${esc(src ? src.props.system : '?')}, ${esc(src ? src.props.service : '')}) measuring ${esc(measures.map(m => m.caption).join(', ') || '?')}. While shelved, operations has no annunciation of this condition from this device.</p>`;
  h += `<h2>Does anything still cover the scenario?</h2>`;
  h += sifsOnSensor.length ? `<p>The same sensor initiates <b>${esc(sifsOnSensor.map(s => s.caption).join(', '))}</b>: the SIS still trips at its own setpoint, but the operator loses the pre-alarm that precedes the trip.</p>` : `<p>No SIF uses this sensor; the alarm is the only automatic response from this device.</p>`;
  h += cover.length ? tbl(['Other device', 'System', 'At', 'Relation', 'Its alarms', 'SIFs it initiates'], cover.map(c => [esc(c.o.caption), esc(c.o.props.system || ''), esc(c.at), esc(c.rel), esc(c.al.map(x => x.caption + ' @ ' + (x.props.setpoint || '?')).join(', ') || '-'), esc(c.sifs.join(', ') || '-')])) : `<p class="bad">No other device measures the same variable at this location or within two process hops.</p>`;
  if (compFor.length) { h += `<h2 class="bad">This alarm is relied on as a compensating measure</h2><ul>` + compFor.map(c => `<li><b>${esc(c.s.caption)}</b> - ${esc(c.s.props.description)} (rank ${c.p.rank || '-'}, ${esc(c.p.basis)}). Conditions: ${esc(c.p.conditions || '-')}. Curated by ${esc(c.p.curated_by)} ${esc(c.p.curated_on || '')}.<br><span class="bad">Shelving it while that SIF is bypassed or degraded removes the compensating measure. Check the bypass register before shelving.</span></li>`).join('') + `</ul>`; }
  if (announces.length) h += `<h2>Trip announcement</h2><p>This alarm announces the trip of <b>${esc(announces.map(s => s.caption).join(', '))}</b>. Shelved, a trip would not be annunciated through it.</p>`;
  if (states.length) h += `<h2>Valid in states</h2><p>${esc(states.map(s => s.caption).join(', '))}</p>`;
  const actions = ['Record the shelving in the alarm shelving log with reason, duration and authoriser.', 'Confirm the operator knows which indication is lost and what to watch instead (table above).', 'If the alarm is a curated compensating measure, confirm no bypass or degraded SIF currently relies on it, or do not shelve.', 'Set a review time; un-shelve on expiry, not on memory.'];
  h += `<h2>Required actions</h2><ol>${actions.map(x => `<li>${esc(x)}</li>`).join('')}</ol><p class="muted">Sources: ${docsLine()}</p>`;
  return h;
}
// ---- MOC impact analysis (CQ3) ----
function mocReport(n, hops, ref) {
  const dist = within([n.id], hops, IMPACT_RELS);
  const affected = Object.keys(dist).map(id => byId[+id]).filter(x => x.id !== n.id).sort((a, b) => dist[a.id] - dist[b.id] || a.label.localeCompare(b.label) || a.caption.localeCompare(b.caption));
  const byLabel = {}; affected.forEach(x => (byLabel[x.label] = byLabel[x.label] || []).push(x));
  const docsSet = {}; [n, ...affected].forEach(x => outE(x.id, 'SHOWN_ON').forEach(e => { const d = byId[e.t]; (docsSet[d.caption] = docsSet[d.caption] || {d, items: new Set()}).items.add(x.caption); }));
  const sifs = affected.filter(x => x.label === 'SIF');
  let h = `<h1>MOC Impact Analysis - ${esc(n.caption)}</h1><p class="muted">${esc(ref || 'no MOC reference given')} | ${esc(n.label)} ${esc(n.props.service || n.props.description || '')} | ${hops} hop(s) over MEASURES, INSTALLED_ON, FEEDS, INITIATES, ACTUATES, PROTECTS, GENERATES, RAISES, CASCADES_TO | generated ${today()} from the pid_graph knowledge graph | DRAFT</p>`;
  h += `<p><b>Summary:</b> ${affected.length} node(s) within ${hops} hop(s): ${Object.entries(byLabel).map(([l, v]) => `${v.length} ${l}`).join(', ') || 'none'}. ${sifs.length ? `<span class="bad">${sifs.length} SIF(s) affected - functional safety review required.</span>` : 'No SIF within reach.'}</p>`;
  h += `<h2>Affected nodes</h2>` + tbl(['Hops', 'Label', 'Node', 'Description', 'Reached via'], affected.map(x => { const via = neighboursVia(x.id, IMPACT_RELS).filter(nb => dist[nb.id] === dist[x.id] - 1).map(nb => nb.e.type + ' ' + cap(nb.id)).slice(0, 3).join('; '); return [dist[x.id], esc(x.label), esc(x.caption) + (x.stub ? ' <span class="bad">(stub)</span>' : ''), esc(x.props.service || x.props.description || ''), esc(via)]; }));
  if (sifs.length) { h += `<h2>Safety functions affected</h2>`; for (const s of sifs) { const i = sifInfo(s.id); h += `<h3>${esc(s.caption)} - ${esc(s.props.description)} (SIL ${esc(s.props.sil)})</h3><p>Initiators: ${esc(i.inits.map(x => x.tag + ' ' + (x.p.voting || '')).join(', '))}. Final elements: ${esc(i.fes.map(f => f.tag + ' ' + (f.p.action || '')).join(', '))}. Protects: ${esc(i.prot.join(', ') || '?')}. ${dist[s.id]} hop(s) from ${esc(n.caption)}.</p>` + cmBlock(i.cms); } }
  h += `<h2>Documents to re-verify</h2>` + tbl(['Document', 'Type', 'Nodes it shows that are in scope', 'File'], Object.values(docsSet).sort((a, b) => a.d.caption.localeCompare(b.d.caption)).map(x => { const d = docByKey[x.d.caption.replace(' rev ', '|')]; return [esc(x.d.caption), esc(x.d.props.doc_type), esc([...x.items].sort().join(', ')), docLink(d, d ? esc(d.file) + (d.pages ? ' p.' + d.pages[0] : '') : '')]; }));
  const actions = ['Confirm the change scope against the affected-nodes table; any node not listed is not reachable from the change in the graph, which is itself worth knowing.', 'Update the instrument index and P&IDs listed above; re-run the pipeline after each re-issue and compare the register.'];
  if (sifs.length) actions.push('Functional safety review for each SIF above: C&E, SRS, LOPA and SIL verification to be revalidated; re-curate compensating measures if initiators or alarms change.');
  if (byLabel.Alarm) actions.push('Alarm rationalisation review for the alarms listed (setpoint, priority, and any compensating-measure role).');
  h += `<h2>Review actions</h2><ol>${actions.map(x => `<li>${esc(x)}</li>`).join('')}</ol><p class="muted">Sources: ${docsLine()}</p>`;
  return h;
}
// ---- shift handover protection status (combined view of the register) ----
function sifStatusNow(sid) {
  const i = sifInfo(sid); const detail = [];
  let initOk = true, touched = false;
  for (const v of [...new Set(i.inits.map(x => x.p.voting || ''))]) { const grp = i.inits.filter(x => (x.p.voting || '') === v); const rem = grp.filter(x => !outSet.has(x.n.id)); const need = needed(v);
    if (rem.length < grp.length) { touched = true; detail.push(`initiators ${v || '1oo1'}: ${rem.length} of ${grp.length} in service (${rem.map(x => x.tag).join(', ') || 'NONE'}), needs ${need}`); }
    if (rem.length < need) initOk = false; }
  const remFE = i.fes.filter(x => !outSet.has(x.n.id));
  if (remFE.length < i.fes.length) { touched = true; detail.push(`final elements: ${remFE.length} of ${i.fes.length} in service (${remFE.map(x => x.tag).join(', ') || 'NONE'})`); }
  const finalOk = remFE.length > 0 || !i.fes.length;
  const status = !touched ? 'UNAFFECTED' : (initOk && finalOk ? 'DEGRADED' : 'DEFEATED');
  const valid = i.cms.filter(m => !m.a.props.oos_id && !(m.src && outSet.has(m.src.id)));
  const lost = i.cms.filter(m => m.a.props.oos_id || (m.src && outSet.has(m.src.id)));
  const flags = [];
  if (status !== 'UNAFFECTED' && !valid.length) flags.push('NO VALID COMPENSATING MEASURE while ' + status);
  for (const m of lost) if (status !== 'UNAFFECTED') flags.push(`compensating measure ${m.alarm} is ${m.a.props.oos_id ? 'shelved (' + m.a.props.oos_id + ')' : 'from ' + m.src.caption + ', which is out'} while the SIF is ${status}`);
  return {i, status, detail: detail.join('; '), valid, lost, flags};
}
function handoverReport() {
  const sifs = N.filter(n => n.label === 'SIF' && !n.stub).sort((a, b) => a.caption.localeCompare(b.caption)).map(s => ({s, r: sifStatusNow(s.id)}));
  const worst = sifs.some(x => x.r.status === 'DEFEATED') ? 'DEFEATED' : (sifs.some(x => x.r.status === 'DEGRADED') ? 'DEGRADED' : 'ALL SIFs UNAFFECTED');
  let h = `<h1>Shift Handover - Protection Status - ${esc(DATA.unit)}</h1><p class="muted">Generated ${today()} ${new Date().toTimeString().slice(0, 5)} from the pid_graph knowledge graph; register state as of graph generation ${esc(DATA.generated)}. Expiry times are compared with the clock now.</p>`;
  h += `<p><b>Headline:</b> <span class="${worst.startsWith('ALL') ? 'ok' : 'bad'}">${worst}</span>. ${OOS.length} element(s) out of service.</p>`;
  h += `<h2>Out of service now</h2>` + (OOS.length ? tbl(['Ref', 'Kind', 'Element', 'Since', 'Expiry', 'Authorised by', 'Reason', 'CM confirmed'], OOS.map(n => { const hh = hoursTo(n.props.oos_expiry); const ex = hh === null ? esc(n.props.oos_expiry || '-') : (hh < 0 ? `<span class="bad">EXPIRED ${esc(n.props.oos_expiry)}</span>` : (hh <= 24 ? `<span class="bad">${esc(n.props.oos_expiry)} (${hh.toFixed(1)} h)</span>` : esc(n.props.oos_expiry)));
    return [esc(n.props.oos_id), esc(kindWord(n.props.oos_kind)), esc(n.caption), esc(n.props.oos_start || ''), ex, esc(n.props.oos_authorised_by || ''), esc(n.props.oos_reason || ''), n.props.oos_cm_confirmed ? 'yes' : '<span class="bad">NO</span>']; })) : '<p class="ok">Nothing out of service.</p>');
  h += `<h2>Safety functions</h2>` + tbl(['SIF', 'SIL', 'Function', 'Status', 'Detail', 'Valid compensating measures', 'Flags'], sifs.map(({s, r}) => [esc(s.caption), esc(s.props.sil), esc(s.props.description), `<span class="${r.status === 'UNAFFECTED' ? 'ok' : 'bad'}">${r.status}</span>`, esc(r.detail || '-'), esc(r.valid.map(m => m.alarm).join(', ') || (r.status === 'UNAFFECTED' ? '-' : 'NONE')), r.flags.length ? '<span class="bad">' + r.flags.map(esc).join('<br>') + '</span>' : '-']));
  const soon = OOS.filter(n => { const hh = hoursTo(n.props.oos_expiry); return hh !== null && hh <= 24; });
  h += `<h2>Attention this shift</h2><ul>` + (sifs.flatMap(({s, r}) => r.flags.map(f => `<li class="bad">${esc(s.caption)}: ${esc(f)}</li>`)).join('') || '') + soon.map(n => { const hh = hoursTo(n.props.oos_expiry); return `<li>${esc(n.props.oos_id)} ${esc(kindWord(n.props.oos_kind))} ${esc(n.caption)} ${hh < 0 ? '<span class="bad">has EXPIRED</span> - restore or re-authorise' : 'expires in ' + hh.toFixed(1) + ' h - plan restoration or re-assessment'}</li>`; }).join('') + OOS.filter(n => !n.props.oos_cm_confirmed).map(n => `<li class="bad">${esc(n.props.oos_id)} ${esc(n.caption)}: compensating measures not confirmed in the register</li>`).join('') + `</ul>`;
  h += `<p class="muted">Sources: ${docsLine()}; register ${esc((OOS[0] || {props: {}}).props.oos_source || 'out_of_service register')}</p>`;
  return h;
}
// ---- trip investigation pack (CQ6 + CQ9) ----
function tripPack(s) {
  const i = sifInfo(s.id); const r = sifStatusNow(s.id);
  const preAlarms = []; i.inits.forEach(x => outE(x.n.id, 'GENERATES').forEach(e => preAlarms.push({on: x.tag, a: byId[e.t]})));
  const locIds = new Set(); i.inits.forEach(x => outE(x.n.id, 'MEASURES').forEach(e => locIds.add(e.t)));
  const nearby = []; locIds.forEach(l => inE(l, 'MEASURES').forEach(e => { const o = byId[e.s]; if (i.inits.some(x => x.n.id === o.id) || o.stub) return; outE(o.id, 'GENERATES').forEach(g => nearby.push({o, at: cap(l), a: byId[g.t]})); }));
  const cascades = outE(s.id, 'CASCADES_TO').map(e => byId[e.t]); const causedBy = inE(s.id, 'CASCADES_TO').map(e => byId[e.s]);
  const ex = (DATA.exceptions || []).filter(e => e.id === s.caption || i.inits.some(x => e.id === x.tag) || i.fes.some(f => e.id === f.tag) || i.raises.some(a => e.id === a.alarm));
  const stateOf = n => n.props.oos_id ? `<span class="bad">${esc(kindWord(n.props.oos_kind))} ${esc(n.props.oos_id)}</span>` : '<span class="ok">in service</span>';
  let h = `<h1>Trip Investigation Pack - ${esc(s.caption)}</h1><p class="muted">${esc(s.props.description)} | SIL ${esc(s.props.sil)} | logic solver ${esc(s.props.logic_solver || '?')} | protects ${esc(i.prot.join(', ') || '?')} | generated ${today()} from the pid_graph knowledge graph | source ${esc(s.props.source_doc)} rev ${esc(s.props.source_rev)}</p>`;
  h += `<p><b>Protection status at generation:</b> <span class="${r.status === 'UNAFFECTED' ? 'ok' : 'bad'}">${r.status}</span>${r.detail ? ' - ' + esc(r.detail) : ''}. Fill in the event time, the first-out indication and the sequence-of-events record before working through the checklist.</p>`;
  h += `<h2>1. What can cause this trip</h2>` + tbl(['Initiator', 'Service', 'System', 'Voting', 'Trip setpoint', 'Measures', 'Cause', 'State now'], i.inits.map(x => [esc(x.tag) + (x.n.stub ? ' <span class="bad">(NOT IN INDEX)</span>' : ''), esc(x.n.props.service || ''), esc(x.n.props.system || ''), esc(x.p.voting || '1oo1'), esc(x.p.setpoint || '?'), esc(outE(x.n.id, 'MEASURES').map(e => cap(e.t)).join(', ') || '?'), esc(x.p.cause_description || ''), stateOf(x.n)]));
  const votes = [...new Set(i.inits.map(x => x.p.voting).filter(Boolean))]; for (const v of votes) { const m = /(\d+)\s*oo\s*(\d+)/i.exec(v); const listed = i.inits.filter(x => x.p.voting === v).length; if (m) h += `<p>${esc(v)}: the trip needs ${m[1]} of ${m[2]} channels to vote${+m[2] !== listed ? ` - <span class="bad">but the C&amp;E lists ${listed} channels (register X10); confirm the real architecture before concluding which channels voted</span>` : ''}.</p>`; }
  h += `<h2>2. What should have preceded it</h2>` + (preAlarms.length ? tbl(['Pre-alarm', 'On initiator', 'Setpoint', 'Priority', 'State now'], preAlarms.map(p => [esc(p.a.caption), esc(p.on), esc(p.a.props.setpoint || '?'), esc(p.a.props.priority || '?'), stateOf(p.a)])) : '<p class="muted">No alarm is generated by any initiator of this SIF: there was no pre-alarm from the SIS sensors themselves.</p>');
  h += nearby.length ? `<p>Other alarms on the same measured items (should show the process excursion in the alarm journal):</p>` + tbl(['Alarm', 'On device', 'System', 'At', 'Setpoint', 'State now'], nearby.map(x => [esc(x.a.caption), esc(x.o.caption), esc(x.o.props.system || ''), esc(x.at), esc(x.a.props.setpoint || '?'), stateOf(x.a)])) : '';
  h += `<h2>3. What the trip should have done</h2>` + (s.props.safe_state ? `<p>SRS safe state: <b>${esc(s.props.safe_state)}</b>; required response time ${esc(s.props.response_time || '?')} within a process safety time of ${esc(s.props.process_safety_time || '?')}.</p>` : '') + tbl(['Final element', 'Expected action', 'Service', 'State now'], i.fes.map(f => [esc(f.tag), esc(f.p.action || '?'), esc(f.n.props.service || ''), stateOf(f.n)]));
  h += i.raises.length ? `<p>Trip announcement: ${i.raises.map(a => esc(a.alarm) + (a.stub ? ' <span class="bad">(not in alarm register - confirm it exists on the DCS)</span>' : '')).join(', ')} should have annunciated.</p>` : '<p class="muted">No trip-announcing alarm is recorded for this SIF (no RAISES in the C&amp;E).</p>';
  if (cascades.length || causedBy.length) h += `<h2>4. Cascade</h2><p>${cascades.length ? 'This trip initiates: ' + esc(cascades.map(c => c.caption).join(', ')) + '. ' : ''}${causedBy.length ? 'This SIF can be initiated by: ' + esc(causedBy.map(c => c.caption).join(', ')) + ' - check whether the trip was a consequence rather than a cause.' : ''}</p>`;
  const checklist = ['Event time and first-out indication from the sequence-of-events recorder / logic solver diagnostics.', 'Which initiator channel(s) voted? Compare each channel\'s trend against its trip setpoint at the event time.', 'Was any channel overridden, bypassed or in fault at the time? Compare with the out-of-service register (states above are as of generation).', 'Did the process actually reach the trip condition (genuine demand), or was it a spurious trip (sensor, wiring, logic)? Compare SIS channels with the BPCS measurements listed in section 2.', 'Did every final element reach its expected state within its stroke time? Record valve position feedback.', 'Was the trip annunciated to the operator (section 3)? Was the pre-alarm (section 2) acknowledged before the trip?', 'Record the demand in the SIF demand log; a genuine demand feeds the SIL verification demand rate.', 'Before reset: root cause understood, initiators healthy, final elements proven, authorisation per procedure.'];
  h += `<h2>5. Investigation checklist</h2><ol>${checklist.map(c => `<li>${esc(c)}</li>`).join('')}</ol>`;
  h += `<h2>6. Documents</h2>` + tbl(['Document', 'Type', 'File'], DOCS.filter(d => d.kind === 'document').map(d => [esc(d.doc_no + (d.rev ? ' rev ' + d.rev : '')), esc(d.doc_type), docLink(d, esc(d.file) + (d.pages ? ' p.' + d.pages[0] : ''))]));
  if (ex.length) h += `<h2>7. Data caveats (exception register)</h2>` + tbl(['Code', 'Node', 'Detail'], ex.map(e => [esc(e.code), esc(e.id), esc(e.detail)]));
  return h;
}
// ---- SIF design basis: SRS requirements + LOPA scenarios (CQ11-CQ13, v1.2) ----
const SRS_FIELDS = [['sil_srs', 'SIL target'], ['rrf_target', 'RRF target'], ['pfd_target', 'PFDavg target'], ['demand_mode', 'Demand mode'], ['safe_state', 'Safe state'],
  ['process_safety_time', 'Process safety time'], ['response_time', 'SIF response time'], ['setpoint_srs', 'Trip setpoint'], ['sensor_architecture', 'Sensor architecture'],
  ['fe_architecture', 'Final element architecture'], ['proof_test_interval', 'Proof test interval'], ['bypass_conditions', 'Bypass conditions'], ['manual_shutdown', 'Manual shutdown'],
  ['reset', 'Reset'], ['logic_solver_srs', 'Logic solver'], ['hazard', 'Hazard / consequence']];
function srsBlock(s) {
  if (!s.props.sil_srs && !s.props.safe_state) return `<p class="muted">No SRS entry loaded for this SIF.</p>`;
  const i = sifInfo(s.id); const ceSp = [...new Set(i.inits.map(x => x.p.setpoint).filter(Boolean))]; const ceV = [...new Set(i.inits.map(x => x.p.voting).filter(Boolean))];
  const cmp = (label, srs, ce) => `<tr><th>${label}</th><td>${esc(srs || '-')}</td><td>${esc(ce || '-')}</td><td>${!srs || !ce ? '-' : (String(srs).replace(/\s/g, '').toLowerCase() === String(ce).replace(/\s/g, '').toLowerCase() || (label === 'Sensor architecture' && ce && String(srs).toLowerCase().includes(String(ce).toLowerCase())) ? '<span class="ok">agree</span>' : '<span class="bad">DIFFER</span>')}</td></tr>`;
  let h = `<table><tr><th>Requirement (SRS)</th><th>SRS says</th><th>C&amp;E says</th><th></th></tr>` + cmp('SIL', s.props.sil_srs, s.props.sil) + cmp('Trip setpoint', s.props.setpoint_srs, ceSp.join(', ')) + cmp('Sensor architecture', s.props.sensor_architecture, ceV.join(', ')) + cmp('Logic solver', s.props.logic_solver_srs, s.props.logic_solver) + `</table>`;
  h += tbl(['Requirement', 'Value'], SRS_FIELDS.filter(([k]) => !['sil_srs', 'setpoint_srs', 'sensor_architecture', 'logic_solver_srs'].includes(k) && s.props[k]).map(([k, l]) => [esc(l), esc(s.props[k])]));
  h += `<p class="muted">Source: SRS ${esc(s.props.srs_ref || '')}</p>`;
  return h;
}
function lopaBlock(s) {
  const scs = inE(s.id, 'CREDITS').map(e => ({sc: byId[e.s], p: e.props}));
  if (!scs.length) return `<p class="muted">No LOPA scenario credits this SIF.</p>`;
  let h = '';
  for (const {sc, p} of scs) {
    const layers = outE(sc.id, 'CREDITS').map(e => ({n: byId[e.t], p: e.props}));
    const threat = outE(sc.id, 'THREATENS').map(e => cap(e.t));
    const ex = (DATA.exceptions || []).filter(e => (e.code === 'X17' || e.code === 'X18') && e.detail.includes(sc.caption));
    h += `<h3>${esc(sc.caption)} - ${esc(sc.props.consequence || '')}</h3><p>Initiating event: ${esc(sc.props.initiating_event || '?')} (${esc(sc.props.ie_frequency || '?')} /yr). Threatens ${esc(threat.join(', ') || '?')}. Severity ${esc(sc.props.severity || '?')}, tolerable frequency ${esc(sc.props.tolerable_frequency || '?')} /yr${sc.props.conditional_modifiers && sc.props.conditional_modifiers !== '-' ? ', modifiers: ' + esc(sc.props.conditional_modifiers) : ''}.<br>Demanded of this SIF: RRF ${esc(p.required_rrf || '?')}, <b>SIL ${esc(p.required_sil || '?')}</b>${p.required_sil && s.props.sil && String(p.required_sil) !== String(s.props.sil) ? ` <span class="bad">(C&amp;E says SIL ${esc(s.props.sil)}${s.props.sil_srs ? ', SRS says SIL ' + esc(s.props.sil_srs) : ''})</span>` : ''}.</p>`;
    h += tbl(['Credited layer', 'Type', 'PFD', 'Basis', 'Independence / status'], layers.map(l => { const flags = ex.filter(e => e.id === l.n.caption).map(e => `<span class="bad">${esc(e.code)}: ${esc(e.detail)}</span>`); return [esc(l.n.caption) + (l.n.id === s.id ? ' (this SIF)' : ''), esc(l.p.ipl_type || ''), esc(l.p.pfd ?? '-'), esc(l.p.credit_description || ''), flags.join('<br>') || (l.n.stub ? '<span class="bad">not in registers</span>' : '<span class="ok">in registers, no shared element found</span>')]; }));
    h += `<p class="muted">Source: LOPA ${esc(sc.props.source_doc)} rev ${esc(sc.props.source_rev)} ${esc(sc.props.source_ref || '')}${sc.props.notes ? ' - ' + esc(sc.props.notes) : ''}</p>`;
  }
  return h;
}
function designBasisReport(s) {
  const i = sifInfo(s.id);
  const ex = (DATA.exceptions || []).filter(e => e.id === s.caption);
  let h = `<h1>SIF Design Basis - ${esc(s.caption)}</h1><p class="muted">${esc(s.props.description)} | generated ${today()} from the pid_graph knowledge graph</p>`;
  h += `<p><b>Function (C&amp;E ${esc(s.props.source_doc)} rev ${esc(s.props.source_rev)}):</b> SIL ${esc(s.props.sil)}, initiators ${esc(i.inits.map(x => x.tag + ' ' + (x.p.voting || '') + ' @ ' + (x.p.setpoint || '?')).join(', '))}; final elements ${esc(i.fes.map(f => f.tag + ' ' + (f.p.action || '')).join(', '))}; protects ${esc(i.prot.join(', ') || '?')}.</p>`;
  h += `<h2>Requirements (SRS)</h2>` + srsBlock(s) + `<h2>Why it exists (LOPA)</h2>` + lopaBlock(s);
  h += `<h2>Compensating measures (curated)</h2>` + cmBlock(i.cms, new Set());
  if (ex.length) h += `<h2>Consistency findings for this SIF</h2>` + tbl(['Code', 'Finding'], ex.map(e => [esc(e.code), esc(e.detail)]));
  h += `<p class="muted">Sources: ${docsLine()}</p>`;
  return h;
}
function showReport(html) { document.getElementById('reportbody').innerHTML = html; document.getElementById('report').hidden = false; window.scrollTo(0, 0); }
document.getElementById('rClose').onclick = () => document.getElementById('report').hidden = true;
document.getElementById('rPrint').onclick = () => window.print();
document.getElementById('btnRegister').onclick = () => showReport(registerReport());
document.getElementById('btnBypass').onclick = () => { if (sel && sel.kind === 'node' && sel.obj.label === 'Instrument') showReport(bypassReport(sel.obj, 'Bypass')); };
document.getElementById('btnMOS').onclick = () => { if (sel && sel.kind === 'node' && outE(sel.obj.id, 'INITIATES').length) showReport(bypassReport(sel.obj, 'MOS')); };
document.getElementById('btnShelve').onclick = () => { if (sel && sel.kind === 'node' && sel.obj.label === 'Alarm') showReport(shelveReport(sel.obj)); };
document.getElementById('btnMOC').onclick = () => { if (sel && sel.kind === 'node' && sel.obj.label !== 'Document') showReport(mocReport(sel.obj, +document.getElementById('mocHops').value, document.getElementById('mocRef').value)); };
document.getElementById('btnHandover').onclick = () => showReport(handoverReport());
document.getElementById('btnTrip').onclick = () => { if (sel && sel.kind === 'node' && sel.obj.label === 'SIF') showReport(tripPack(sel.obj)); };
document.getElementById('btnDesign').onclick = () => { if (sel && sel.kind === 'node' && sel.obj.label === 'SIF') showReport(designBasisReport(sel.obj)); };
function setButtons(obj, kind) { const node = kind === 'node' ? obj : null;
  document.getElementById('btnTrip').disabled = !(node && node.label === 'SIF' && !node.stub);
  document.getElementById('btnDesign').disabled = !(node && node.label === 'SIF' && !node.stub);
  document.getElementById('btnBypass').disabled = !(node && node.label === 'Instrument');
  document.getElementById('btnMOS').disabled = !(node && node.label === 'Instrument' && outE(node.id, 'INITIATES').length);
  document.getElementById('btnShelve').disabled = !(node && node.label === 'Alarm');
  document.getElementById('btnMOC').disabled = !(node && node.label !== 'Document'); }
const _select = select; select = function (obj, kind) { _select(obj, kind); setButtons(obj, kind); };
svg.addEventListener('click', () => setButtons(null, null));
</script></body></html>
"""


def build(store, unit: str, load_run: str, include_pending: bool = False) -> str:
    """The in-page assessments are safety-relevant surfaces, so by default the page is built from the
    trusted view (trust rule T7): pending and rejected vision facts are left out. include_pending=True
    shows everything and says so; use it to look at the vision layer, not to assess anything."""
    from . import ontology as O
    from .records import TrustedView
    view = TrustedView(store)
    hidden = view.left_out()
    hidden_n = hidden["nodes"] + hidden["rels"]
    if include_pending:
        gate_note = f" - EXPLORATION: includes {hidden_n} pending / rejected vision facts; not for assessments" if hidden_n else ""
    else:
        gate_note = f" - {hidden_n} pending vision facts left out (trust rule T7)" if hidden_n else ""
        store = view
    nodes, index = [], {}
    for n in store.nodes():
        key = tuple(str(n["key"][k]) for k in O.KEYS[n["label"]])
        caption = " rev ".join(key) if n["label"] == "Document" else key[0]
        index[(n["label"], key)] = len(nodes)
        props = {k: v for k, v in n["props"].items() if k not in ("stub",)}
        nodes.append({"id": len(nodes), "label": n["label"], "caption": caption, "stub": bool(n["props"].get("stub")), "props": props})
    edges = []
    extraction: dict[str, dict] = {}
    for r in store.rels():
        s = index[(r["start_label"], tuple(str(r["start_key"][k]) for k in O.KEYS[r["start_label"]]))]
        t = index[(r["end_label"], tuple(str(r["end_key"][k]) for k in O.KEYS[r["end_label"]]))]
        edges.append({"s": s, "t": t, "type": r["type"], "props": r["props"]})
        f = r["props"].get("source_file")
        if f:
            x = extraction.setdefault(f, {"file": f, "edges": 0, "by": set()})
            x["edges"] += 1
            x["by"].add(r["props"].get("extracted_by", ""))
    documents = _document_links(store, extraction)
    from .reconcile import reconcile
    exceptions = reconcile(store, unit=unit)["exceptions"]
    from datetime import datetime
    html = (TEMPLATE.replace("__UNIT__", unit).replace("__NODES__", str(len(nodes))).replace("__EDGES__", str(len(edges)))
            .replace("__LOADRUN__", load_run).replace("__COLORS__", json.dumps(COLORS))
            .replace("__DATA__", json.dumps({"unit": unit, "nodes": nodes, "edges": edges, "documents": documents,
                                              "exceptions": exceptions, "generated": datetime.now().strftime("%Y-%m-%d %H:%M") + gate_note}, default=str)))
    return html


def _find_file(name: str) -> Path | None:
    """Locate a source file under data/ (recursively) by its file name."""
    if not name:
        return None
    hits = sorted((ROOT / "data").rglob(name))
    return hits[0] if hits else None


def _document_links(store, extraction: dict) -> list[dict]:
    """Every source the graph rests on, with a link relative to reports/ that works offline."""
    out = []
    for n in sorted(store.nodes("Document"), key=lambda d: (d["props"].get("doc_type", ""), d["key"]["doc_no"])):
        p = n["props"]
        path = _find_file(p.get("file", ""))
        href = None
        if path is not None:
            href = "../" + path.relative_to(ROOT).as_posix()
            pages = p.get("pages")
            if path.suffix.lower() == ".pdf" and pages:
                href += f"#page={pages[0]}"
        out.append({"doc_no": n["key"]["doc_no"], "rev": n["key"]["rev"], "doc_type": p.get("doc_type", ""), "title": p.get("title", ""),
                    "file": p.get("file", ""), "pages": p.get("pages"), "transmittal": p.get("transmittal", ""),
                    "stub": bool(p.get("stub")), "href": href, "found": path is not None, "kind": "document"})
    for f, x in sorted(extraction.items()):
        path = _find_file(f)
        out.append({"doc_no": f, "rev": "", "doc_type": "EXTRACTION", "title": f"P&ID extraction ({', '.join(sorted(x['by']))}), {x['edges']} edges",
                    "file": f, "pages": None, "transmittal": "", "stub": False,
                    "href": ("../" + path.relative_to(ROOT).as_posix()) if path else None, "found": path is not None, "kind": "extraction"})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--unit", default="U-100")
    ap.add_argument("--backend", choices=["neo4j", "memory"], default="neo4j")
    ap.add_argument("--out", default=None)
    ap.add_argument("--include-pending", action="store_true",
                    help="exploration only: also show vision facts that are review=pending or rejected")
    a = ap.parse_args(argv)
    if a.backend == "neo4j":
        from .db import DATABASE, get_driver
        from .neo4j_store import Neo4jStore
        d = get_driver()
        try:
            store = Neo4jStore(d, DATABASE)
            runs = sorted({n["props"].get("load_run", "") for n in store.nodes()})
            html = build(store, a.unit, runs[-1] if runs else "", include_pending=a.include_pending)
        finally:
            d.close()
    else:
        from .pipeline import build_store, new_load_run
        store, _ = build_store(unit=a.unit, index=ROOT / "data" / "U100-INST-INDEX-Rev-B.xlsx", ce=ROOT / "data" / "U100-CE-CHART-Rev-A.xlsx",
                               topology=ROOT / "data" / "pid_audit_U100_topology.csv", load_run=new_load_run("explorer"),
                               curated=ROOT / "data" / "curated" / "compensating_measures_U-100.csv")
        html = build(store, a.unit, "memory", include_pending=a.include_pending)
    out = Path(a.out) if a.out else ROOT / "reports" / f"explorer_{a.unit}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
