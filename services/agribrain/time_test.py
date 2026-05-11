import requests, time
t = time.time()
r = requests.post('http://127.0.0.1:8000/v2/plot-intelligence', json={'lat':36.0,'lng':3.0}, timeout=40)
elapsed = time.time()-t
d = r.json()
eng_ok = sum(1 for e in d.get('engines',[]) if e['status']=='OK')
print(f"HTTP {r.status_code} | {elapsed:.1f}s | success={d.get('success')} | engines {eng_ok}/{len(d.get('engines',[]))} OK")
print(f"Sources: {d.get('assimilation',{}).get('sources_used')}")
for e in d.get('engines', []):
    dot = "OK" if e['status']=='OK' else "DEGRADED"
    print(f"  [{e['id']}] {dot} — {e['statusLabel']}: {e['summary'][:60]}")
