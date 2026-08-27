import runData from "./illustrative-run.v1.json";
import type { IllustrativeScientificRun } from "./illustrativeRun.schema";

export const ILLUSTRATIVE_RUN = runData as unknown as IllustrativeScientificRun;

export function getManifest() {
  return ILLUSTRATIVE_RUN.manifest;
}

export function getEvidenceGraph() {
  return ILLUSTRATIVE_RUN.evidenceGraph;
}

export function getFieldCube() {
  return ILLUSTRATIVE_RUN.fieldCube;
}

export function getWorldline() {
  return ILLUSTRATIVE_RUN.worldline;
}

export function getLayerExecution(layerId: string) {
  return ILLUSTRATIVE_RUN.layerExecutions.find((l) => l.layerId === layerId);
}

export function getAsmaeRun() {
  return ILLUSTRATIVE_RUN.asmae;
}

export function getClaims() {
  return ILLUSTRATIVE_RUN.claims;
}
