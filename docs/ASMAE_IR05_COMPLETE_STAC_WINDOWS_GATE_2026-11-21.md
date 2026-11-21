# ASMAE IR05 archive lane — complete STAC pagination and exact windows

Status: implementation candidate, qualification HOLD. Base: provider truthfulness branch @ `c803113`, itself descended from `ad3fc57`.

## Implementation
- STAC search exhausts GET/POST `rel=next` links with bounded pagination and same-origin HTTPS enforcement. Rejects pagination loops, off-origin links, missing links when matched count proves more results, and full pages without completeness evidence.
- Catalog unavailable/offline returns explicit error, never an empty successful interval.
- Partitioned queries preserve exact UTC half-open `[start,end)` windows across month boundaries; item timestamps are interpreted in UTC and endpoint-inclusive duplicate observations are filtered.
- Malformed scene metadata and unknown source scopes fail closed. Product level is never fabricated as L2A/GRD merely because the source is Sentinel.
- Archive download planner's `success=True` but quota-truncated scene lists are rejected as incomplete before bootstrap checkpoint advancement.
- Added 14 offline adversarial HTTP/partition/quota tests. All are **authored only**, not executed in this review.

## Still open
True CDSE STAC integration, verified assets, 2015+ complete archive coverage, selective late-data replays, real 13-state historical assimilation and posterior uncertainty, and interactive native statewise maps. The bridge remains inventory-only and the 1m/numerical publishing holds stay active.

## Acceptance
Run `pytest services/agribrain/layer0/tests/test_ir05_stac_window_completeness.py -q`, IR05/Gate B, full Layer0/Layer05 and frontend regressions. Test live pagination, storage quotas, invalid dates, month boundary overlap, late arrivals and full-archive first-open then incrementality at exact SHA. Do not treat 14 new offline tests as real-provider proof.
