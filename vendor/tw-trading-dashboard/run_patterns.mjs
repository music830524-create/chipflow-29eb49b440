// 讀 stdin 的 JSON → 對每檔呼叫 detectPatterns（逐字沿用 tw-trading-dashboard 的型態辨識）→ 輸出 JSON。
// MIT License, Copyright (c) 2026 EquiLens contributors — https://github.com/wakin61043/tw-trading-dashboard
import { detectPatterns, PATTERNS } from './patterns.mjs';
let buf = '';
process.stdin.setEncoding('utf8');
for await (const c of process.stdin) buf += c;
const inp = JSON.parse(buf), out = [];
const mk = (dates, rows) => rows.map((r, i) => ({ date: dates[i], open: r[0], max: r[1], min: r[2], close: r[3], Trading_Volume: r[4] }));
for (const s of inp.stocks) {
  try {
    const a = mk(inp.dates, s.a), p = mk(inp.dates, s.p);
    const m = detectPatterns(a, p, {});
    if (m.length) out.push({ id: s.id, matches: m.map(x => ({ id: x.id, name: x.name, category: x.category, score: x.score, status: x.status, start: x.start, end: x.end, breakoutDate: x.breakoutDate, description: x.description, anchors: x.anchors, resistance: x.resistance, support: x.support, atr: x.atr, volumeRatio: x.volumeRatio, scoreParts: x.scoreParts, lines: x.lines, plan: x.plan, warnings: x.warnings })) });
  } catch (e) { process.stderr.write(`skip ${s.id}: ${e.message}\n`); }
}
process.stdout.write(JSON.stringify({ types: PATTERNS, hits: out }));
