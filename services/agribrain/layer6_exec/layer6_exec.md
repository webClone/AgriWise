# Layer 6 Audit: Execution Engine (layer6_exec)

## 1. Executive Summary & Verification Status
Layer 6 (Execution) is the strategic work dispatch and feedback assimilation engine of the AgriBrain system. It synthesizes task plans from Layers 3, 4, and 5, verifies resource feasibility, computes execution progress, and runs biophysical solvers for solute transport, drift drift, and carbon sequestration.
* **Code Integrity:** High. Zero compile errors across all engines.
* **Smart Routing Gating:** Smart router directs calls through either the LOW-LATENCY path (FAST) or the DEEP CAUSAL path (FULL).
* **Test Status:** Core Crank-Nicolson and RothC RK4 solvers verified via pytest.

---

## 2. Granular Engine Inventory & Mapping
1. **InterventionSynthesisEngine** ([engines/intervention_synthesis.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/engines/intervention_synthesis.py)): Aggregates upstream recommendations and flags conflicts.
2. **ResourceFeasibilityEngine** ([engines/resource_feasibility.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/engines/resource_feasibility.py)): Gates execution against available labor, budget, and water quotas.
3. **DAGExecutionEngine** ([execution/dag_runner.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/execution/dag_runner.py)): Coordinates task dependencies and updates completion logs.
4. **OutcomeEvaluationEngine** ([outcomes/metrics.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/outcomes/metrics.py)): Assesses physical NDVI/VWC responses post-intervention.
5. **CalibrationEngine** ([engines/calibration.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/engines/calibration.py)): Adjusts process model noise and growth rates.
6. **Nitrogen Leaching Solver** ([engines/nitrogen_leaching.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/engines/nitrogen_leaching.py)): 1D solute transport Crank-Nicolson solver.
7. **VPD Spray Window Solver** ([engines/vpd_spray_window.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/engines/vpd_spray_window.py)): 3D Lagrangian droplet drift simulator.
8. **Carbon Sequestration Solver** ([engines/carbon_sequestration.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_exec/engines/carbon_sequestration.py)): 5-pool RothC soil carbon RK4 simulator.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - `Layer6Input` containing upstream results, operational resources, active evidence batches, and previous DAG status.
* **Outputs Generated:**
  - `Layer6Output` detailing authorized portfolios, resolved conflicts, execution status logs, outcome projections, and carbon balance estimates.

---

## 4. Key Mathematical Formulations

### A. 1D Solute Transport Crank-Nicolson Solver
Solves the coupled Richards / Advection-Dispersion Equation (ADE) for nitrogen ($NO_3^-$) leaching across 10 soil layers ($dz=0.1$m) daily:
$$\frac{\partial C}{\partial t} = D \frac{\partial^2 C}{\partial z^2} - v \frac{\partial C}{\partial z} - S(z)$$
Where $D = D_0 + \alpha |v|$ is local dispersion, $v$ is pore water velocity, and $S(z)$ is crop root nitrogen uptake. Solved using the tridiagonal Thomas algorithm.

### B. 3D Lagrangian Spray Droplet Drift & Evaporation Simulator
Simulates droplet trajectories ($100\mu\text{m}$ to $400\mu\text{m}$ sizes) under log wind profile conditions:
$$m \frac{d^2 \mathbf{x}}{dt^2} = \mathbf{F}_{drag} + \mathbf{F}_{gravity} + \mathbf{F}_{buoyancy}$$
Where drag force is modeled using Schiller-Naumann sphere correlations, and droplet evaporation diameter decreases with VPD:
$$\frac{d(D^2)}{dt} = -\lambda_{evap} \cdot \text{VPD} \quad \text{where } e_{sat}(T) = 0.61078 \cdot e^{\frac{17.27 T}{T+237.3}}$$

### C. RothC Soil Carbon Pool Solver (RK4 integration)
Integrates 5 carbon pools (Decomposable Plant Material DPM, Resistant Plant Material RPM, Microbial Biomass BIO, Humified Organic Matter HUM, Inert Organic Matter IOM) over 7-day execution windows:
$$\frac{d\mathbf{C}}{dt} = \mathbf{A} \cdot \mathbf{k} \cdot \rho_{env} \cdot N_{limit} \cdot \mathbf{C} + \mathbf{In}_{carbon}$$
Where $\rho_{env} = f_T(T) \cdot f_W(W)$ is the environmental scaling factor, and integration is solved via a 4th Order Runge-Kutta (RK4) routine.

### D. Shoelace Polygon Area
Computes actual plot boundaries (hectares) to calibrate application volumes:
$$\text{Area} = \frac{1}{2} \left| \sum_{i=1}^n (x_i y_{i+1} - x_{i+1} y_i) \right| \quad (\text{projected from coordinates})$$

---

## 5. Audit Recommendations
1. **Dynamic Soil Moisture Coupling:** Feed real-time telemetry soil moisture sensors into the 1D Crank-Nicolson boundary conditions.
2. **Expand Spray Drift Physics:** Incorporate boom height, tractor speed, and specific nozzle classifications into the Lagrangian simulator.
