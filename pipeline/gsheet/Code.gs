/**
 * WFR RCA live sheet - pulls two JSON files from the public GitHub repo and rebuilds two tabs:
 *   "Raw data"  - one row per order (trailing 90 days): order, ticket, issue, investigation buckets,
 *                 raised buckets, evidence.            <- pipeline/rca_export.json
 *   "RCA view"  - the day-wise RCA table of the website's Tab 7.   <- pipeline/rca_trend.json
 * Both files are rebuilt and pushed by the daily refresh session, so the sheet follows git.
 *
 * Setup: see README.md in this folder (paste this file into Extensions > Apps Script, run refreshAll once,
 * then run installDailyTrigger once).
 */

var BASE = 'https://raw.githubusercontent.com/vermatanishk/WFR-dashboard-TV-/main/pipeline/';
var EXPORT_URL = BASE + 'rca_export.json';
var TREND_URL = BASE + 'rca_trend.json';
var RAW_TAB = 'Raw data';
var VIEW_TAB = 'RCA view';
var INFO_TAB = 'Info';

function onOpen() {
  SpreadsheetApp.getUi().createMenu('WFR RCA')
    .addItem('Refresh now', 'refreshAll')
    .addItem('Install daily refresh (07:00 IST)', 'installDailyTrigger')
    .addToUi();
}

function refreshAll() {
  var exp = fetchJson_(EXPORT_URL);
  var trend = fetchJson_(TREND_URL);
  writeRaw_(exp);
  writeView_(trend);
  writeInfo_(exp, trend);
  SpreadsheetApp.getActive().toast('RCA data refreshed (' + exp.rows.length + ' orders)', 'WFR RCA', 5);
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

function writeRaw_(exp) {
  var sh = sheet_(RAW_TAB);
  sh.clear();
  var cols = exp.columns;
  var values = [cols].concat(exp.rows);
  sh.getRange(1, 1, values.length, cols.length).setValues(values);
  // order id and ticket id as plain numbers/text, date as text so it sorts as ISO
  sh.getRange(1, 1, 1, cols.length).setFontWeight('bold').setBackground('#1f2937').setFontColor('#ffffff');
  sh.setFrozenRows(1);
  sh.setFrozenColumns(2);
  if (sh.getFilter()) sh.getFilter().remove();
  sh.getRange(1, 1, values.length, cols.length).createFilter();
  sh.autoResizeColumns(1, cols.length);
}

function writeView_(t) {
  var sh = sheet_(VIEW_TAB);
  sh.clear();
  var days = t.days.slice().reverse(); // most recent first, same as the website
  var head = ['Metric', '3 month total', 'Last month total', 'Last 2 weeks total'].concat(days.map(function (d) { return t.day_labels[d]; }));
  var rows = t.rows.map(function (r) {
    var label = new Array((r.indent || 0) * 3 + 1).join(' ') + r.label + (r.sub ? '  (' + r.sub + ')' : '');
    return [label, r['3mo'].text, r['1mo'].text, r['2wk'].text].concat(days.map(function (d) { return r.daily[d].text; }));
  });
  var values = [head].concat(rows);
  sh.getRange(1, 1, values.length, head.length).setValues(values);
  sh.getRange(1, 1, 1, head.length).setFontWeight('bold').setBackground('#1f2937').setFontColor('#ffffff');
  t.rows.forEach(function (r, i) {
    if (r.kind === 'wfr_pto') {
      sh.getRange(i + 2, 1, 1, head.length).setFontWeight('bold').setBackground('#fff3cd');
    }
  });
  sh.setFrozenRows(1);
  sh.setFrozenColumns(4);
  sh.setColumnWidth(1, 420);
  sh.getRange(1, 2, values.length, head.length - 1).setHorizontalAlignment('right');
  sh.getRange(2, 1, rows.length, head.length).setFontSize(10);
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
