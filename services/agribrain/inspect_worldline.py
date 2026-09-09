import json
from pathlib import Path

def inspect_plot(pdir_path):
    pdir = Path(pdir_path)
    head_file = pdir / 'head.json'
    head = json.loads(head_file.read_text(encoding='utf-8'))
    events = sorted((pdir / 'events').glob('*.json'), key=lambda x: int(json.loads(x.read_text(encoding='utf-8')).get('sequence', 0)))
    
    print(f"================================================================")
    print(f"AGRONOMIC WORLDLINE INSPECTION: PLOT {head.get('plot_id')}")
    print(f"Tenant: {head.get('tenant_id')} | Namespace: {head.get('namespace')}")
    print(f"Total Lifecycle Events: {head.get('sequence')}")
    print(f"================================================================")
    
    for ev_path in events:
        ev = json.loads(ev_path.read_text(encoding='utf-8'))
        seq = ev.get('sequence')
        etype = ev.get('event_type')
        auth = ev.get('authority')
        eff = ev.get('effective_at')
        payload = ev.get('payload', {})
        
        print(f"\n--- [Event #{seq}] {etype} | Date: {eff} | Authority: {auth} ---")
        
        if etype == 'CROP_POSTERIOR':
            cp = payload.get('crop_posterior', {})
            print(f"  [Crop Identity]: {cp.get('crop_name', cp.get('declared_crop', 'N/A'))} (Confidence: {cp.get('confidence', cp.get('probability', 'N/A'))})")
            if 'crop_features' in cp:
                print(f"  [Features]: {cp.get('crop_features')}")
                
        elif etype == 'PHENOLOGY_POSTERIOR':
            pp = payload.get('phenology_posterior', {})
            print(f"  [Phenology Stage]: {pp.get('current_stage', pp.get('stage', 'N/A'))} (BBCH: {pp.get('bbch_scale', 'N/A')}) | Progress: {pp.get('progress_fraction', 'N/A')}")
            print(f"  [GDD Thermal Accumulation]: {pp.get('accumulated_gdd', 'N/A')} °C-days")
            
        elif etype == 'CURRENT_POSTERIOR_DIAGNOSTIC' or etype == 'CURRENT_POSTERIOR_VALIDATED':
            psa = payload.get('plot_state_artifact', {})
            states = psa.get('states', {})
            print(f"  [Biophysical Assimilation (ASMAE)]:")
            for state_name, val in list(states.items())[:6]:
                print(f"    - {state_name}: {val.get('mean') if isinstance(val, dict) else val}")
                
        elif etype == 'ASMAE_SPATIAL_DIAGNOSTIC_COMPLETED':
            print(f"  [Microzone Spatial Diagnostic]:")
            print(f"    - Execution Status: {payload.get('execution_status')}")
            print(f"    - Production Usable: {payload.get('production_usable')}")
            print(f"    - Spatial Available: {payload.get('spatial_available')}")
            print(f"    - ASMAE Content Digest: {str(payload.get('asmae_content_hash'))[:24]}...")
            
        elif etype == 'ARCHIVE_ACQUISITION_PLAN':
            print(f"  [Sensor Acquisition Trigger]: {payload.get('reason')} (Sources: {payload.get('requested_sources')})")
            
        elif etype == 'CANONICAL_PLOT_SNAPSHOT':
            print(f"  [Consolidated Snapshot Commit]:")
            print(f"    - Snapshot ID: {payload.get('snapshot_id')}")
            print(f"    - Layer Executions: {payload.get('layer_run_ids')}")

if __name__ == '__main__':
    inspect_plot('services/agribrain/artifacts/plot_worldlines/697ddd3bd4195b809226a67b/697ddd3bd4195b809226a680/a8e2a6f3c70d8796a9992591d4395ffe')
