CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Farms Table
CREATE TABLE IF NOT EXISTS farms (
  id UUID PRIMARY KEY,
  name TEXT,
  owner_type TEXT,
  location TEXT,
  created_at TIMESTAMP DEFAULT now()
);

-- 2. Fields Table (The core geospatial unit)
CREATE TABLE IF NOT EXISTS fields (
  id UUID PRIMARY KEY,
  farm_id UUID REFERENCES farms(id),
  name TEXT,
  crop_code TEXT,
  geom GEOMETRY(POLYGON, 4326),
  area_ha DOUBLE PRECISION,
  sowing_date DATE,
  created_at TIMESTAMP DEFAULT now()
);

-- Spatial index for fast queries
CREATE INDEX IF NOT EXISTS idx_fields_geom ON fields USING GIST (geom);

-- 3. Daily Indicators (Time-series data for ML)
CREATE TABLE IF NOT EXISTS field_indicators_daily (
  field_id UUID REFERENCES fields(id),
  date DATE,
  -- Earth Observation Indices
  ndvi_mean DOUBLE PRECISION,
  ndmi_mean DOUBLE PRECISION,
  evi_mean DOUBLE PRECISION,
  -- SAR (Sentinel-1)
  vv_mean DOUBLE PRECISION,
  vh_mean DOUBLE PRECISION,
  -- Weather
  rainfall_mm DOUBLE PRECISION,
  temp_c DOUBLE PRECISION,
  vpd_kpa DOUBLE PRECISION,
  -- Labels (Optional)
  stress_label TEXT,
  PRIMARY KEY (field_id, date)
);

-- 4. Admin Regions (For aggregation)
CREATE TABLE IF NOT EXISTS admin_regions (
  id SERIAL PRIMARY KEY,
  name TEXT,
  type TEXT, -- 'wilaya', 'commune'
  geom GEOMETRY(MULTIPOLYGON, 4326)
);
