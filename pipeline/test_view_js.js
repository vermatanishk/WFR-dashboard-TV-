// Run: node pipeline/test_view_js.js
// Evaluates gsheet/Code.gs computeView_() on rca_export.json + rca_view_spec.json for All AND each return state
// and compares EVERY cell with rca_trend.json (which Python produced from the same export).
const fs = require('fs'), path = require('path');
const dir = __dirname;
const PRE = { swap: ['swap_export', 'swap_view_spec', 'swap_trend'], wfr: ['cmp_wfr_export', 'cmp_wfr_view_spec', 'cmp_wfr_trend'], damage: ['cmp_damage_export', 'cmp_damage_view_spec', 'cmp_damage_trend'] };
const pre = PRE[process.argv[2]] || ['rca_export', 'rca_view_spec', 'rca_trend']; // node test_view_js.js [swap|wfr|damage]
const src = fs.readFileSync(path.join(dir, 'gsheet', 'Code.gs'), 'utf8');
const sandbox = {};
new Function('sandbox', src + '\nsandbox.computeView_ = computeView_;')(sandbox);
const exp = JSON.parse(fs.readFileSync(path.join(dir, pre[0] + '.json'), 'utf8'));
const spec = JSON.parse(fs.readFileSync(path.join(dir, pre[1] + '.json'), 'utf8'));
const trend = JSON.parse(fs.readFileSync(path.join(dir, pre[2] + '.json'), 'utf8'));
let bad = 0, cells = 0;
const variants = [[null, trend]].concat(Object.keys(trend.by_return).map(k => [k, trend.by_return[k]]));
variants.forEach(([rs, want]) => {
  const got = sandbox.computeView_(exp.columns, exp.rows, spec.layout, exp.t2_cap_date, exp.generated_at, rs, trend.days);
  if (JSON.stringify(got.days) !== JSON.stringify(want.days)) { console.log('DAYS DIFFER', rs); bad++; }
  if (got.rows.length !== want.rows.length) { console.log('ROW COUNT DIFFERS', rs); bad++; }
  want.rows.forEach((w, i) => {
    const g = got.rows[i];
    if (!g || g.label !== w.label || g.key !== w.key) { console.log('LABEL/KEY', rs, i); bad++; return; }
    ['3mo', '1mo', '2wk'].forEach(k => { cells++; if (g[k].text !== w[k].text) { console.log('DIFF', rs, w.label, k, g[k].text, w[k].text); bad++; } });
    want.days.forEach(d => { cells++; if (g.daily[d].text !== w.daily[d].text) { if (bad < 15) console.log('DIFF', rs, w.label, d); bad++; } });
  });
  if (got.excluded_tickets !== want.excluded_tickets) { console.log('EXCLUDED', rs, got.excluded_tickets, want.excluded_tickets); bad++; }
});
console.log(`JS evaluator vs ${pre[2]}.json: ${cells} cells compared across ${variants.length} variants, ${bad} differences`);
process.exit(bad ? 1 : 0);
