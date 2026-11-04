/** Shared owned-plot scalar mutation contract. Nested Prisma writes are forbidden. */
import type { Prisma } from "@prisma/client";

export class PlotMutationValidationError extends Error {
  readonly status: 400 | 403;
  constructor(message: string, status: 400 | 403 = 403) {
    super(message);
    this.status = status;
    this.name = "PlotMutationValidationError";
  }
}
export type OwnedPlotMutation = {
  metadata: Prisma.PlotUpdateInput;
  geoJson: Record<string, unknown> | undefined;
};

const SOIL_TYPES = new Set(["CLAY","SANDY","LOAM","SILT","PEAT","CHALKY"]);
const IRRIGATION_TYPES = new Set(["DRIP","SPRINKLER","PIVOT","FLOOD","RAINFED"]);

function positive(value: unknown, field: string): number {
  if (
    (typeof value !== "number" && typeof value !== "string")
    || (typeof value === "string" && !value.trim())
  ) throw new PlotMutationValidationError("Invalid " + field, 400);
  const number = Number(value);
  if (!Number.isFinite(number) || number <= 0)
    throw new PlotMutationValidationError("Invalid " + field, 400);
  return number;
}
function nullableText(value: unknown, field: string): string | null {
  if (value === null) return null;
  if (typeof value !== "string")
    throw new PlotMutationValidationError("Invalid " + field, 400);
  return value;
}

export function parseOwnedPlotMutation(
  input: unknown, { allowBodyId = false }: { allowBodyId?: boolean } = {},
): OwnedPlotMutation {
  if (!input || typeof input !== "object" || Array.isArray(input))
    throw new PlotMutationValidationError("Invalid plot update body", 400);
  const metadata: Prisma.PlotUpdateInput = {};
  let geoJson: Record<string, unknown> | undefined;
  for (const [key, value] of Object.entries(input)) {
    switch (key) {
      case "id":
        if (!allowBodyId || typeof value !== "string")
          throw new PlotMutationValidationError("Plot identity is read-only");
        break;
      case "name":
        if (typeof value !== "string" || !value.trim())
          throw new PlotMutationValidationError("Invalid plot name", 400);
        metadata.name = value.trim();
        break;
      case "nameAr": metadata.nameAr = nullableText(value, key); break;
      case "area": metadata.area = positive(value, key); break;
      case "perimeter":
        metadata.perimeter = value === null ? null : positive(value, key); break;
      case "ownership": metadata.ownership = nullableText(value, key); break;
      case "irrigationDistrict":
        metadata.irrigationDistrict = nullableText(value, key); break;
      case "soilType":
        if (value !== null && (typeof value !== "string" || !SOIL_TYPES.has(value)))
          throw new PlotMutationValidationError("Invalid soilType", 400);
        metadata.soilType = value as Prisma.PlotUpdateInput["soilType"];
        break;
      case "irrigation":
        if (value !== null && (typeof value !== "string" || !IRRIGATION_TYPES.has(value)))
          throw new PlotMutationValidationError("Invalid irrigation", 400);
        metadata.irrigation = value as Prisma.PlotUpdateInput["irrigation"];
        break;
      case "physicalConstraints":
        if (!Array.isArray(value) || value.some(item => typeof item !== "string"))
          throw new PlotMutationValidationError("Invalid physicalConstraints", 400);
        metadata.physicalConstraints = { set: value };
        break;
      case "geoJson":
        if (!value || typeof value !== "object" || Array.isArray(value))
          throw new PlotMutationValidationError("Invalid plot geometry", 400);
        geoJson = value as Record<string, unknown>;
        break;
      default:
        // Reject ALL unknown fields, including relational create/connect/set.
        throw new PlotMutationValidationError("Unapproved plot update field: " + key);
    }
  }
  return { metadata, geoJson };
}
