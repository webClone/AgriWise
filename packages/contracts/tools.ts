import { z } from "zod";

// --- Domain: Earth Observation (EO) ---

export const GetFieldIndicatorsSchema = z.object({
  fieldId: z.string().uuid().describe("Unique UUID of the field polygon"),
  startDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).describe("Start date (YYYY-MM-DD)"),
  endDate: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).describe("End date (YYYY-MM-DD)"),
  indicators: z.array(z.enum(["ndvi", "ndmi", "rainfall", "temp", "gdd"])).describe("List of indicators to compute"),
});

export type GetFieldIndicatorsInput = z.infer<typeof GetFieldIndicatorsSchema>;

// --- Domain: Machine Learning (ML) ---

export const PredictYieldSchema = z.object({
  fieldId: z.string().uuid().describe("Unique UUID of the field"),
  crop: z.string().describe("Crop name (e.g. 'wheat', 'tomato')"),
});

export type PredictYieldInput = z.infer<typeof PredictYieldSchema>;

// --- Tool Registry Definition ---
// This aligns with Vertex/Gemini Tool Config

export const AgriBrainTools = {
  eo_getFieldIndicators: {
    name: "eo_getFieldIndicators",
    description: "Fetch historical time-series indicators (NDVI, Rainfall) for a specific field.",
    parameters: GetFieldIndicatorsSchema,
  },
  ml_predictYield: {
    name: "ml_predictYield",
    description: "Predict yield potential for a crop on a specific field using ML models.",
    parameters: PredictYieldSchema,
  },
};
