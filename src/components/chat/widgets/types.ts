export interface FieldIndicatorsProps {
  data: {
    field_id: string;
    date: string;
    ndvi: number;
    ndmi: number;
    rainfall_mm: number;
    temp_c: number;
  }[];
}

export interface YieldPredictionProps {
  data: {
    field_id: string;
    crop: string;
    predicted_yield_t_ha: number;
    confidence: number;
    limiting_factors: string[];
  };
}
