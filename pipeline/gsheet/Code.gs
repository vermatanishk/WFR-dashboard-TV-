/**
 * WFR RCA live sheet - pulls JSON from the public GitHub repo and rebuilds two tabs:
 *   "Raw data"  - one row per order (trailing 60 days): order, ticket, issue, investigation buckets,
 *                 raised buckets, evidence.            <- pipeline/rca_export.json
 *   "RCA view"  - the website's Tab 7 day-wise table, COMPUTED HERE FROM THE "Raw data" TAB using the
 *                 declarative layout in pipeline/rca_view_spec.json (same spec the website uses, so the
 *                 two cannot drift; pipeline/test_view_js.js checks this evaluator against rca_trend.json).
 * The files are rebuilt and pushed by the daily refresh session, so the sheet follows git.
 *
 * Setup: see README.md in this folder (paste this file into Extensions > Apps Script, run refreshAll once,
 * then run installDailyTrigger once).
 */

var BASE = 'https://raw.githubusercontent.com/vermatanishk/WFR-dashboard-TV-/main/pipeline/';
var EXPORT_URL = BASE + 'rca_export.json';
var SPEC_URL = BASE + 'rca_view_spec.json';
var RAW_TAB = 'Raw data';
var VIEW_TAB = 'RCA view';
var INFO_TAB = 'Info';
var FILTER_CELL = 'B1';          // "Return request" selector on the RCA view tab
var RET_OPTIONS = ['All', 'Raised - Accepted & refunded', 'Raised - Cancelled', 'Raised - Rejected', 'Raised - In progress', 'Not raised'];
var HEADER_ROW = 3;               // RCA view: row 1 = selector, row 3 = column header
var SPEC_TAB = 'Spec';
// Order swap layer (separate tab, own raw data + spec; the RCA tabs above are untouched)
var SWAP_EXPORT_URL = BASE + 'swap_export.json';
var SWAP_SPEC_URL = BASE + 'swap_view_spec.json';
var SWAP_RAW_TAB = 'Swap raw data';
var SWAP_VIEW_TAB = 'Order Swap';
var SWAP_SPEC_TAB = 'Swap spec';            // hidden: layout + cutoff saved at refresh so the dropdown works offline

// Complaint baseline layer (2026-10-25): union of ClickHouse return requests + Zoho tickets -> WFR funnel, Order damage, Summary.
// Each view has its own raw tab + hidden spec tab and the same Return request dropdown (B1) as the RCA tabs.
var CMP_VIEWS = [
  { exp: BASE + 'cmp_wfr_export.json', spec: BASE + 'cmp_wfr_view_spec.json', raw: 'WFR raw data', view: 'WFR funnel', specTab: 'WFR spec', noFilter: true },
  { exp: BASE + 'cmp_damage_export.json', spec: BASE + 'cmp_damage_view_spec.json', raw: 'Damage raw data', view: 'Order damage', specTab: 'Damage spec' }
];
var SUMMARY_URL = BASE + 'cmp_summary.json';
var SUMMARY_TAB = 'Summary';
var VIEW_TAB_COLOR = '#ffe699';      // light yellow: the dashboard (view) tabs - raw-data tabs stay uncoloured
var SUMMARY_TAB_COLOR = '#f4b6b6';   // light red: the Summary tab

function onOpen() {
  SpreadsheetApp.getUi().createMenu('WFR RCA')
    .addItem('Refresh now', 'refreshAll')
    .addItem('Install daily refresh (07:00 IST)', 'installDailyTrigger')
    .addToUi();
}

function refreshAll() {
  var exp = fetchJson_(EXPORT_URL);
  var spec = fetchJson_(SPEC_URL);
  writeRaw_(exp);
  saveSpec_(spec, exp);
  // Build the view from what is actually in the Raw data tab (so a filtered/edited tab is what you see).
  var trend = buildViewFromRaw_(spec, exp);
  writeView_(trend);
  writeInfo_(exp, trend);
  refreshSwap_();
  refreshCmp_();
  SpreadsheetApp.getActive().toast('RCA data refreshed (' + exp.rows.length + ' orders)', 'WFR RCA', 5);
}

/** Order swap tab: raw cases + view computed from them with the same evaluator as the RCA view. */
function refreshSwap_() {
  var exp = fetchJson_(SWAP_EXPORT_URL);
  var spec = fetchJson_(SWAP_SPEC_URL);
  writeRaw_(exp, SWAP_RAW_TAB);
  saveSpec_(spec, exp, SWAP_SPEC_TAB);
  var raw = sheet_(SWAP_RAW_TAB).getDataRange().getValues();
  var rs = currentReturnFilter_(SWAP_VIEW_TAB);
  writeView_(computeView_(raw[0], raw.slice(1), spec.layout, exp.t2_cap_date, exp.generated_at, rs === 'All' ? null : rs), SWAP_VIEW_TAB);
}

/** Complaint-baseline tabs: raw cases + view computed from them (same evaluator), then the static Summary tab. */
function refreshCmp_() {
  CMP_VIEWS.forEach(function (c) {
    var exp = fetchJson_(c.exp);
    var spec = fetchJson_(c.spec);
    writeRaw_(exp, c.raw);
    saveSpec_(spec, exp, c.specTab);
    var raw = sheet_(c.raw).getDataRange().getValues();
    var rs = c.noFilter ? 'All' : currentReturnFilter_(c.view);
    writeView_(computeView_(raw[0], raw.slice(1), spec.layout, exp.t2_cap_date, exp.generated_at, rs === 'All' ? null : rs), c.view, c.noFilter);
  });
  writeSummary_(fetchJson_(SUMMARY_URL));
}

/** Summary: at most 8 rows x 3 columns, macro numbers only. */
function writeSummary_(s) {
  var sh = sheet_(SUMMARY_TAB);
  sh.setTabColor(SUMMARY_TAB_COLOR);
  sh.clear();
  var head = ['Metric'].concat(s.columns);
  var vals = [head].concat(s.rows.map(function (r) { return [r.label + '  (' + r.sub + ')'].concat(r.values); }));
  sh.getRange(1, 1, 1, 1).setValue('Complaints raised ' + s.window[0] + ' to ' + s.window[1] + ' (last 30 days). Cells: count | % of the row named in brackets.').setFontStyle('italic');
  sh.getRange(3, 1, vals.length, head.length).setValues(vals);
  sh.getRange(3, 1, 1, head.length).setFontWeight('bold').setBackground('#1f2937').setFontColor('#ffffff');
  sh.getRange(3, 2, vals.length, head.length - 1).setHorizontalAlignment('right');
  (s.footnotes || []).forEach(function (t, i) { sh.getRange(3 + vals.length + 1 + i, 1).setValue(t).setFontColor('#52514e'); });
  sh.setColumnWidth(1, 520);
  for (var c = 2; c <= head.length; c++) sh.setColumnWidth(c, 130);
}

function viewConfigs_() {
  return [{ raw: RAW_TAB, view: VIEW_TAB, specTab: SPEC_TAB }, { raw: SWAP_RAW_TAB, view: SWAP_VIEW_TAB, specTab: SWAP_SPEC_TAB }]
    .concat(CMP_VIEWS);
}

function currentReturnFilter_(tab) {
  var v = sheet_(tab || VIEW_TAB).getRange(FILTER_CELL).getValue();
  return RET_OPTIONS.indexOf(v) >= 0 ? v : 'All';
}

function buildViewFromRaw_(spec, exp) {
  var raw = sheet_(RAW_TAB).getDataRange().getValues();
  var rs = currentReturnFilter_();
  return computeView_(raw[0], raw.slice(1), spec.layout, exp.t2_cap_date, exp.generated_at, rs === 'All' ? null : rs);
}

/** Save the layout (chunked, one JSON string split across rows) + cutoff in a hidden tab. */
function saveSpec_(spec, exp, tab) {
  var sh = sheet_(tab || SPEC_TAB);
  sh.clear();
  var txt = JSON.stringify({ layout: spec.layout, t2_cap_date: exp.t2_cap_date, generated_at: exp.generated_at });
  var rows = [];
  for (var i = 0; i < txt.length; i += 40000) rows.push([txt.substring(i, i + 40000)]);
  sh.getRange(1, 1, rows.length, 1).setValues(rows);
  sh.hideSheet();
}

function loadSpec_(tab) {
  var vals = sheet_(tab || SPEC_TAB).getDataRange().getValues();
  return JSON.parse(vals.map(function (r) { return r[0]; }).join(''));
}

/**
 * Changing the Return request dropdown re-cuts the whole view from the Raw data tab. A simple onEdit trigger
 * cannot call external URLs, so it only uses data already in the sheet (Raw data + the hidden Spec tab).
 */
function onEdit(e) {
  var sh = e && e.range && e.range.getSheet();
  if (!sh || e.range.getA1Notation() !== FILTER_CELL) return;
  var cfg = viewConfigs_().filter(function (c) { return c.view === sh.getName(); })[0];
  if (!cfg) return;
  var spec = loadSpec_(cfg.specTab);
  var raw = sheet_(cfg.raw).getDataRange().getValues();
  var rs = currentReturnFilter_(sh.getName());
  writeView_(computeView_(raw[0], raw.slice(1), spec.layout, spec.t2_cap_date, spec.generated_at, rs === 'All' ? null : rs), sh.getName());
}

function installDailyTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'refreshAll') ScriptApp.deleteTrigger(t);
  });
  // The refresh session pushes in the evening IST; a morning pull picks it up. raw.githubusercontent
  // caches for ~5 minutes, so a manual refresh right after a push may show the previous version.
  ScriptApp.newTrigger('refreshAll').timeBased().everyDays(1).atHour(7).inTimezone('Asia/Kolkata').create();
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

function writeRaw_(exp, tab) {
  var sh = sheet_(tab || RAW_TAB);
  sh.clear();
  var cols = exp.columns;
  var values = [cols].concat(exp.rows);
  var dateCol = cols.indexOf('Created date') + 1;
  sh.getRange(1, dateCol, values.length, 1).setNumberFormat('@'); // keep ISO dates as text
  sh.getRange(1, 1, values.length, cols.length).setValues(values);
  sh.getRange(1, 1, 1, cols.length).setFontWeight('bold').setBackground('#1f2937').setFontColor('#ffffff');
  sh.setFrozenRows(1);
  sh.setFrozenColumns(2);
  if (sh.getFilter()) sh.getFilter().remove();
  sh.getRange(1, 1, values.length, cols.length).createFilter();
  sh.autoResizeColumns(1, cols.length);
}

function writeView_(t, tab, noFilter) {
  var sh = sheet_(tab || VIEW_TAB);
  sh.setTabColor(VIEW_TAB_COLOR);
  var keep = RET_OPTIONS.indexOf(sh.getRange(FILTER_CELL).getValue()) >= 0 ? sh.getRange(FILTER_CELL).getValue() : 'All';
  sh.clear();
  if (noFilter) {
    sh.getRange('A1').setValue('No filter - the return-request outcome is shown as rows. Window: last 60 days.').setFontStyle('italic');
  } else {
    sh.getRange('A1').setValue('Return request filter (applies to the whole table):').setFontWeight('bold');
    sh.getRange(FILTER_CELL).setValue(keep).setBackground('#fff3cd').setFontWeight('bold')
      .setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(RET_OPTIONS, true).build());
  }
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

function writeInfo_(exp, trend) {
  var sh = sheet_(INFO_TAB);
  sh.clear();
  var info = [
    ['Data generated (UTC)', exp.generated_at],
    ['T-2 cap date (last complete day in the RCA view)', trend.t2_cutoff],
    ['Newer tickets held back from the view', trend.excluded_tickets],
    ['Orders in Raw data', exp.rows.length],
    ['Sheet refreshed', new Date()],
    ['Source', EXPORT_URL],
    ['', ''],
    ['How to read', 'Raw data = one row per order, first ticket wins (same rule as the website tile). RCA view cells are "count | % of parent row".'],
    ['Evidence', 'Photo-derived buckets are capped at "Likely"; accuracy builds over time. Cold-chain damaged tickets are not photo-read.']
  ];
  sh.getRange(1, 1, info.length, 2).setValues(info);
  sh.getRange(1, 1, info.length, 1).setFontWeight('bold');
  sh.setColumnWidth(1, 360);
  sh.setColumnWidth(2, 640);
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
