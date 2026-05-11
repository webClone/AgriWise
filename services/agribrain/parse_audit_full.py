import json
data = json.load(open('full_season_audit.json'))
for p_id, history in data.items():
    print(f'=== {p_id} ===')
    triggered = set()
    for d in history:
        for diag in d['diags']:
            if diag not in triggered:
                print(f"Day {d['day']} ({d['stage']}): NEW DIAGNOSIS -> {diag} | Actions: {d['actions']}")
                triggered.add(diag)
