/**
 * WFR live sheet - follows git. Rebuilds from the public GitHub repo (the 7 pm refresh session pushes it):
 *
 *   Tab order (always enforced after a refresh):
 *     1 Summary        max 8 rows x 3 columns (WFR | Damage | Swap), last 30 days
 *     2 WFR funnel     complaint baseline (return requests U Zoho tickets) with the root-cause cascade, 60 days, day-wise
 *     3 Order damage   same, physical damage by photo bucket
 *     4 Order Swap     swap cases attributed Warehouse vs Logistics
 *     5 WFR raw data / Damage raw data / Swap raw data   one row per complaint / case (the detailed breakdown of each view)
 *     then Info, hidden spec tabs, and any other tab (e.g. "sreeniketh") - those are NEVER touched.
 *
 *   NOTHING IS EVER DELETED (owner, 2026-11-20): raw-data tabs are a cache = archive U latest export, upserted by key
 *   (Order ID + Complaint type, or Order ID + Ticket ID). Rows that leave the 60-day window stay; existing rows are refreshed in place;
 *   new rows are appended; new columns are appended at the right. The views are re-computed from the raw tabs (window = trailing 60 days).
 *   The git side keeps the same rows in pipeline/archive/*_archive.json (pipeline/archive_exports.py), so the sheet can always be rebuilt.
 *
 *   Daily: two triggers, 07:00 and 21:00 IST (the 7 pm routine pushes around 20:00 IST). Every view tab and the Info tab show
 *   "Data through <date>" and turn red (STALE) when a layer is more than 2 days behind - a silently stale tab is a bug.
 *
 * Setup: see README.md (paste this file into Extensions > Apps Script, run refreshAll once, then installDailyTrigger once).
 */

var BASE = 'https://raw.githubusercontent.com/vermatanishk/WFR-dashboard-TV-/main/pipeline/';
var ARCH_BASE = BASE + 'archive/';
var INFO_TAB = 'Info';
var HEADER_ROW = 3;               // view tabs: row 1 = status banner, row 3 = column header

// Order swap layer (own raw data + spec)
var SWAP = { exp: BASE + 'swap_export.json', spec: BASE + 'swap_view_spec.json', arch: ARCH_BASE + 'swap_export_archive.json',
             raw: 'Swap raw data', view: 'Order Swap', specTab: 'Swap spec', keys: ['Order ID', 'Ticket ID'], name: 'Order swap' };

// Complaint baseline layer: union of ClickHouse return requests + Zoho tickets -> WFR funnel, Order damage, Summary.
var CMP_VIEWS = [
  { exp: BASE + 'cmp_wfr_export.json', spec: BASE + 'cmp_wfr_view_spec.json', arch: ARCH_BASE + 'cmp_wfr_export_archive.json',
    raw: 'WFR raw data', view: 'WFR funnel', specTab: 'WFR spec', keys: ['Order ID', 'Complaint type'], name: 'WFR funnel' },
  { exp: BASE + 'cmp_damage_export.json', spec: BASE + 'cmp_damage_view_spec.json', arch: ARCH_BASE + 'cmp_damage_export_archive.json',
    raw: 'Damage raw data', view: 'Order damage', specTab: 'Damage spec', keys: ['Order ID', 'Complaint type'], name: 'Order damage' }
];
var RCA_EXPORT_URL = BASE + 'rca_export.json';          // freshness of the root-cause columns (shown on Info)
var SANITY_URL = BASE + 'sanity_report.json';
var SUMMARY_URL = BASE + 'cmp_summary.json';
var SUMMARY_TAB = 'Summary';
var VIEW_TAB_COLOR = '#c0392b';      // dark red: the dashboard (view) tabs - raw-data tabs stay uncoloured
var SUMMARY_TAB_COLOR = '#7f1d1d';   // darkest red: the Summary tab
var STALE_DAYS = 2;                  // a layer more than this many days behind today (IST) is flagged STALE
var TAB_ORDER = ['Summary', 'WFR funnel', 'Order damage', 'Order Swap', 'WFR raw data', 'Damage raw data', 'Swap raw data', 'Info'];

function onOpen() {
  SpreadsheetApp.getUi().createMenu('WFR')
    .addItem('Refresh now', 'refreshAll')
    .addItem('Install daily refresh (07:00 + 21:00 IST)', 'installDailyTrigger')
    .addItem('Re-order tabs', 'orderTabs_')
    .addToUi();
}

/** Refresh every layer. A failing layer never stops the others; its error is written to the Info tab and the tab is flagged. */
function refreshAll() {
  var errors = [];
  var status = {};
  function run(label, fn) {
    try { fn(); } catch (e) { errors.push(label + ': ' + e.message); }
  }
  CMP_VIEWS.forEach(function (c) { run(c.name, function () { status[c.name] = refreshView_(c); }); });
  run('Summary', function () { writeSummary_(fetchJson_(SUMMARY_URL)); });
  run('Order swap', function () { status[SWAP.name] = refreshView_(SWAP); });
  run('Info', function () { writeInfo_(status, errors); });
  run('Tabs', orderTabs_);
  SpreadsheetApp.getActive().toast(errors.length ? 'Refreshed with ' + errors.length + ' error(s) - see Info' : 'All views refreshed', 'WFR', 5);
}

/** Raw tab (upsert, never delete) + hidden spec + the view computed from the whole raw tab. Returns {through, generated}. */
function refreshView_(c) {
  var exp = fetchJson_(c.exp);
  var spec = fetchJson_(c.spec);
  var arch = null;
  try { arch = fetchJson_(c.arch); } catch (e) { arch = null; }   // archive is optional until the first push that contains it
  var n = upsertRaw_(c.raw, exp, arch, c.keys);
  saveSpec_(spec, exp, c.specTab);
  var raw = sheet_(c.raw).getDataRange().getValues();
  var st = statusText_(exp.t2_cap_date, exp.generated_at);
  writeView_(computeView_(raw[0], raw.slice(1), spec.layout, exp.t2_cap_date, exp.generated_at, null), c.view, st);
  return { through: exp.t2_cap_date, generated: exp.generated_at, rawRows: n, stale: st.stale };
}

/** Summary: at most 8 rows x 3 columns, macro numbers only. */
function writeSummary_(s) {
  var sh = sheet_(SUMMARY_TAB);
  sh.setTabColor(SUMMARY_TAB_COLOR);
  sh.clear();
  var head = ['Metric'].concat(s.columns);
  var vals = [head].concat(s.rows.map(function (r) { return [r.label + '  (' + r.sub + ')'].concat(r.values); }));
  sh.getRange(1, 1, 1, 1).setValue('Complaints raised ' + s.window[0] + ' to ' + s.window[1] + ' (last 30 days). Cells: count | % of the row named in brackets.').setFontStyle('italic');
  var st = statusText_(s.window[1], s.generated_at || '');
  sh.getRange(2, 1).setValue(st.text).setFontColor(st.stale ? '#b91c1c' : '#15803d').setFontWeight('bold');
  sh.getRange(3, 1, vals.length, head.length).setValues(vals);
  sh.getRange(3, 1, 1, head.length).setFontWeight('bold').setBackground('#1f2937').setFontColor('#ffffff');
  sh.getRange(3, 2, vals.length, head.length - 1).setHorizontalAlignment('right');
  (s.footnotes || []).forEach(function (t, i) { sh.getRange(3 + vals.length + 1 + i, 1).setValue(t).setFontColor('#52514e'); });
  sh.setColumnWidth(1, 520);
  for (var c = 2; c <= head.length; c++) sh.setColumnWidth(c, 130);
}

/** "Data through D" banner; STALE when D is more than STALE_DAYS behind today (IST). Pure string logic. */
function statusText_(through, generated) {
  var today = Utilities.formatDate(new Date(), 'Asia/Kolkata', 'yyyy-MM-dd');
  var lag = Math.round((new Date(today + 'T00:00:00Z') - new Date(String(through) + 'T00:00:00Z')) / 86400000);
  var stale = !(lag <= STALE_DAYS);
  var txt = (stale ? '⚠ STALE - data only through ' : 'Data through ') + through + (generated ? ' (built ' + String(generated).slice(0, 16).replace('T', ' ') + ' UTC)' : '') +
            (stale ? ' - today is ' + today + '; the daily routine has not delivered newer data (see Info).' : '');
  return { text: txt, stale: stale, lag: lag };
}

/** Save the layout (chunked, one JSON string split across rows) + cutoff in a hidden tab (derived from git, safe to rewrite). */
function saveSpec_(spec, exp, tab) {
  var sh = sheet_(tab);
  sh.clear();
  var txt = JSON.stringify({ layout: spec.layout, t2_cap_date: exp.t2_cap_date, generated_at: exp.generated_at });
  var rows = [];
  for (var i = 0; i < txt.length; i += 40000) rows.push([txt.substring(i, i + 40000)]);
  sh.getRange(1, 1, rows.length, 1).setValues(rows);
  sh.hideSheet();
}

function onEdit(e) {}

/** Two daily refreshes: 07:00 IST and 21:00 IST (after the 7 pm routine has pushed). raw.githubusercontent caches ~5 minutes. */
function installDailyTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'refreshAll') ScriptApp.deleteTrigger(t);
  });
  [7, 21].forEach(function (h) {
    ScriptApp.newTrigger('refreshAll').timeBased().everyDays(1).atHour(h).inTimezone('Asia/Kolkata').create();
  });
}

function fetchJson_(url) {
  var res = UrlFetchApp.fetch(url + '?t=' + Date.now(), { muteHttpExceptions: true });
  if (res.getResponseCode() !== 200) {
    throw new Error('Fetch failed ' + res.getResponseCode() + ' for ' + url);
  }
  return JSON.parse(res.getContentText());
}

function sheet_(name) {
  var ss = SpreadsheetApp.getActive();
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

/**
 * NON-DESTRUCTIVE raw tab. Result = every row already in the tab U archive rows (added if missing) U latest export rows (upsert).
 * Key = the key columns joined; an export value replaces the cell unless it is blank; unknown columns are appended at the right;
 * rows are never removed. Sorted newest day first for readability (a sort is a re-order, not a delete). Returns the row count.
 */
function upsertRaw_(tab, exp, arch, keyCols) {
  var sh = sheet_(tab);
  var existing = sh.getLastRow() > 0 ? sh.getDataRange().getValues() : [];
  var header = existing.length ? existing[0].map(String) : [];
  [arch, exp].forEach(function (src) {
    if (!src) return;
    src.columns.forEach(function (c) { if (header.indexOf(c) < 0) header.push(c); });
  });
  var W = header.length;
  var rows = existing.slice(1).map(function (r) { var o = r.slice(0, W); while (o.length < W) o.push(''); return o; });
  var kix = keyCols.map(function (k) { return header.indexOf(k); });
  function keyOf(r) { return kix.map(function (i) { return String(r[i]); }).join('|'); }
  var index = {};
  rows.forEach(function (r, i) { index[keyOf(r)] = i; });
  function toRow(src, row) {
    var o = new Array(W);
    for (var i = 0; i < W; i++) o[i] = '';
    src.columns.forEach(function (c, j) { o[header.indexOf(c)] = row[j]; });
    return o;
  }
  if (arch) {          // archive: only fills rows the sheet does not hold yet (the sheet's own copy is at least as new)
    arch.rows.forEach(function (r) {
      var o = toRow(arch, r), k = keyOf(o);
      if (!(k in index)) { index[k] = rows.length; rows.push(o); }
    });
  }
  exp.rows.forEach(function (r) {   // latest export: refresh in place or append
    var o = toRow(exp, r), k = keyOf(o);
    if (k in index) {
      var old = rows[index[k]];
      for (var i = 0; i < W; i++) if (o[i] !== '' && o[i] !== null) old[i] = o[i];
    } else { index[k] = rows.length; rows.push(o); }
  });
  var dcol = header.indexOf('Created date');
  rows.sort(function (a, b) {
    var x = isoDate_(a[dcol]), y = isoDate_(b[dcol]);
    if (x !== y) return x < y ? 1 : -1;
    var p = String(a[0]), q = String(b[0]);
    return p === q ? 0 : (p < q ? 1 : -1);
  });
  var values = [header].concat(rows);
  if (sh.getMaxColumns() < W) sh.insertColumnsAfter(sh.getMaxColumns(), W - sh.getMaxColumns());
  if (sh.getMaxRows() < values.length) sh.insertRowsAfter(sh.getMaxRows(), values.length - sh.getMaxRows());
  sh.getRange(1, dcol + 1, values.length, 1).setNumberFormat('@');          // keep ISO dates as text
  sh.getRange(1, 1, values.length, W).setValues(values);
  sh.getRange(1, 1, 1, W).setFontWeight('bold').setBackground('#1f2937').setFontColor('#ffffff');
  sh.setFrozenRows(1);
  sh.setFrozenColumns(2);
  if (sh.getFilter()) sh.getFilter().remove();
  sh.getRange(1, 1, values.length, W).createFilter();
  return rows.length;
}

function writeView_(t, tab, st) {
  var sh = sheet_(tab);
  sh.setTabColor(VIEW_TAB_COLOR);
  sh.clear();
  sh.getRange('A1').setValue((st ? st.text + '   |   ' : '') + 'Window: last 60 days. Detail: filter the matching raw-data tab (it also holds older rows).')
    .setFontStyle('italic').setFontColor(st && st.stale ? '#b91c1c' : '#374151').setFontWeight(st && st.stale ? 'bold' : 'normal');
  var days = t.days.slice().reverse(); // most recent first, same as the website
  var head = ['Metric', 'Last 60 days total', 'Last 30 days total', 'Last 14 days total']
    .concat(days.map(function (d) { return t.day_labels[d]; }));
  var rows = t.rows.map(function (r) {
    var label = new Array((r.indent || 0) * 3 + 1).join(' ') + r.label + (r.sub ? '  (' + r.sub + ')' : '');
    return [label, r['3mo'].text, r['1mo'].text, r['2wk'].text].concat(days.map(function (d) { return r.daily[d].text; }));
  });
  var values = [head].concat(rows);
  sh.getRange(HEADER_ROW, 1, values.length, head.length).setValues(values);
  sh.getRange(HEADER_ROW, 1, 1, head.length).setFontWeight('bold').setBackground('#1f2937').setFontColor('#ffffff');
  t.rows.forEach(function (r, i) {
    if (r.kind === 'wfr_pto') {
      sh.getRange(HEADER_ROW + 1 + i, 1, 1, head.length).setFontWeight('bold').setBackground('#fff3cd');
    }
  });
  sh.setFrozenRows(HEADER_ROW);
  sh.setFrozenColumns(4);
  sh.setColumnWidth(1, 420);
  sh.getRange(HEADER_ROW, 2, values.length, head.length - 1).setHorizontalAlignment('right');
  sh.getRange(HEADER_ROW + 1, 1, rows.length, head.length).setFontSize(10);
}

/** Info: per-layer data-through dates (red when stale), the last refresh errors and the latest sanity-check result. */
function writeInfo_(status, errors) {
  var sh = sheet_(INFO_TAB);
  sh.clear();
  var rca = null, sanity = null;
  try { rca = fetchJson_(RCA_EXPORT_URL); } catch (e) { rca = null; }
  try { sanity = fetchJson_(SANITY_URL); } catch (e) { sanity = null; }
  var info = [['Sheet refreshed', new Date()], ['Source', BASE], ['Cache', 'Raw-data tabs are append/upsert only - rows are never deleted; archive in git: pipeline/archive/']];
  var flags = [];
  Object.keys(status).forEach(function (k) {
    var s = status[k]; var st = statusText_(s.through, s.generated);
    info.push(['Layer: ' + k, st.text + '  | raw rows kept: ' + s.rawRows]); flags.push(st.stale);
  });
  if (rca) { var sr = statusText_(rca.t2_cap_date, rca.generated_at); info.push(['Layer: root-cause (RCA) columns', sr.text]); flags.push(sr.stale); }
  if (sanity) {
    info.push(['Sanity check (values vs T-2)', sanity.pass + ' pass, ' + sanity.fail + ' fail - cap ' + sanity.cap + ' - ' + sanity.generated_at]);
    flags.push(sanity.fail > 0);
    sanity.checks.forEach(function (c) { if (c.status === 'FAIL' || c.status === 'WARN') { info.push(['  ' + c.status + ' [' + c.section + ']', c.text]); flags.push(c.status === 'FAIL'); } });
  }
  errors.forEach(function (e) { info.push(['REFRESH ERROR', e]); flags.push(true); });
  info.push(['', ''], ['How to read', 'A complaint = one order x complaint type, from the UNION of ClickHouse return requests and Zoho tickets. Cells are "count | % of parent row". Views cover the last 60 days; raw tabs hold everything ever pulled.'],
            ['Evidence', 'Photo-derived buckets are hand-read from customer photos. Cold-chain damage is not photo-read. Warehouse accepted = explicit admission read from the Warehouse comment thread.']);
  sh.getRange(1, 1, info.length, 2).setValues(info);
  sh.getRange(1, 1, info.length, 1).setFontWeight('bold');
  flags.forEach(function (bad, i) { sh.getRange(4 + i, 2).setFontColor(bad ? '#b91c1c' : '#15803d'); });
  sh.setColumnWidth(1, 360);
  sh.setColumnWidth(2, 900);
}

/** Summary, WFR funnel, Order damage, Order Swap, then the three raw tabs, then Info. Every other tab (hidden specs, user tabs) is left where it is. */
function orderTabs_() {
  var ss = SpreadsheetApp.getActive();
  var pos = 1;
  TAB_ORDER.forEach(function (n) {
    var sh = ss.getSheetByName(n);
    if (!sh || sh.isSheetHidden()) return;
    ss.setActiveSheet(sh);
    ss.moveActiveSheet(pos++);
  });
  var first = ss.getSheetByName('Summary');
  if (first) ss.setActiveSheet(first);
}

/**
 * Pure evaluator, mirrors pipeline/rca_view_spec.py evaluate(). No Apps Script APIs, so it is unit-tested in
 * node. columns: header row of Raw data; rows: data rows; layout: rca_view_spec.json layout; cutoff: T-2 date.
 */
var WINDOW_DAYS_ = 60;
var MONTHS_ = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function isoDate_(v) {
  if (v instanceof Date) {
    var m = v.getMonth() + 1, d = v.getDate();
    return v.getFullYear() + '-' + (m < 10 ? '0' : '') + m + '-' + (d < 10 ? '0' : '') + d;
  }
  return String(v);
}

function computeView_(columns, rows, layout, cutoff, generatedAt, returnState, days) {
  var col = {};
  columns.forEach(function (c, i) { col[c] = i; });
  var dcol = col['Created date'];
  var rcol = col['Return request'];
  var kept = rows.filter(function (r) {
    return isoDate_(r[dcol]) <= cutoff && (!returnState || String(r[rcol]) === returnState);
  });
  var byDay = {};
  kept.forEach(function (r) {
    var d = isoDate_(r[dcol]);
    (byDay[d] = byDay[d] || []).push(r);
  });
  // day columns are always those of the unfiltered view, so the selector never shifts them
  if (!days) {
    // calendar days, trailing WINDOW_DAYS_ ending at the cutoff (mirrors rca_view_spec.evaluate)
    var mn = null;
    rows.forEach(function (r) { var d = isoDate_(r[dcol]); if (d <= cutoff && (mn === null || d < mn)) mn = d; });
    var end = new Date(cutoff + 'T00:00:00Z');
    var start = new Date(end.getTime() - (WINDOW_DAYS_ - 1) * 86400000);
    var first = mn !== null && new Date(mn + 'T00:00:00Z') > start ? new Date(mn + 'T00:00:00Z') : start;
    days = [];
    for (var t = first.getTime(); t <= end.getTime(); t += 86400000) days.push(new Date(t).toISOString().slice(0, 10));
    byDay = {};
    kept.forEach(function (r) { var d = isoDate_(r[dcol]); if (d >= days[0]) (byDay[d] = byDay[d] || []).push(r); });
  }
  days.forEach(function (d) { byDay[d] = byDay[d] || []; });
  function matches(r, where) {
    for (var i = 0; i < where.length; i++) {
      var c = where[i][0], op = where[i][1], vals = where[i][2];
      var v = String(r[col[c]]);
      if ((op === 'in') !== (vals.indexOf(v) >= 0)) return false;
    }
    return true;
  }
  var items = {}, cache = {};
  layout.forEach(function (it) { items[it.key] = it; });
  function counts(it) {
    if (!cache[it.key]) {
      var o = {};
      days.forEach(function (d) {
        o[d] = byDay[d].filter(function (r) { return matches(r, it.where); }).length;
      });
      cache[it.key] = o;
    }
    return cache[it.key];
  }
  function sum(o, ds) { return ds.reduce(function (a, d) { return a + o[d]; }, 0); }
  function cell(it, ds) {
    var n = sum(counts(it), ds);
    if (it.parent === null || it.parent === undefined) return { n: n, text: String(n) };
    var den = sum(counts(items[it.parent]), ds);
    // Python rounds half to even; JS Math.round rounds half up - emulate banker's rounding to match.
    var x = den ? 100 * n / den : 0;
    var fl = Math.floor(x), diff = x - fl;
    var r = diff > 0.5 ? fl + 1 : diff < 0.5 ? fl : (fl % 2 === 0 ? fl : fl + 1);
    var pct = den ? r + '%' : '\u2013';
    return { n: n, text: n + ' | ' + pct };
  }
  var out = layout.map(function (it) {
    var daily = {};
    days.forEach(function (d) { daily[d] = cell(it, [d]); });
    return { key: it.key, label: it.label, sub: it.sub || null, kind: it.head ? 'wfr_pto' : 'plain', indent: it.indent,
             '3mo': cell(it, days), '1mo': cell(it, days.slice(-30)), '2wk': cell(it, days.slice(-14)), daily: daily };
  });
  var labels = {};
  days.forEach(function (d) { labels[d] = parseInt(d.slice(8, 10), 10) + ' ' + MONTHS_[parseInt(d.slice(5, 7), 10) - 1]; });
  return { days: days, day_labels: labels, rows: out, as_of: String(generatedAt).slice(0, 10), t2_cutoff: cutoff,
           excluded_tickets: rows.filter(function (r) { return isoDate_(r[dcol]) > cutoff && (!returnState || String(r[rcol]) === returnState); }).length };
}
