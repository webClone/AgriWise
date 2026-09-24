export type Locale = "en" | "ar" | "fr";
export type TextDirection = "ltr" | "rtl";

export interface LocaleMeta {
  code: Locale;
  nativeName: string;
  englishName: string;
  dir: TextDirection;
  flag: string;
}

export const SUPPORTED_LOCALES: Record<Locale, LocaleMeta> = {
  en: {
    code: "en",
    nativeName: "English",
    englishName: "English",
    dir: "ltr",
    flag: "🇬🇧",
  },
  ar: {
    code: "ar",
    nativeName: "العربية",
    englishName: "Arabic",
    dir: "rtl",
    flag: "🇩🇿",
  },
  fr: {
    code: "fr",
    nativeName: "Français",
    englishName: "French",
    dir: "ltr",
    flag: "🇫🇷",
  },
};

export interface Translations {
  nav: {
    perception: string;
    reasoning: string;
    scale: string;
    architecture: string;
    platforms: string;
    deploy: string;
    forEnterprise: string;
    analyzeField: string;
    worldModel: string;
  };
  hero: {
    slogan: string;
    headlineMain: string;
    headlineAccent: string;
    subheadline: string;
    exploreCognitiveLoop: string;
    simulateCounterfactuals: string;
    liveCanopyBadge: string;
    foundationModel: string;
    surveillanceStream: string;
    plotSector: string;
    vpdText: string;
    windText: string;
    copilotTitle: string;
    copilotSubtitle: string;
    scenarioChipsLabel: string;
    chipRain: string;
    chipFertigation: string;
    chipVadose: string;
    inputPlaceholder: string;
    dispatchBtn: string;
    dispatchedBtn: string;
    simulate72h: string;
    vadoseMoisture: string;
    optimalBadge: string;
    transpirationFlux: string;
    noStressBadge: string;
    learnedPrior: string;
    calibratedBadge: string;
    dagLedger: string;
    verifiedBadge: string;
    sensorProof: string;
    streams: {
      drone: {
        title: string;
        badge: string;
        box1Title: string;
        box1Desc: string;
        box2Title: string;
        box2Desc: string;
      };
      growth: {
        title: string;
        badge: string;
        box1Title: string;
        box1Desc: string;
        box2Title: string;
        box2Desc: string;
      };
      irrigation: {
        title: string;
        badge: string;
        box1Title: string;
        box1Desc: string;
        box2Title: string;
        box2Desc: string;
      };
      harvest: {
        title: string;
        badge: string;
        box1Title: string;
        box1Desc: string;
        box2Title: string;
        box2Desc: string;
      };
    };
  };
  footer: {
    slogan: string;
    tagline: string;
    platform: string;
    solutions: string;
    company: string;
    fieldMonitoring: string;
    cropIntelligence: string;
    agribrain: string;
    farmers: string;
    agronomists: string;
    farmEnterprise: string;
    banksInsurance: string;
    government: string;
    about: string;
    contact: string;
    privacy: string;
    terms: string;
    rightsReserved: string;
  };
  common: {
    language: string;
    selectLanguage: string;
  };
  perception: {
    sectionBadge: string;
    slides: {
      loop: { badge: string; title: string; subtitle: string };
      memory: { badge: string; title: string; subtitle: string };
      reality: { badge: string; title: string; subtitle: string };
    };
    stageLabel: string;
    stages: {
      step: string;
      name: string;
      tagline: string;
      detail: string;
      metric: string;
    }[];
    targetMetric: string;
    closedGuarantee: string;
    closedGuaranteeText: string;
    seasonsTitle: string;
    seasonsSubtitle: string;
    seasonsList: {
      year: string;
      crop: string;
      variety: string;
      yieldRealized: string;
      delta: string;
      learnedPrior: string;
      waterUsed: string;
      resilienceScore: string;
      status: string;
    }[];
    reconciliationCard: {
      title: string;
      statusBadge: string;
      waterBudget: string;
      convergenceTitle: string;
      uncertaintyReduced: string;
    };
    realityControls: {
      header: string;
      splitView: string;
      surface: string;
      subsurface: string;
      droneScan: string;
      growthTimelapse: string;
      irrigationFlux: string;
      surfaceLabel: string;
      subsurfaceLabel: string;
      vadoseCore: string;
      matricSuction: string;
      droughtBoundary: string;
      hydraulicConductivity: string;
    };
  };
  reasoning: {
    sectionBadge: string;
    slides: {
      diagnosis: { num: string; badge: string; title: string; subtitle: string };
      simulation: { num: string; badge: string; title: string; subtitle: string };
    };
    hypothesesLabel: string;
    hypotheses: {
      id: string;
      cause: string;
      mechanism: string;
      actionIfTrue: string;
    }[];
    mechanismLabel: string;
    recommendedActionLabel: string;
    nextBestLabel: string;
    nextBestTitle: string;
    nextBestDesc: string;
    activeGraphLabel: string;
    graphNodes: {
      vpd: string;
      matric: string;
      stomatal: string;
      thermal: string;
    };
    branches: {
      id: string;
      name: string;
      tag: string;
      projectedYield: string;
      waterImpact: string;
      downsideRisk: string;
      netEconomicAdvantage: string;
      rationale: string;
    }[];
    chartHeader: string;
    chartSelected: string;
    optimalBandLabel: string;
    wiltingLabel: string;
    rainLabel: string;
    scrubStatus: {
      optimal: string;
      wilting: string;
      rainRecharged: string;
      rapidSaturation: string;
      rootHypoxia: string;
      stomatalCalibrated: string;
    };
    videoToggle: {
      show: string;
      hide: string;
    };
    videoTelemetryTitle: string;
    videoTelemetrySubtitle: string;
  };
  scale: {
    sectionBadge: string;
    slides: {
      scale: { num: string; badge: string; title: string; subtitle: string };
      national: { num: string; badge: string; title: string; subtitle: string };
    };
    tierNav: string[];
    tiers: {
      name: string;
      subtitle: string;
      headline: string;
      description: string;
      videoBadge: string;
      metric: string;
    }[];
    biophysicalGuarantee: string;
    liveStreamBtn: string;
    orthoPhotoBtn: string;
    liveStreamTag: string;
    scaleLevelTag: string;
    oversightActive: string;
    simulateDroughtBtn: string;
    simulatingDroughtBtn: string;
    emergencyBannerTitle: string;
    emergencyBannerText: string;
    stressTestBadge: string;
    sovereignCards: {
      title: string;
      tag: string;
      metricNormal: string;
      metricShock: string;
      impactNormal: string;
      impactShock: string;
      desc: string;
    }[];
  };
  architecture: {
    sectionBadge: string;
    slides: {
      layers: { num: string; badge: string; title: string; subtitle: string };
      continuous: { num: string; badge: string; title: string; subtitle: string };
    };
    layersLabel: string;
    layers: {
      id: string;
      code: string;
      name: string;
      tagline: string;
      role: string;
      mathematicalBasis: string;
      guarantee: string;
      provenanceLevel: string;
      status: string;
      outputs: string[];
    }[];
    pipelineDagTitle: string;
    pipelineStatus: string;
    pipelineNodes: {
      ingestion: string;
      inversion: string;
      cube: string;
      simulation: string;
      action: string;
    };
    continuousTitle: string;
    continuousSubtitle: string;
    moatPoints: { title: string; desc: string }[];
    omegaDiscoveryTitle: string;
    omegaDiscoveryDesc: string;
  };
  platforms: {
    sectionBadge: string;
    title: string;
    subtitle: string;
    doors: {
      id: string;
      badge: string;
      title: string;
      subtitle: string;
      tagline: string;
      coreQuestion: string;
      agriwiseAnswer: string;
      kpis: { label: string; value: string; detail: string }[];
      capabilities: string[];
      ctaLabel: string;
      ctaHref: string;
      mockUI: {
        panelTitle: string;
        primaryMetric: { label: string; value: string; status: string };
        feedItems: { time: string; text: string; tag: string }[];
      };
    }[];
  };
  deployment: {
    sectionBadge: string;
    headlineMain: string;
    headlineAccent: string;
    subheadline: string;
    fieldGateway: {
      badge: string;
      title: string;
      desc: string;
      cta: string;
    };
    enterpriseGateway: {
      badge: string;
      title: string;
      desc: string;
      cta: string;
    };
    complianceNotice: string;
  };
  contactDialog: {
    title: string;
    subtitle: string;
    labels: {
      name: string;
      email: string;
      organization: string;
      orgType: string;
      fieldCount: string;
      country: string;
      message: string;
    };
    placeholders: {
      name: string;
      email: string;
      organization: string;
      fieldCount: string;
      message: string;
    };
    orgTypes: {
      enterprise: string;
      cooperative: string;
      government: string;
      bank: string;
      research: string;
      other: string;
    };
    buttons: {
      submit: string;
      submitting: string;
      successTitle: string;
      successDesc: string;
      close: string;
    };
    errors: {
      required: string;
      server: string;
    };
  };
  auth: {
    signIn: string;
    signUp: string;
    signOut: string;
    loginTitle: string;
    loginSubtitle: string;
    registerTitle: string;
    registerSubtitle: string;
    tabs: {
      otp: string;
      password: string;
      demo: string;
    };
    labels: {
      phone: string;
      phonePlaceholder: string;
      password: string;
      passwordPlaceholder: string;
      identifier: string;
      identifierPlaceholder: string;
      name: string;
      namePlaceholder: string;
      wilaya: string;
      selectWilaya: string;
      role: string;
      farmName: string;
      farmNamePlaceholder: string;
      farmArea: string;
      farmAreaPlaceholder: string;
    };
    otp: {
      sendCode: string;
      sendingCode: string;
      enterCode: string;
      enterCodeSubtitle: string;
      verifyAndLogin: string;
      verifying: string;
      resendCode: string;
      resendIn: string;
      changePhone: string;
      devFill: string;
    };
    demo: {
      title: string;
      desc: string;
      farmerTitle: string;
      farmerDesc: string;
      agronomistTitle: string;
      agronomistDesc: string;
      sovereignTitle: string;
      sovereignDesc: string;
      loginAs: string;
    };
    roles: {
      smallFarmer: string;
      mediumFarmer: string;
      largeFarmer: string;
      agronomist: string;
      cooperative: string;
      enterprise: string;
      sovereign: string;
    };
    switch: {
      noAccount: string;
      haveAccount: string;
      registerNow: string;
      loginNow: string;
    };
    userMenu: {
      myFarms: string;
      operations: string;
      logout: string;
    };
    errors: {
      invalidPhone: string;
      invalidOtp: string;
      invalidCredentials: string;
      phoneTaken: string;
      required: string;
      general: string;
    };
  };
}
