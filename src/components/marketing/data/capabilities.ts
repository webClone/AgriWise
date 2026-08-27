/* ═══ AgriBrain Capabilities ═══════════════════════════════════
   The six AgriBrain verbs, evidence source taxonomy, and authority
   ladder. Consumed by AgriBrainStory, EvidenceGraphStory,
   AuthorityStory, and stakeholder-specific sections.
   ═══════════════════════════════════════════════════════════════ */

/* ── The six AgriBrain verbs ─────────────────────────────── */

export interface AgriBrainVerb {
  id: string;
  label: string;
  description: string;
  /** What raw data becomes at this stage */
  transformation: string;
  icon: string;
  color: string;
}

export const AGRIBRAIN_VERBS: AgriBrainVerb[] = [
  {
    id: "observe",
    label: "Observe",
    description:
      "Ingest heterogeneous evidence — satellite scenes, weather records, soil measurements, sensor telemetry, farmer events, photographs, drone imagery, laboratory results.",
    transformation: "Raw data → governed evidence objects with provenance",
    icon: "👁️",
    color: "#22d3ee",
  },
  {
    id: "reconstruct",
    label: "Reconstruct",
    description:
      "Estimate the physical state of the field from incomplete, noisy, multi-resolution evidence. Fuse observations across time, space and modality. Quantify what is observed versus what is inferred.",
    transformation: "Evidence objects → reconstructed field state with uncertainty",
    icon: "🔧",
    color: "#60a5fa",
  },
  {
    id: "interpret",
    label: "Interpret",
    description:
      "Generate competing agronomic explanations for observed states. Evaluate hypotheses against available evidence. Identify which additional observations would discriminate between explanations.",
    transformation: "Field state → ranked hypotheses with confidence and evidence gaps",
    icon: "🧠",
    color: "#818cf8",
  },
  {
    id: "decide",
    label: "Decide",
    description:
      "Evaluate possible actions under constraints — agronomic, economic, operational, regulatory. Produce recommendations with explicit assumptions, trade-offs and authority levels.",
    transformation: "Hypotheses + constraints → ranked recommendations with authority",
    icon: "⚖️",
    color: "#a78bfa",
  },
  {
    id: "communicate",
    label: "Communicate",
    description:
      "Render intelligence into maps, alerts, tasks, reports, explanations and institutional signals appropriate for each audience — from a farmer's phone to a ministry's dashboard.",
    transformation: "Recommendations → audience-specific intelligence products",
    icon: "📡",
    color: "#4ade80",
  },
  {
    id: "learn",
    label: "Learn",
    description:
      "Record actual outcomes. Compare predictions to reality. Update model calibration. Build longitudinal memory. The field's history improves future intelligence.",
    transformation: "Outcomes → calibration updates → improved future intelligence",
    icon: "📚",
    color: "#fbbf24",
  },
];

/* ── Authority ladder ────────────────────────────────────── */

export interface AuthorityLevel {
  id: string;
  label: string;
  description: string;
  color: string;
  /** Can this level be used for prescriptive decisions? */
  prescriptiveAllowed: boolean;
}

export const AUTHORITY_LADDER: AuthorityLevel[] = [
  {
    id: "observed",
    label: "Observed",
    description:
      "Directly measured by a sensor with known calibration, support area and measurement time.",
    color: "#22d3ee",
    prescriptiveAllowed: true,
  },
  {
    id: "assimilated",
    label: "Assimilated",
    description:
      "Multiple observations combined through a physically consistent model. Provenance and individual contributions are traceable.",
    color: "#60a5fa",
    prescriptiveAllowed: true,
  },
  {
    id: "estimated",
    label: "Estimated",
    description:
      "Inferred from indirect evidence or model propagation. Uncertainty is quantified. Not a direct observation.",
    color: "#818cf8",
    prescriptiveAllowed: true,
  },
  {
    id: "diagnostic",
    label: "Diagnostic",
    description:
      "An interpretation of observed/estimated state against agronomic knowledge. Multiple competing explanations may exist.",
    color: "#a78bfa",
    prescriptiveAllowed: true,
  },
  {
    id: "advisory",
    label: "Advisory",
    description:
      "A suggested course of action based on diagnostic assessment and operational constraints. Requires human judgement.",
    color: "#fbbf24",
    prescriptiveAllowed: false,
  },
  {
    id: "prescriptive",
    label: "Prescriptive",
    description:
      "A specific operational instruction. Only issued when evidence support, model confidence, and governance rules all permit.",
    color: "#f87171",
    prescriptiveAllowed: false,
  },
];

/* ── Platform capabilities ───────────────────────────────── */

export interface Capability {
  id: string;
  label: string;
  description: string;
  icon: string;
}

export const CAPABILITIES: Capability[] = [
  { id: "field-monitoring", label: "Field Monitoring", description: "Continuous satellite and sensor observation of crop state, health and growth.", icon: "📡" },
  { id: "crop-health", label: "Crop Health", description: "Multi-source vegetation health assessment using spectral indices, sensor data and photographic evidence.", icon: "🌿" },
  { id: "irrigation", label: "Irrigation Intelligence", description: "Water balance, soil moisture, evapotranspiration and irrigation scheduling.", icon: "💧" },
  { id: "tasks", label: "Task Management", description: "Field tasks, intervention scheduling, assignment and outcome tracking.", icon: "📋" },
  { id: "scouting", label: "Scouting & Evidence", description: "Guided field inspection with photo evidence, GPS-tagged observations and hypothesis validation.", icon: "🔍" },
  { id: "weather", label: "Weather Intelligence", description: "Forecast integration, GDD accumulation, frost/heat alerts and historical weather context.", icon: "🌤️" },
  { id: "farm-portfolio", label: "Farm Portfolio", description: "Multi-farm monitoring, comparison, anomaly prioritisation and resource allocation.", icon: "📊" },
  { id: "anomaly-detection", label: "Anomaly Detection", description: "Automatic identification of unusual crop behaviour requiring investigation.", icon: "⚠️" },
  { id: "hypothesis-evaluation", label: "Hypothesis Evaluation", description: "Competing explanations for observed anomalies, ranked by evidence and identifying discriminating observations.", icon: "🧪" },
  { id: "reports", label: "Reports & Communication", description: "Automated field reports, season summaries and stakeholder communications.", icon: "📄" },
  { id: "multi-field", label: "Multi-Field Operations", description: "Enterprise-scale monitoring across dozens to thousands of fields with operational dashboards.", icon: "🗺️" },
  { id: "teams", label: "Team Coordination", description: "Multi-user workspaces, role-based access, task assignment and activity tracking.", icon: "👥" },
  { id: "equipment", label: "Equipment & Assets", description: "Equipment tracking, maintenance scheduling and operational logistics.", icon: "🚜" },
  { id: "yield-economics", label: "Yield & Economics", description: "Production forecasting, profitability analysis and economic decision support.", icon: "📈" },
  { id: "api", label: "API Access", description: "Programmatic access to field state, evidence layers and intelligence products.", icon: "⚙️" },
  { id: "crop-cycle-state", label: "Crop Cycle State", description: "Current phenological stage, growth trajectory and season timeline.", icon: "🌱" },
  { id: "yield-estimation", label: "Yield Estimation", description: "Calibrated yield intervals (P10/P50/P90) based on multi-source evidence.", icon: "📊" },
  { id: "stress-history", label: "Stress History", description: "Temporal record of stress events, interventions and recovery.", icon: "📉" },
  { id: "portfolio-monitoring", label: "Portfolio Monitoring", description: "Aggregate monitoring across institutional agricultural portfolios.", icon: "🏦" },
  { id: "event-detection", label: "Event Detection", description: "Satellite-based detection of drought, flood, hail and other agricultural events.", icon: "🌊" },
  { id: "temporal-evidence", label: "Temporal Evidence", description: "Before/after satellite evidence for verifiable event impact assessment.", icon: "⏱️" },
  { id: "claims-support", label: "Claims Support", description: "Evidence packages for insurance claims with traceable provenance and uncertainty.", icon: "📋" },
  { id: "risk-layers", label: "Risk Layers", description: "Spatial risk products for portfolio management and underwriting.", icon: "🗺️" },
  { id: "national-inventory", label: "National Crop Inventory", description: "Satellite-derived crop type, area and phenological stage at national scale.", icon: "🌾" },
  { id: "food-security", label: "Food Security Signals", description: "Production outlook, anomaly detection and food supply risk indicators.", icon: "🍞" },
  { id: "water-governance", label: "Water Governance", description: "Agricultural water demand, irrigation monitoring and water allocation intelligence.", icon: "💧" },
  { id: "drought-monitoring", label: "Drought Monitoring", description: "Multi-indicator drought detection, severity assessment and spatial extent tracking.", icon: "☀️" },
  { id: "subsidy-monitoring", label: "Subsidy & Program Monitoring", description: "Evidence-based monitoring of agricultural program coverage and impact.", icon: "📝" },
  { id: "extension", label: "Extension Service", description: "Prioritised field visit scheduling and agronomic guidance for extension agents.", icon: "🧑‍🌾" },
  { id: "sovereign-deployment", label: "Sovereign Deployment", description: "National infrastructure deployment with data sovereignty and institutional governance.", icon: "🏛️" },
  { id: "member-portfolio", label: "Member Portfolio", description: "Aggregate monitoring of cooperative member farms.", icon: "🤝" },
  { id: "harvest-coordination", label: "Harvest Coordination", description: "Coordinated harvest timing and logistics across member farms.", icon: "🚛" },
  { id: "quality", label: "Quality Assessment", description: "Crop quality estimation from spectral, sensor and environmental evidence.", icon: "✅" },
  { id: "supply-planning", label: "Supply Planning", description: "Aggregate production forecasting for supply chain planning.", icon: "📦" },
  { id: "supply-monitoring", label: "Supply Monitoring", description: "Regional crop production monitoring for procurement intelligence.", icon: "🌍" },
  { id: "procurement-quality", label: "Procurement Quality", description: "Source-region quality assessment for agricultural commodity buyers.", icon: "🔎" },
  { id: "source-region", label: "Source Region", description: "Monitoring of agricultural production regions relevant to supply chains.", icon: "📍" },
  { id: "commodity-outlook", label: "Commodity Outlook", description: "Production-based outlook for agricultural commodity markets.", icon: "📈" },
  { id: "longitudinal-data", label: "Longitudinal Data", description: "Multi-season, field-level datasets for research and analysis.", icon: "📊" },
  { id: "experimental-support", label: "Experimental Support", description: "Plot-level monitoring and treatment comparison for agricultural experiments.", icon: "🧪" },
  { id: "causal-discovery", label: "Causal Discovery", description: "Tools for investigating causal relationships in agricultural systems.", icon: "🔗" },
  { id: "uncertainty", label: "Uncertainty Quantification", description: "Calibrated uncertainty estimates on all intelligence products.", icon: "📐" },
  { id: "integration", label: "System Integration", description: "Integration with sensors, labs, ERP, irrigation controllers and institutional systems.", icon: "🔌" },
  { id: "data-products", label: "Data Products", description: "Structured intelligence products for downstream consumption.", icon: "📦" },
  { id: "webhooks", label: "Webhooks & Events", description: "Real-time event notifications for automated workflows.", icon: "🔔" },
];
