# Layer 3: Transitional Water Intelligence Engine

Maturity: **TRANSITION FOUNDATION / VALID_DEGRADED**. This package is not the
Agricultural World Model and its decision-shaped output is shadow-only; L8 owns
canonical action selection.

Layer 3 coordinates specialized physical, statistical, and control engines across the soil-plant-atmosphere continuum (SPAC).

---

## 1. Engine Inventory & Capabilities

### A. Atmospheric & Evaporative Demand (`layer3_water/et/`)
1. **PenmanMonteithET0**: Computes standard FAO-56 reference evapotranspiration ($ET_0$) with atmospheric provenance tracking across psychrometric, radiation, wind, and temperature hierarchies.
2. **DualKcEngine**: Implements FAO-56 dual crop coefficient methodology. Computes basal transpiration $K_{cb}$ from Layer 2 canopy state (continuous Beer-Lambert and fractional cover fusion), climate adjustments, soil evaporation $K_e$, and separates potential demand ($ET_p, T_{\text{pot}}, E_{s,\text{pot}}$) from realized fluxes ($ET_a, T_{\text{act}}, E_{s,\text{act}}, T_{\text{deficit}}$).

### B. Soil Hydraulics & Profile Database (`layer3_water/soil/`)
3. **SoilProfileDatabase**: Standardized USDA texture hydraulic parameter database providing Van Genuchten parameters ($\theta_r, \theta_{\text{wp}}, \theta_{\text{fc}}, \theta_s, K_{\text{sat}}, \alpha, n$).
4. **LayeredWaterBalanceEngine**: Simulates multi-layer vertical soil water balance (infiltration, runoff, percolation cascade, topsoil evaporation bounded by $\theta_r$, root extraction bounded by $\theta_{\text{wp}}$, and exact mass conservation closure error calculation).

### C. Data Assimilation (`layer3_water/assimilation/`)
5. **WaterStateAssimilator**: 1D Optimal Interpolation and Kalman Filter ($X^+ = X^- + \mathbf{K}(y - \mathbf{H}X^-)$) ingesting in-situ TDR probe profiles, satellite SMAP surface moisture, and canopy cooling radiometer differentials.

### D. Adaptive Numerical Solver (`layer3_water/solver/`)
6. **SolverSelector**: Executes and reports `EMPIRICAL_BUCKET`. Richards 1D remains unavailable and an eligible/requested Richards mode degrades truthfully to the implemented bucket solver.

### E. Root Zone & Water Limitation (`layer3_water/root_zone/`, `layer3_water/limitation/`)
7. **RootZoneAvailabilityEngine**: Computes active root depth $Z_r$, TAW, demand-adjusted $p_{\text{adj}}$, RAW, depletion $D_r$, Feddes root uptake distribution $U(z)$, and stress factor $K_s$.
8. **WaterLimitationEngine**: Evaluates physical transpiration restriction $T_{\text{deficit}} = (1 - K_s)T_{\text{pot}}$ and propagates 4-component quadrature uncertainties.

### F. Historical Stress Memory & Forecasting (`layer3_water/contracts/`, `layer3_water/forecast/`)
9. **HydraulicStressMemoryState**: Accumulates cumulative transpiration deficit, consecutive stress days, integrated VPD stress index, and recovery rates.
10. **EnsembleForecastEngine**: Simulates probabilistic depletion trajectories $P(D_r > \text{RAW})$ across calibrated NWP weather and soil parameter ensembles.

### G. Shadow Decision Analysis (`layer3_water/decision/`)
11. **MPCPrescriptiveOptimizer**: Transitional shadow analysis only. Its output is not a canonical prescription or machine-execution authorization.
