// Run: node pipeline/test_view_js.js
// Evaluates gsheet/Code.gs computeView_() on rca_export.json + rca_view_spec.json and compares EVERY cell with
// rca_trend.json (which Python produced from the same export). Fails loudly on any difference.
const fs = require('fs'), path = require('path');
const dir = __dirname;
const src = fs.readFileSync(path.join(dir, 'gsheet', 'Code.gs'), 'utf8');
const sandbox = {};
new Function('sandbox', src + '\nsandbox.computeView_ = computeView_;')(sandbox);
const exp = JSON.parse(fs.readFileSync(path.join(dir, 'rca_export.json'), 'utf8'));
const spec = JSON.parse(fs.readFileSync(path.join(dir, 'rca_view_spec.json'), 'utf8'));
const want = JSON.parse(fs.readFileSync(path.join(dir, 'rca_trend.json'), 'utf8'));
const got = sandbox.computeView_(exp.columns, exp.rows, spec.layout, exp.t2_cap_date, exp.generated_at);
let bad = 0, cells = 0;
if (JSON.stringify(got.days) !== JSON.stringify(want.days)) { console.log('DAYS DIFFER'); bad++; }
if (got.rows.length !== want.rows.length) { console.log('ROW COUNT DIFFERS', got.rows.length, want.rows.length); bad++; }
want.rows.forEach((w, i) => {
  const g = got.rows[i];
  if (!g || g.label !== w.label) { console.log('LABEL', i, g && g.label, '|', w.label); bad++; return; }
  ['3mo', '1mo', '2wk'].forEach(k => { cells++; if (g[k].text !== w[k].text) { console.log('DIFF', w.label, k, g[k].text, w[k].text); bad++; } });
  want.days.forEach(d => { cells++; if (g.daily[d].text !== w.daily[d].text) { if (bad < 15) console.log('DIFF', w.label, d, g.daily[d].text, w.daily[d].text); bad++; } });
});
if (got.excluded_tickets !== want.excluded_tickets) { console.log('EXCLUDED', got.excluded_tickets, want.excluded_tickets); bad++; }
console.log(`JS evaluator vs rca_trend.json: ${cells} cells compared, ${bad} differences`);
process.exit(bad ? 1 : 0);
