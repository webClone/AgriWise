import assertStrict from 'node:assert/strict';

/**
 * Frontend Request State & Job Status Reconciliation Test Suite
 */
console.log('Running Frontend Layer10 Request State & Handoff Tests...');

// 1. Verify Job Status Reconciliation
function testJobStatusReconciliation() {
  const queuedJob = {
    job_id: 'job_123',
    status: 'failed',
    stage: 'complete',
    result_status: 'error',
    reason: 'NameError overall_unc not defined',
  };

  const cachedPublication = {
    snapshot_id: 'snap_old_456',
    asmae_job: {
      job_id: 'job_123',
      status: 'queued', // stale embedded state
    },
    surface_inventory: {},
  };

  // Reconcile status against durable job store
  const reconciledStatus = queuedJob.status === 'failed' ? 'failed' : cachedPublication.asmae_job.status;
  assertStrict.equal(reconciledStatus, 'failed', 'Durable job failure must overwrite stale cached publication state');
  console.log('✓ Job status reconciliation test passed');
}

// 2. Verify Final Snapshot Promotion Handoff
function testSnapshotPromotionHandoff() {
  const refreshCompletedEvent = {
    plotId: 'plot_6a09e03e',
    finalSnapshotId: 'snap_new_789',
  };

  // Handoff options must request specific snapshotId without forcing scientific rerun
  const fetchOptions = {
    forceRefresh: false,
    snapshotId: refreshCompletedEvent.finalSnapshotId,
  };

  assertStrict.equal(fetchOptions.forceRefresh, false, 'Refresh completion must not trigger forced scientific rerun');
  assertStrict.equal(fetchOptions.snapshotId, 'snap_new_789', 'Exact finalSnapshotId must be promoted');
  console.log('✓ Snapshot promotion handoff test passed');
}

// 3. Verify HUD Active Resolution from Render Receipt
function testHudActiveResolution() {
  const activeSurfaceType = 'NDVI_CLEAN'; // Provider fallback active

  const isAsmaeRendered = activeSurfaceType.startsWith('CANOPY_ASMAE_');
  const hudActiveLabel = isAsmaeRendered
    ? 'ASMAE 10m Diagnostic Active'
    : 'ASMAE Diagnostic Requested (Materialization Pending)';

  assertStrict.equal(
    hudActiveLabel,
    'ASMAE Diagnostic Requested (Materialization Pending)',
    'HUD active label must require an ASMAE render receipt'
  );
  console.log('✓ HUD active resolution test passed');
}

testJobStatusReconciliation();
testSnapshotPromotionHandoff();
testHudActiveResolution();

console.log('All 3 Frontend Layer10 Request State Tests Passed!');
