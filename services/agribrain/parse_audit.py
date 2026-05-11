import json
data = json.load(open('season_audit.json'))
for p_id, history in data.items():
    print(f'=== {p_id} ===')
    for d in history:
        # Print every 20 days or if Transpiration Failure is detected
        if d['day'] % 20 == 0 or 'TRANSPIRATION_FAILURE' in d['l3_diagnoses']:
            print(f"Day {d['day']} ({d['stage']}): LST={d['l0_lst']}, T_air={d['l1_t_air']}, Delta={d['l3_delta_t']}, ESI={d['l3_esi']} -> Diags: {d['l3_diagnoses']} -> Actions: {d['l3_actions']}")
