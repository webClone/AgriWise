import { test } from "node:test";
import assert from "node:assert/strict";

import {
  beginHistoricalSelection,
  createInitialHistoricalDisplayState,
  formatDisplayIdentityToken,
  resetHistoricalToLive,
  resolveHistoricalFailure,
  resolveHistoricalSuccess,
} from "../../src/lib/agribrain/historical-display-identity.mjs";

function makeResp(plotId, asOfDate, version, geomHash = "sha256:g1") {
  return {
    available: true,
    plot_id: plotId,
    geometry_hash: geomHash,
    archive_state_version: version,
    as_of_date: asOfDate,
    valid_time_T: `${asOfDate}T23:59:59+00:00`,
    knowledge_cutoff_K: "2026-11-26T00:00:00+00:00",
  };
}

test("Atomic Historical Display Identity: 2026 -> delayed 2018 -> 2021 -> stale 2018 -> failed request never disagrees", () => {
  const plotId = "6a09d9e91dd0c7ed6fce7d50";
  const geomHash = "sha256:g1";

  // 1. Start on 2026-09-01 and commit
  let st = createInitialHistoricalDisplayState();
  st = beginHistoricalSelection(st, "2026-09-01");
  const gen2026 = st.requestGeneration;
  st = resolveHistoricalSuccess(st, {
    generation: gen2026,
    plotId,
    geometryHash: geomHash,
    activeSurfaceKey: "vigor",
    data: makeResp(plotId, "2026-09-01", "v_2026", geomHash),
  });
  assert.equal(st.committed?.identity.validTimeT.slice(0, 10), "2026-09-01");
  assert.match(formatDisplayIdentityToken(st, plotId, "vigor"), /2026-09-01/);

  // 2. User switches to 2018-07-15 (slow/delayed) -> committed MUST clear immediately (no stale 2026 raster under 2018 label!)
  st = beginHistoricalSelection(st, "2018-07-15");
  const gen2018 = st.requestGeneration;
  assert.equal(st.loading, true);
  assert.equal(st.committed, null);
  assert.match(formatDisplayIdentityToken(st, plotId, "vigor"), /^loading\|/);

  // 3. Before 2018 arrives, user switches to 2021-04-15 and 2021 resolves
  st = beginHistoricalSelection(st, "2021-04-15");
  const gen2021 = st.requestGeneration;
  st = resolveHistoricalSuccess(st, {
    generation: gen2021,
    plotId,
    geometryHash: geomHash,
    activeSurfaceKey: "canopy_water",
    data: makeResp(plotId, "2021-04-15", "v_2021", geomHash),
  });
  assert.equal(st.committed?.identity.validTimeT.slice(0, 10), "2021-04-15");
  assert.equal(st.committed?.identity.responseGeneration, gen2021);

  // 4. Delayed 2018 response finally resolves -> MUST NOT overwrite 2021!
  st = resolveHistoricalSuccess(st, {
    generation: gen2018,
    plotId,
    geometryHash: geomHash,
    activeSurfaceKey: "vigor",
    data: makeResp(plotId, "2018-07-15", "v_2018", geomHash),
  });
  assert.equal(st.committed?.identity.validTimeT.slice(0, 10), "2021-04-15");
  assert.equal(st.committed?.identity.responseGeneration, gen2021);

  // 5. User selects 2018 again and that request fails -> old 2021 raster MUST NOT stay active
  st = beginHistoricalSelection(st, "2018-07-15");
  st = resolveHistoricalFailure(st, { generation: st.requestGeneration, errorMessage: "HTTP 503" });
  assert.equal(st.loading, false);
  assert.equal(st.error, "HTTP 503");
  assert.equal(st.committed, null);
  assert.match(formatDisplayIdentityToken(st, plotId, "vigor"), /^withheld\|/);

  // 6. Geometry mismatch in response fails closed cleanly
  st = beginHistoricalSelection(st, "2021-04-15");
  st = resolveHistoricalSuccess(st, {
    generation: st.requestGeneration,
    plotId,
    geometryHash: geomHash,
    activeSurfaceKey: "vigor",
    data: makeResp(plotId, "2021-04-15", "v_2021", "sha256:stale_geom"),
  });
  assert.equal(st.committed, null);
  assert.match(st.error || "", /geometry hash mismatch/i);

  // 7. Return to Live clears requested date and increments generation
  st = resetHistoricalToLive(st);
  assert.equal(st.requestedAsOfDate, null);
  assert.equal(st.committed, null);
  assert.match(formatDisplayIdentityToken(st, plotId, "vigor"), /^live\|/);
});
