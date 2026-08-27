/* ═══ Canonical Audience Data ══════════════════════════════════
   Single source of truth for all stakeholder/audience definitions.
   Consumed by: StakeholderGateway, HeroIntelligence, CTAConstellation,
   InstitutionalContactDialog, and future /solutions/[role] pages.
   ═══════════════════════════════════════════════════════════════ */

export const AUDIENCE_IDS = [
  "farmer",
  "agronomist",
  "enterprise",
  "cooperative",
  "bank",
  "insurance",
  "government",
  "agribusiness",
  "research",
  "api",
] as const;

export type AudienceId = (typeof AUDIENCE_IDS)[number];

/** How the hero canvas should render for this audience */
export type PreviewMode =
  | "single-field"
  | "multi-field"
  | "portfolio-risk"
  | "event-footprint"
  | "national-canvas"
  | "agronomist-portfolio"
  | "supply-chain"
  | "research-grid"
  | "api-architecture";

export interface ActionConfig {
  label: string;
  href: string;
  /** "route" = navigates to a page. "contact" = opens InstitutionalContactDialog. "scroll" = scrolls to section. */
  type: "route" | "contact" | "scroll";
}

export interface Audience {
  id: AudienceId;
  label: string;
  shortLabel: string;
  icon: string;
  color: string;
  tagline: string;
  description: string;
  /** What key question does this audience answer with AgriWise? */
  centralQuestion: string;
  /** Key capabilities relevant to this audience (references CapabilityId) */
  capabilities: string[];
  /** Evidence types most relevant to this audience */
  evidence: string[];
  primaryAction: ActionConfig;
  secondaryAction?: ActionConfig;
  previewMode: PreviewMode;
}

export const AUDIENCES: Record<AudienceId, Audience> = {
  farmer: {
    id: "farmer",
    label: "Farmer",
    shortLabel: "Farmer",
    icon: "🌾",
    color: "#4ade80",
    tagline: "Understand and manage your field",
    description:
      "Evidence-backed field intelligence — from satellite observation to irrigation decisions, crop health monitoring, and harvest planning.",
    centralQuestion: "What is happening in my field, and what should I do?",
    capabilities: [
      "field-monitoring",
      "crop-health",
      "irrigation",
      "tasks",
      "scouting",
      "weather",
    ],
    evidence: [
      "satellite-optical",
      "weather",
      "soil-sensor",
      "farmer-photo",
      "farmer-event",
    ],
    primaryAction: {
      label: "Analyze My Field",
      href: "/farm/new",
      type: "route",
    },
    secondaryAction: {
      label: "See Farmer Tools",
      href: "#platform",
      type: "scroll",
    },
    previewMode: "single-field",
  },

  agronomist: {
    id: "agronomist",
    label: "Agronomist",
    shortLabel: "Agronomist",
    icon: "🔬",
    color: "#22d3ee",
    tagline: "Be more effective across many farms",
    description:
      "Portfolio monitoring, anomaly prioritisation, competing stress hypotheses, evidence collection workflows, and outcome tracking across assigned farms.",
    centralQuestion:
      "Which farms need attention, what are the competing explanations, and what evidence would discriminate between them?",
    capabilities: [
      "farm-portfolio",
      "anomaly-detection",
      "hypothesis-evaluation",
      "scouting",
      "tasks",
      "reports",
    ],
    evidence: [
      "satellite-optical",
      "satellite-sar",
      "weather",
      "soil-sensor",
      "farmer-photo",
      "drone",
      "lab-analysis",
    ],
    primaryAction: {
      label: "Open Agronomist Workspace",
      href: "/farm",
      type: "route",
    },
    secondaryAction: {
      label: "Explore AgriBrain",
      href: "/agribrain",
      type: "route",
    },
    previewMode: "agronomist-portfolio",
  },

  enterprise: {
    id: "enterprise",
    label: "Farm Enterprise",
    shortLabel: "Enterprise",
    icon: "🏢",
    color: "#818cf8",
    tagline: "Operational intelligence across the company",
    description:
      "Multi-field monitoring, team coordination, equipment and irrigation management, yield distributions, profitability analysis, sensor/drone integration, premium imagery, API access and SLA.",
    centralQuestion:
      "What is the operational state across all our fields, and where are the risks?",
    capabilities: [
      "multi-field",
      "teams",
      "irrigation",
      "equipment",
      "yield-economics",
      "api",
    ],
    evidence: [
      "satellite-optical",
      "satellite-sar",
      "weather",
      "soil-sensor",
      "drone",
      "irrigation-controller",
      "management-history",
    ],
    primaryAction: {
      label: "Explore Farm Enterprise",
      href: "",
      type: "contact",
    },
    secondaryAction: {
      label: "Request a Demo",
      href: "",
      type: "contact",
    },
    previewMode: "multi-field",
  },

  cooperative: {
    id: "cooperative",
    label: "Cooperative",
    shortLabel: "Cooperative",
    icon: "🤝",
    color: "#34d399",
    tagline: "Member intelligence and harvest coordination",
    description:
      "Aggregate member farm intelligence, coordinate harvest timing, quality assessment, supply planning, and shared infrastructure management.",
    centralQuestion:
      "What is the state of our members' production, and how do we coordinate operations?",
    capabilities: [
      "member-portfolio",
      "harvest-coordination",
      "quality",
      "supply-planning",
    ],
    evidence: [
      "satellite-optical",
      "weather",
      "management-history",
      "market-data",
    ],
    primaryAction: {
      label: "Explore Cooperative Intelligence",
      href: "",
      type: "contact",
    },
    secondaryAction: {
      label: "Talk to AgriWise",
      href: "",
      type: "contact",
    },
    previewMode: "multi-field",
  },

  bank: {
    id: "bank",
    label: "Bank / Lender",
    shortLabel: "Bank",
    icon: "🏦",
    color: "#60a5fa",
    tagline: "Agricultural credit that can see the crop cycle",
    description:
      "Crop-cycle state, stress trajectory, yield intervals, operational history and portfolio signals. Decision support under human supervision — not autonomous credit scoring.",
    centralQuestion:
      "What is the agricultural evidence behind this credit portfolio?",
    capabilities: [
      "crop-cycle-state",
      "yield-estimation",
      "stress-history",
      "portfolio-monitoring",
    ],
    evidence: [
      "satellite-optical",
      "satellite-sar",
      "weather",
      "management-history",
      "measured-outcomes",
    ],
    primaryAction: {
      label: "Explore AgriBank Intelligence",
      href: "",
      type: "contact",
    },
    secondaryAction: {
      label: "Discuss Portfolio Integration",
      href: "",
      type: "contact",
    },
    previewMode: "portfolio-risk",
  },

  insurance: {
    id: "insurance",
    label: "Insurance",
    shortLabel: "Insurance",
    icon: "🛡️",
    color: "#f59e0b",
    tagline: "From satellite event to defensible field evidence",
    description:
      "Event detection, affected portfolio identification, temporal before/after evidence, uncertainty quantification, and claims-support evidence packages.",
    centralQuestion:
      "What happened, which policies are affected, and what is the field-level evidence?",
    capabilities: [
      "event-detection",
      "portfolio-monitoring",
      "temporal-evidence",
      "claims-support",
      "risk-layers",
    ],
    evidence: [
      "satellite-optical",
      "satellite-sar",
      "weather",
      "soil-sensor",
      "farmer-photo",
      "measured-outcomes",
    ],
    primaryAction: {
      label: "Explore Insurance Risk",
      href: "",
      type: "contact",
    },
    secondaryAction: {
      label: "Discuss Claims & Risk API",
      href: "",
      type: "contact",
    },
    previewMode: "event-footprint",
  },

  government: {
    id: "government",
    label: "Government",
    shortLabel: "Government",
    icon: "🏛️",
    color: "#a78bfa",
    tagline: "National agricultural intelligence infrastructure",
    description:
      "Crop inventory, production outlook, water governance, drought monitoring, food-security signals, subsidy/program monitoring, extension-service prioritisation, disaster evidence, and sovereign deployment.",
    centralQuestion:
      "What is the state of national agricultural production, water, food security, and where should we intervene?",
    capabilities: [
      "national-inventory",
      "food-security",
      "water-governance",
      "drought-monitoring",
      "subsidy-monitoring",
      "extension",
      "sovereign-deployment",
    ],
    evidence: [
      "satellite-optical",
      "satellite-sar",
      "weather",
      "soil-sensor",
      "management-history",
      "market-data",
      "measured-outcomes",
    ],
    primaryAction: {
      label: "Explore Government Intelligence",
      href: "",
      type: "contact",
    },
    secondaryAction: {
      label: "Discuss Sovereign Deployment",
      href: "",
      type: "contact",
    },
    previewMode: "national-canvas",
  },

  agribusiness: {
    id: "agribusiness",
    label: "Agribusiness",
    shortLabel: "Agribusiness",
    icon: "📦",
    color: "#fb923c",
    tagline: "Supply intelligence and procurement visibility",
    description:
      "Supply/demand intelligence, procurement quality and timing, source-region monitoring, and commodity outlook based on satellite-observed production evidence.",
    centralQuestion:
      "What does agricultural production evidence tell us about supply, quality and timing?",
    capabilities: [
      "supply-monitoring",
      "procurement-quality",
      "source-region",
      "commodity-outlook",
    ],
    evidence: [
      "satellite-optical",
      "weather",
      "market-data",
      "measured-outcomes",
    ],
    primaryAction: {
      label: "Explore Supply Intelligence",
      href: "",
      type: "contact",
    },
    secondaryAction: {
      label: "Discuss Data/API Integration",
      href: "",
      type: "contact",
    },
    previewMode: "supply-chain",
  },

  research: {
    id: "research",
    label: "Research",
    shortLabel: "Research",
    icon: "🧪",
    color: "#e879f9",
    tagline: "Longitudinal agricultural research infrastructure",
    description:
      "Multi-season field-level datasets, experimental plot monitoring, causal discovery support, calibrated uncertainty, and reproducible analytical infrastructure.",
    centralQuestion:
      "Can we build longitudinal, reproducible, evidence-backed agricultural research on this infrastructure?",
    capabilities: [
      "longitudinal-data",
      "experimental-support",
      "causal-discovery",
      "uncertainty",
      "api",
    ],
    evidence: [
      "satellite-optical",
      "satellite-sar",
      "weather",
      "soil-sensor",
      "drone",
      "lab-analysis",
      "management-history",
      "measured-outcomes",
    ],
    primaryAction: {
      label: "Explore Research Infrastructure",
      href: "",
      type: "contact",
    },
    secondaryAction: {
      label: "Partner with AgriWise",
      href: "",
      type: "contact",
    },
    previewMode: "research-grid",
  },

  api: {
    id: "api",
    label: "Developer / Enterprise API",
    shortLabel: "API",
    icon: "⚙️",
    color: "#94a3b8",
    tagline: "Build with agricultural intelligence",
    description:
      "Programmatic access to field state, evidence layers, AgriBrain intelligence, and institutional data products. Sensors, laboratories, irrigation controllers, ERP, claims systems, and government data infrastructure.",
    centralQuestion:
      "How do we integrate agricultural intelligence into our own systems?",
    capabilities: ["api", "integration", "data-products", "webhooks"],
    evidence: [],
    primaryAction: {
      label: "Build with AgriWise API",
      href: "",
      type: "contact",
    },
    secondaryAction: {
      label: "View Architecture",
      href: "/agribrain",
      type: "route",
    },
    previewMode: "api-architecture",
  },
};

/** Audiences that are shown as hero role chips */
export const HERO_AUDIENCES: AudienceId[] = [
  "farmer",
  "agronomist",
  "enterprise",
  "bank",
  "insurance",
  "government",
];

/** Audiences that are institutional (use contact dialog, not direct app routes) */
export const INSTITUTIONAL_AUDIENCES: AudienceId[] = [
  "enterprise",
  "cooperative",
  "bank",
  "insurance",
  "government",
  "agribusiness",
  "research",
  "api",
];

/** Contact intent types — maps to InstitutionalContactDialog */
export type ContactIntent = Exclude<AudienceId, "farmer">;
