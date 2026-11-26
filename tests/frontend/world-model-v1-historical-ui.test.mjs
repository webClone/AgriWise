import { test } from "node:test";
import assert from "node:assert/strict";
import { summarizeWorldModelV1View } from "../../src/lib/agribrain/historical-world-model-view.mjs";

test("World Model V1 UI summary preserves unverified crop identity, synthetic rejection, and exploratory tag", () => {
  const unverifiedView = summarizeWorldModelV1View({
    domain_identity: {
      resolved_crop_code: "unknown",
      crop_identity_verified: false,
      tenant_identity_verified: false,
      synthetic_label_rejected: true,
      soil_texture: "sandy",
    },
    crop_context_as_of: {
      crop: "unknown",
      crop_identity_verified: false,
      physical_regime: "UNVERIFIED_CROP_REGIME",
      unknown_probability: 0.72,
    },
    crop_identity_timeline: [{ top_group: "cereal", unknown_probability: 0.72 }],
    retrovalidation_summary: {
      exploratory_by_horizon: {
        exploratory_36_90d: { n: 24, skill_vs_persistence: 0.14, joint_forecast_rmse: 0.068 },
      },
      scientific_failure_diagnosis: {
        primary_cause: "unverified_domain_identity",
        recommended_evidence_to_unblock: ["Populate a verified non-synthetic CropCycle record."],
      },
    },
  });

  assert.equal(unverifiedView.cropVerified, false);
  assert.equal(unverifiedView.cropBadgeLabel, "Unverified Crop (EO Group Posterior Only)");
  assert.equal(unverifiedView.tenantLabel, "Isolated Dev Fixture");
  assert.equal(unverifiedView.syntheticRejected, true);
  assert.equal(unverifiedView.asOfCropLabel, "unknown / EO mixture");
  assert.equal(unverifiedView.unknownMassPct, 72);
  assert.equal(unverifiedView.exploratory36_90d?.exploratoryOnly, true);
  assert.equal(unverifiedView.primaryFailureCause, "unverified_domain_identity");

  const verifiedView = summarizeWorldModelV1View({
    domain_identity: {
      resolved_crop_code: "citrus",
      crop_identity_verified: true,
      tenant_identity_verified: true,
      synthetic_label_rejected: false,
    },
    crop_context_as_of: {
      crop: "citrus",
      crop_identity_verified: true,
      physical_regime: "ACTIVE_FRUITING",
      unknown_probability: 0.01,
    },
  });
  assert.equal(verifiedView.cropVerified, true);
  assert.equal(verifiedView.cropBadgeLabel, "Verified CropCycle: citrus");
  assert.equal(verifiedView.tenantLabel, "Verified");
  assert.equal(verifiedView.asOfCropLabel, "citrus");
});
