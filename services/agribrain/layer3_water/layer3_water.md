# Layer 3: Transitional Water Intelligence (layer3_water)

## 1. Executive Summary & Architectural Contract
Layer 3 (Water) is a **TRANSITION FOUNDATION / VALID_DEGRADED** state-estimation pipeline for the soil–root–atmosphere continuum. It is not the Agricultural World Model. Its action-shaped fields are shadow outputs and are ignored by the canonical orchestrator; L8 owns action selection.

$$\mathbb{P}(X_t^{\text{water}} \mid X_{t-1}^{\text{water}}, Y_{1:t}, \text{weather}, \text{management})$$

* **Layer Boundary Integrity:** Consumes latent vegetation coordinates ($X_t^{\text{L2}}$: LAI, FVC, root depth proxy) and emits physical water constraints ($X_t^{\text{L3}\to\text{L4}}$: $K_s, T_{\text{deficit}}, \text{TAW}, \text{RAW}, D_r, \text{stress\_memory}$) without touching remote sensing indices or cellular biology.
* **Validation Status:** focused contract and scientific probes exist, but the package is not certified for unrestricted prescription or machine execution.

---

## 2. Transition Engine Architecture

```mermaid
graph TD
    subgraph Ingestion & Solver Selection
        L2[Layer 2 Vegetation State] --> Demand
        L0[Meteorology L0/L1] --> ET0[Penman-Monteith ET0]
        SoilDB[USDA Soil Hydraulic DB] --> Balance[Multi-Layer Soil Balance]
        SolverSel[Solver Selector: validated bucket only] --> Balance
    end

    subgraph Evapotranspiration & Flux Partitioning
        ET0 --> DualKc[Dual Kc Partitioning: Kcb, Ke]
        DualKc --> PotFlux[Potential Fluxes: Tpot, Espot]
        PotFlux --> RootZone[Root Zone Availability & Feddes U z]
    end

    subgraph Hydrological Simulation & Assimilation
        Balance --> ProgSoil[Prognostic Soil State X-]
        Obs[Sensors: TDR Probes, SMAP, Thermal] --> Assim[Water State Assimilator: 1D EnKF / OI]
        ProgSoil --> Assim
        Assim --> PostSoil[Posterior Soil State X+]
        PostSoil --> RootZone
    end

    subgraph Memory, Forecast & MPC
        RootZone --> Ks[Transpiration Stress Ks & Tdeficit]
        Ks --> Memory[Hydraulic Stress Memory Accumulator]
        PostSoil --> Forecast[Weather Ensemble Depletion Forecast]
        Forecast --> MPC[Receding Horizon MPC Optimizer]
        MPC --> Decision[Water Decision & Tradeoff Ledger]
    end

    subgraph Boundary Interfaces
        Ks --> L2Receipt[Layer 3 to Layer 2 Hydrological Constraint]
        Memory --> L4Receipt[Layer 3 to Layer 4 Biophysical Boundary Receipt]
        Ks --> L4Receipt
    end
```

---

## 3. Core Transition Modules

1. **Psychrometric & ET0 Engine** ([`layer3_water/et/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/et)):
   - Penman-Monteith daily reference ET ($ET_0$) with atmospheric provenance tracking.
   - Dual $K_c$ canopy demand partitioning ($K_{cb}, K_e$).
2. **Multi-Layer Soil Balance & Hydraulic Potentials** ([`layer3_water/soil/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/soil)):
   - Discretized 5-layer hydraulic profile.
   - Van Genuchten water retention curve inversion ($\psi_m(z), K(\theta, z)$).
   - Infiltration, surface runoff, and tipping-bucket/percolation cascade with exact mass balance closure error tracking.
3. **Data Assimilation Engine** ([`layer3_water/assimilation/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/assimilation)):
   - 1D Optimal Interpolation / Kalman Filter ($X^+ = X^- + \mathbf{K}(y - \mathbf{H}X^-)$) ingesting in-situ probes, satellite SMAP, and thermal cooling radiometer constraints.
4. **Historical Hydraulic Stress Memory Accumulator** ([`layer3_water/contracts/water_state.py`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/contracts/water_state.py)):
   - Accumulates cumulative transpiration deficit, consecutive stress days, integrated VPD stress index, and recovery rate.
5. **Physical Solver Selector** ([`layer3_water/solver/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/solver)):
   - Reports the implemented `EMPIRICAL_BUCKET`; Richards requests degrade explicitly because no validated Richards runner is installed.
6. **Ensemble Forecast Engine** ([`layer3_water/forecast/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/forecast)):
   - Probabilistic depletion trajectories $P(D_r > \text{RAW})$ across calibrated NWP weather and soil parameter ensembles.
7. **Shadow MPC Analyzer** ([`layer3_water/decision/`](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer3_water/decision)):
   - Transitional comparison output only; it does not own canonical actions.
