/* ═══ AgriWise Canonical ScaleStoryLayout Model ══════════════════
   Single Source of Truth for DOM narrative positioning, WebGL timeline
   pacing, chapter navigation, and telemetry analytics.
   ═══════════════════════════════════════════════════════════════ */

export interface StoryStageLayout {
  id: "field" | "farm" | "organization" | "region" | "nation";
  num: string;
  label: string;
  micro: string;
  title: string;
  side: "left" | "right" | "center";
  holdStart: number; // 0..1 normalized scroll progress
  holdEnd: number;   // 0..1 normalized scroll progress
  narrativeCenter: number; // center of hold for DOM element placement
  isClimax?: boolean;
}

export interface ScaleStoryLayoutModel {
  totalHeightVh: number;
  stages: StoryStageLayout[];
}

export const SCALE_PACING = {
  fieldHold: 0.16,
  fieldToFarm: 0.12,
  farmHold: 0.14,
  farmToOrganization: 0.12,
  organizationHold: 0.14,
  organizationToRegion: 0.12,
  regionHold: 0.12,
  regionToNation: 0.14,
  nationHold: 0.24,
};

export function compileScaleStoryLayout(): ScaleStoryLayoutModel {
  const totalWeight = Object.values(SCALE_PACING).reduce((a, b) => a + b, 0);

  const fHold = SCALE_PACING.fieldHold / totalWeight;
  const fToFarm = SCALE_PACING.fieldToFarm / totalWeight;
  const farmH = SCALE_PACING.farmHold / totalWeight;
  const farmToOrg = SCALE_PACING.farmToOrganization / totalWeight;
  const orgH = SCALE_PACING.organizationHold / totalWeight;
  const orgToReg = SCALE_PACING.organizationToRegion / totalWeight;
  const regH = SCALE_PACING.regionHold / totalWeight;
  const regToNat = SCALE_PACING.regionToNation / totalWeight;
  const natH = SCALE_PACING.nationHold / totalWeight;

  const fieldStart = 0;
  const fieldEnd = fHold;

  const farmStart = fieldEnd + fToFarm;
  const farmEnd = farmStart + farmH;

  const orgStart = farmEnd + farmToOrg;
  const orgEnd = orgStart + orgH;

  const regStart = orgEnd + orgToReg;
  const regEnd = regStart + regH;

  const natStart = regEnd + regToNat;
  const natEnd = natStart + natH;

  const stages: StoryStageLayout[] = [
    {
      id: "field",
      num: "01",
      label: "ONE FIELD",
      micro: "ILLUSTRATIVE PARCEL · PLOT-017",
      title: "One field becomes a living intelligence object.",
      side: "left",
      holdStart: fieldStart,
      holdEnd: fieldEnd,
      narrativeCenter: (fieldStart + fieldEnd) / 2,
    },
    {
      id: "farm",
      num: "02",
      label: "ITS FARM",
      micro: "FARM CLUSTER · FARM-04",
      title: "Related parcels become one operational system.",
      side: "right",
      holdStart: farmStart,
      holdEnd: farmEnd,
      narrativeCenter: (farmStart + farmEnd) / 2,
    },
    {
      id: "organization",
      num: "03",
      label: "ORGANIZATION",
      micro: "NETWORKED AGGREGATION · PORTFOLIO-02",
      title: "Farms become one organizational picture.",
      side: "left",
      holdStart: orgStart,
      holdEnd: orgEnd,
      narrativeCenter: (orgStart + orgEnd) / 2,
    },
    {
      id: "region",
      num: "04",
      label: "REGIONAL SYSTEM",
      micro: "ILLUSTRATIVE AGGREGATION · MITIDJA",
      title: "Local systems reveal regional patterns.",
      side: "right",
      holdStart: regStart,
      holdEnd: regEnd,
      narrativeCenter: (regStart + regEnd) / 2,
    },
    {
      id: "nation",
      num: "05",
      label: "NATIONAL INTELLIGENCE",
      micro: "SOVEREIGN VISIBILITY · ALGERIA",
      title: "Regional intelligence becomes national visibility.",
      side: "left",
      holdStart: natStart,
      holdEnd: natEnd,
      narrativeCenter: (natStart + natEnd) / 2,
      isClimax: true,
    },
  ];

  return {
    totalHeightVh: 450,
    stages,
  };
}

export const SCALE_STORY_LAYOUT = compileScaleStoryLayout();
