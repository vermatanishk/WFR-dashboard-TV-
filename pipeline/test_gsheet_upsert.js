// Run: node pipeline/test_gsheet_upsert.js
// Proves the Google-Sheet raw tabs are NON-DESTRUCTIVE: upsertRaw_() in gsheet/Code.gs against a mock sheet.
//   * a row that already sits in the tab but is no longer in the export (out of the 60-day window) is kept
//   * an archive row missing from the tab is added, an archive row already in the tab is not overwritten by older data
//   * an export row refreshes the existing row in place (blank export values keep the old value) and new rows are appended
//   * a column that only exists in the tab (user note) and a new export column are both kept (appended at the right)
const fs = require('fs'), path = require('path');
const src = fs.readFileSync(path.join(__dirname, 'gsheet', 'Code.gs'), 'utf8');

function mockSheet(initial) {
  const sh = { grid: initial.map(r => r.slice()), frozen: 0 };
  sh.getLastRow = () => sh.grid.length;
  sh.getDataRange = () => ({ getValues: () => sh.grid.map(r => r.slice()) });
  sh.getMaxColumns = () => 100; sh.getMaxRows = () => 100000;
  sh.insertColumnsAfter = () => {}; sh.insertRowsAfter = () => {};
  sh.getRange = (r, c, nr, nc) => ({
    setNumberFormat() { return this; }, setFontWeight() { return this; }, setBackground() { return this; }, setFontColor() { return this; },
    createFilter() { return this; },
    setValues(v) { sh.grid = v.map(x => x.slice()); return this; },
  });
  sh.setFrozenRows = () => {}; sh.setFrozenColumns = () => {};
  sh.getFilter = () => null;
  return sh;
}

const tab = mockSheet([
  ['Order ID', 'Created date', 'Complaint type', 'Status', 'My note'],
  [1, '2026-07-01', 'Damage', 'old-window row', 'keep me'],        // fell out of every export: must survive
  [2, '2026-11-10', 'Damage', 'accepted', ''],                     // in the export: refreshed
  [3, '2026-09-01', 'Expiry', 'archived-in-sheet', 'x'],           // also in archive with older data: sheet copy wins
]);
const sandbox = {};
new Function('sandbox', 'SpreadsheetApp', 'Utilities', src + '\nsandbox.upsertRaw_ = upsertRaw_;')(sandbox, { getActive: () => ({ getSheetByName: () => tab, insertSheet: () => tab }) }, {});
const exp = { columns: ['Order ID', 'Created date', 'Complaint type', 'Status', 'New col'], rows: [
  [2, '2026-11-10', 'Damage', 'refunded', 'n1'],
  [4, '2026-11-18', 'Damage', 'new', 'n2'],
  [5, '2026-11-18', 'Damage', '', 'n3'],
] };
const arch = { columns: ['Order ID', 'Created date', 'Complaint type', 'Status'], rows: [
  [3, '2026-09-01', 'Expiry', 'older archive value'],
  [6, '2026-06-30', 'Damage', 'archive only'],
] };
const n = sandbox.upsertRaw_('t', exp, arch, ['Order ID', 'Complaint type']);
const g = tab.grid, H = g[0], rows = g.slice(1);
const col = c => H.indexOf(c);
let bad = 0;
function check(name, ok) { console.log((ok ? 'PASS ' : 'FAIL ') + name); if (!ok) bad++; }
const byId = id => rows.find(r => String(r[0]) === String(id));
check('row count = union of tab, archive and export (6 distinct orders)', n === 6 && rows.length === 6);
check('out-of-window row kept with its user note', byId(1) && byId(1)[col('My note')] === 'keep me' && byId(1)[col('Status')] === 'old-window row');
check('export refreshes an existing row in place', byId(2)[col('Status')] === 'refunded' && byId(2)[col('New col')] === 'n1');
check('sheet copy is not overwritten by older archive data', byId(3)[col('Status')] === 'archived-in-sheet' && byId(3)[col('My note')] === 'x');
check('archive-only row is restored', byId(6) && byId(6)[col('Status')] === 'archive only');
check('new export row appended', byId(4) && byId(4)[col('Status')] === 'new');
check('new export column appended at the right, user column kept', H[H.length - 1] === 'New col' && H.indexOf('My note') >= 0 && H.indexOf('My note') < H.indexOf('New col'));
check('sorted newest day first', rows[0][col('Created date')] >= rows[rows.length - 1][col('Created date')]);
// second run is idempotent
const before = JSON.stringify(tab.grid);
sandbox.upsertRaw_('t', exp, arch, ['Order ID', 'Complaint type']);
check('re-running changes nothing (idempotent)', JSON.stringify(tab.grid) === before);
process.exit(bad ? 1 : 0);
