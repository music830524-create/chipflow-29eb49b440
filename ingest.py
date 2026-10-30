"""Sort raw ToAlpha MCP result files (saved with write_to_file) into toalpha_in/<tool>_<sid>.json.
usage: python3 ingest.py <dir-with-saved-results> [--since-minutes N]
Detects tool by JSON keys; stock id read from the content itself (no manual mapping needed)."""
import json, sys, os, glob, time
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'toalpha_in')
os.makedirs(OUT, exist_ok=True)
def load(p):
    t = open(p, encoding='utf-8').read()
    try: j, _ = json.JSONDecoder().raw_decode(t[t.index('{'):])
    except Exception: return None
    return j
def main():
    d = sys.argv[1]
    since = time.time() - 60 * int(sys.argv[sys.argv.index('--since-minutes') + 1]) if '--since-minutes' in sys.argv else 0
    n = 0
    for p in glob.glob(os.path.join(d, '*.txt')):
        if os.path.getmtime(p) < since: continue
        j = load(p)
        if not isinstance(j, dict): continue
        sid = (j.get('stock') or {}).get('id')
        name = None
        if 'ratings' in j and sid: name = f'broker_ratings_{sid}'
        elif 'rows' in j and sid and 'summary' not in j: name = f'financials_{sid}'
        elif 'calls' in j and sid: name = f'conference_calls_{sid}'
        elif 'items' in j and 'stock_ids' in j: name = 'news_' + os.path.basename(p)[:8]
        elif 'events' in j and j['events'] and all(e.get('event') == '法說會' for e in j['events']): name = 'calendar_conf'
        else: continue
        json.dump(j, open(os.path.join(OUT, name + ('.txt' if name.startswith(('news_', 'calendar')) else '.json')), 'w', encoding='utf-8'), ensure_ascii=False)
        n += 1
    print('ingested', n)
main()
