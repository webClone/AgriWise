# MESIA: Multi-Environment Spectrum Intelligence Architecture
## Opportunistic Radio Environmental Sensing, Physical Metrology & Epistemic Governance

---

## 1. Executive Summary & Maturity Status

**MESIA** (*Multi-Environment Spectrum Intelligence Architecture*) is the passive, opportunistic electromagnetic observatory of AgriBrain. Operating at **TRL 1–2** (*Research Demonstrator* as of Release 6.1 / August 2026), MESIA continuously surveils ambient radio-frequency signals of opportunity (SoOP)—including terrestrial digital broadcast television (DVB-T/T2), cellular downlinks (LTE/5G), navigation constellations (GNSS-R GPS/Galileo/BeiDou), ambient local area networks (Wi-Fi 802.11bf CSI), and spaceborne bistatic reflectometry (NASA CYGNSS, Sentinel-1 C-SAR)—to extract physical biophysical properties of agricultural parcels without deploying active dedicated transmitters.

### Epistemic Boundaries & Non-Negotiable Constraints
- **TRL 1–2 Boundary**: MESIA is strictly an electromagnetic observation demonstrator and hypothesis generator.
- **Zero Actuation Authority**: MESIA has **ZERO** direct field actuation, irrigation, or fertilizer control authority. All outputs are strictly advisory `evidence_proposal` objects.
- **ASMAE Owns the Posterior**: MESIA never maintains a competing biological truth model. ASMAE (*Adaptive Spatial Multimodal Agronomic Engine*) owns the agricultural posterior and biophysical lattice.
- **AgriBrain Layer 0 Fail-Closed Gating**: MESIA proposals are routed through the AgriBrain Layer 0 evidence spine. Uncalibrated, out-of-epoch, or nuisance-contaminated observations are quarantined immediately.

---

## 2. The 10 Constitutional Principles (P-01 through P-10)

MESIA adheres to ten immutable constitutional principles embedded directly into type invariants, contract validators, and automated CI/CD security scanning gates:

| Principle ID | Name | Architectural & Operational Meaning |
|---|---|---|
| **P-01** | **No Universal-Receiver Fiction** | A receiver coverage manifest and geodetic sensitivity profile must exist before scanning. MESIA never asserts ubiquitous or continuous coverage where hardware geometry does not support it. |
| **P-02** | **Discover Before Identify** | Physical detection records an energy or phase disturbance (`WaveCandidate`); protocol identity is an asynchronous, evidence-gated classification step. |
| **P-03** | **Identify Before Sense** | Agronomic biophysical interpretation requires `PROTOCOL_CONFIRMED` or `CONTROLLED_SOURCE` status. Unidentified spectral energy is never inverted into soil moisture. |
| **P-04** | **Native Evidence Survives** | Raw IQ samples, CSI matrices, range Doppler maps, SNR traces, and SigMF descriptors remain immutable, content-addressed (SHA-256), and replayable in perpetuity. |
| **P-05** | **No Raw-Phase Stitching Across Independent RATs** | Carrier phase coherence is never stitched across unsynchronized radio access technologies. Fusion occurs exclusively at the calibrated likelihood or constraint level. |
| **P-06** | **Configuration is Part of the Measurement** | Six distinct epoch domains (Geometry, Instrument, Network, Coexistence, Calibration, and Software Model) are mandatory inputs. If an epoch changes, previous calibration ceases. |
| **P-07** | **UNKNOWN is a Valid Result** | Ambiguous, out-of-distribution, or unfamiliar spectral events are retained explicitly as `UNKNOWN` rather than forced into known protocol classes. |
| **P-08** | **ASMAE Owns the Posterior & Two-State Decoupling** | State space is split into agronomic states ($\mathbf{x}_{\text{agri}}$) and instrument/nuisance states ($\mathbf{x}_{\text{inst}}$). Hardware drift is never attributed to soil drying. |
| **P-09** | **Capabilities Qualify Separately** | A cluster or receiver is never globally certified; each frequency band, spatial stratum, target variable, and use-case qualifies via an independent authority record. |
| **P-10** | **Fail Closed and Revoke** | Any failure in calibration drift, holdout closure, spatial boundary isolation, or sensor pose demotes affected evidence to `QUARANTINED` with automated revocation. |

---

## 3. Mathematical & Physical Foundations

### 3.1 Free Space Path Loss (FSPL) & Friis Link Budget
For opportunistic terrestrial emitters (cellular towers, broadcast masts), the isotropic path loss $L_{\text{FSPL}}$ in decibels over distance $d$ (meters) and carrier frequency $f$ (Hertz) is modeled as:
$$L_{\text{FSPL}}(d, f) = 20 \log_{10}(d) + 20 \log_{10}(f) + 20 \log_{10}\left(\frac{4\pi}{c}\right) = 20 \log_{10}(d) + 20 \log_{10}(f) - 147.55$$

The received signal reference power $P_{\text{rx}}$ at the parcel receiver incorporates transmit power $P_{\text{tx}}$, antenna gains $G_{\text{tx}}, G_{\text{rx}}$, and excess environmental attenuation $A_{\text{excess}}$:
$$P_{\text{rx}} = P_{\text{tx}} + G_{\text{tx}} + G_{\text{rx}} - L_{\text{FSPL}}(d, f) - A_{\text{excess}}$$

### 3.2 ITU-R P.833 Foliar and Canopy Attenuation
Forward scatter attenuation through vegetation canopy chord length $d_{\text{canopy}}$ (meters) uses the empirical ITU-R P.833 formulation adjusted for ambient relative humidity $\text{RH}$ (%):
$$\gamma_{\text{veg}}(f, \text{RH}) = 0.075 \cdot \left(\frac{\text{RH}}{60.0}\right) \cdot \left(\frac{f}{10^9}\right)^{0.2} \quad [\text{dB/m}]$$
$$A_{\text{canopy}} = \gamma_{\text{veg}} \cdot d_{\text{canopy}}$$

The non-dimensional Canopy Water Index ($\text{CWI} \in [0, 1]$) is inferred from excess foliar attenuation:
$$\text{CWI} = \max\left(0.0, \min\left(1.0, 1.0 - \exp\left(-0.015 \cdot A_{\text{canopy}}\right)\right)\right)$$

### 3.3 Complex Dielectric Permittivity & Soil Moisture Inversion
The soil complex relative dielectric permittivity $\varepsilon = \varepsilon' - j\varepsilon''$ is related to volumetric water content ($\theta_v = \text{VWC}$) through the semi-empirical Dobson 4-component mixing model and Topp's polynomial:
$$\varepsilon'(\theta_v) = 3.03 + 9.3 \theta_v + 146.0 \theta_v^2 - 76.7 \theta_v^3$$
$$\theta_v(\varepsilon') = -0.053 + 0.0292 \varepsilon' - 5.5 \times 10^{-4} (\varepsilon')^2 + 4.3 \times 10^{-6} (\varepsilon')^3$$

Skin depth $\delta_s$ for electromagnetic penetration into the soil volume at frequency $\omega = 2\pi f$:
$$\delta_s = \frac{1}{\omega} \left[ \frac{\mu_0 \varepsilon_0 \varepsilon'}{2} \left( \sqrt{1 + \left(\frac{\varepsilon'' + \frac{\sigma}{\omega \varepsilon_0}}{\varepsilon'}\right)^2} - 1 \right) \right]^{-1/2}$$

| Radio Channel | Frequency Band | Skin Depth ($\delta_s$) | Physical Target Stratum |
|---|---|---|---|
| **DVB-T2 Broadcast UHF** | 470 – 700 MHz | 35 – 100 cm | Deep Subsoil / Groundwater Boundary |
| **GNSS-R L-Band (L1/L2/L5)** | 1176 – 1575 MHz | 5 – 30 cm | Crop Root-Zone Volumetric Water Content |
| **Cellular LTE-1800 / 2100** | 1800 – 2170 MHz | 2 – 10 cm | Shallow Root-Zone & Canopy Attenuation |
| **Wi-Fi CSI (OFDM Subcarriers)**| 2412 – 2484 MHz | 0.5 – 5 cm | Surface Skin Layer & Foliar Interception |
| **Sentinel-1 C-SAR (Bistatic)**| 5.405 GHz | 0.2 – 1.5 cm | Boundary Roughness & Topsoil Permittivity |

### 3.4 Fresnel Reflection Coefficients & Ground Bounce
For bistatic specular reflection at grazing angle $\psi$ (or incidence angle $\theta_i = 90^\circ - \psi$):
$$R_H = \frac{\sin\psi - \sqrt{\varepsilon - \cos^2\psi}}{\sin\psi + \sqrt{\varepsilon - \cos^2\psi}}$$
$$R_V = \frac{\varepsilon \sin\psi - \sqrt{\varepsilon - \cos^2\psi}}{\varepsilon \sin\psi + \sqrt{\varepsilon - \cos^2\psi}}$$
Surface soil reflectivity $\Gamma_0 = |R|^2$ is adjusted for surface RMS roughness height $s$ via the Beckmann-Kirchhoff factor:
$$\Gamma_{\text{rough}}(\psi) = \Gamma_0(\psi) \cdot \exp\left( - \left(\frac{4\pi s}{\lambda} \sin\psi\right)^2 \right)$$

### 3.5 1D Cell-Averaging CFAR (CA-CFAR) Detection
Peak detection over power spectrum bins $X[k]$ computes threshold $T[k] = \alpha \cdot P_{\text{noise}}$ using $N_{\text{train}} = 2 \cdot N_{\text{cells}}$ reference cells excluding $N_{\text{guard}}$ guard cells around the Cell Under Test (CUT):
$$\alpha = N_{\text{train}} \cdot \left( P_{fa}^{-1 / N_{\text{train}}} - 1 \right)$$
$$P_{\text{noise}}[k] = \frac{1}{2 N_{\text{cells}}} \left( \sum_{i=k-N_{\text{guard}}-N_{\text{cells}}}^{k-N_{\text{guard}}-1} X[i] + \sum_{i=k+N_{\text{guard}}+1}^{k+N_{\text{guard}}+N_{\text{cells}}} X[i] \right)$$

---

## 4. Two-State Decoupling & ASMAE P-08 Evidence Proposals

### 4.1 State-Space Separation $\mathbf{x} = [\mathbf{x}_{\text{agri}}, \mathbf{x}_{\text{inst}}]^T$
To strictly prevent instrument degradation, temperature drift, or multipath antenna tilt from masquerading as biological water extraction, MESIA enforces two-state decoupling:
- $\mathbf{x}_{\text{agri}}$: Topsoil VWC (0–5 cm), root-zone VWC (5–30 cm), deep subsoil VWC (30–100 cm), Canopy Water Index, and leaf surface wetness.
- $\mathbf{x}_{\text{inst}}$: Front-end receiver temperature, thermal gain drift ($0.045\text{ dB/}^\circ\text{C}$), antenna displacement ($|\Delta\mathbf{r}| < 1\text{ cm}$), cellular handover flags, and 50$\Omega$ load calibration status.

### 4.2 Bayesian Nuisance Attribution
When an RF power delta $\Delta P$ is observed, the Bayesian Nuisance Model evaluates likelihoods across mutually exclusive physical causes:
$$P(\text{cause}_i \mid \Delta P, T, \text{RH}, v_{\text{wind}}, \Delta\mathbf{r}) \propto P(\Delta P \mid \text{cause}_i) \cdot P(\text{cause}_i)$$
Causes evaluated: `SOIL_MOISTURE_CHANGE`, `DEW_CONDENSATION`, `FOLIAR_WIND_FLUTTER`, `THERMAL_DRIFT`, `ANTENNA_DISPLACEMENT`, and `CELL_HANDOVER`. If dominant probability lies outside `SOIL_MOISTURE_CHANGE`, soil VWC update is **SUPPRESSED**.

### 4.3 Kalman Innovation Proposal Format
Proposals emitted to ASMAE follow the standard innovation syntax:
$$\nu_k = y_k - \mathcal{H}(\hat{\mathbf{x}}_k^-), \quad \mathbf{S}_k = \mathbf{H}_k \mathbf{P}_k^- \mathbf{H}_k^T + \mathbf{R}_k \cdot \kappa_{\text{IMM}}$$
Where:
- $\nu_k$ is the bounded innovation value (e.g., $\Delta\text{VWC}$ in $\text{m}^3/\text{m}^3$).
- $\mathbf{R}_k$ is ISO GUM expanded metrological variance.
- $\kappa_{\text{IMM}} \ge 1.0$ is the Interacting Multiple Model regime inflation factor (inflating variance during sirocco winds or dew formation).
- `decision_eligible` is strictly hard-coded to `False`.

---

## 5. Subsystem & Component Directory Inventory

MESIA comprises 26 modular subpackages structured under `services/agribrain/mesia/`:

```
services/agribrain/mesia/
├── assimilation/        # Dynamic belief updating & spatial Kalman assimilation
├── behaviour/           # Source-specific measurement contracts & behaviour primitives
├── cellular/            # LTE/5G downlink forward-scatter & cell topology correlator
├── constitution/        # Machine-readable P-01..P-10 constitutional rule definitions
├── contracts/           # 22 typed frozen dataclass contracts (Authority, Epochs, Waves)
├── control_plane/       # Central observatory orchestration & scheduler
├── data/                # Ephemeris TLEs, OSM telecom cache, and in-situ capture logs
├── discovery/           # Multi-detector bank (CA-CFAR, OS-CFAR, Kurtosis, Chirp)
├── epoch_authority/     # Central authority managing the 6 lineage epoch domains
├── experiments/         # Specialized experimental pipelines (Wildfire, FDTD, etc.)
├── governance/          # CI/CD claim scanner and scientific integrity validator
├── identity/            # OpenSet waveform classification & deterministic protocol rules
├── integration.py       # AgriBrain Layer 0 evidence spine admission bridge
├── integration_layer3.py# AgriBrain Layer 3 root-zone water balance coupling
├── lanes/               # Signal-specific processing pipelines (GNSS-R, CSI, UHF, Cell)
├── learning/            # Physics-informed neural receivers & ASMAE evaluators
├── metrology/           # ISO GUM compliant uncertainty budgets & coverage graphs
├── omega/               # Autonomous validation & benchmark verification
├── ontology/            # Canonical identity states and confirmation level enums
├── operations/          # Live observatory execution and health monitoring
├── opportunistic/       # In-situ ground-wave decoders and spatial ray tracers
├── planning/            # Cadastral sweep, dwell, and priority survey planning
├── radio_families/      # RAT-specific physics models (DVB, LTE, Wi-Fi, GNSS)
├── service.py           # MesiaProductionService entry-point (scan_plot_spectrum)
├── spatial_isolation/   # 5-tier boundary protection & cadastral buffer erosion
├── storage/             # Content-addressed immutable evidence repository (SHA-256)
├── tests/               # Dedicated test suite (6 files, 101 tests, 100% passing)
├── truth/               # Controlled calibration targets & reference benchmarks
└── validation/          # Dual-closure verification & holdout prediction loops
```

---

## 6. Verification & Test Suite

The test suite in `services/agribrain/mesia/tests/` verifies the entire mathematical, metrological, and governance pipeline:

| Test File | Tests | Focus Areas |
|---|---|---|
| `test_mesia_pipeline_scenarios.py` | 51 | Multi-agroclimatic scans (Mitidja, Biskra, Sahel), CA-CFAR discovery, open-set classification, IMM regime filtering, ISO GUM uncertainty budgets, 2.5D vertical strata. |
| `test_mesia_truth_and_security.py` | 17 | Zero unreviewed claim scanner, anti-spoofing rejection, epoch lineage validation, fail-closed revocation on uncalibrated streams. |
| `test_mesia_opportunistic.py` | 16 | Opportunistic LTE downlink forward scatter, canopy chord intersection geometry, grazing angle penetration. |
| `test_mesia_full_pipeline_verification.py` | 7 | Full end-to-end multi-radio pipeline, SigMF CSI classification, Richards infiltration limits, Magnus dew depression. |
| `test_mesia_deployment_designer.py` | 7 | Spatial geometry, receiver placement optimization, Fresnel ellipse boundary coverage, link budget calculations. |
| `test_mesia_contract_upgrades.py` | 3 | Contract upgrade compatibility, content hash determinism, serialization schema immutability. |
| **Total** | **101** | **100% Pass Rate across all test suites** |

---

## 7. Execution & Regression Commands

### Run MESIA Test Suite:
```bash
py -3 -m pytest services/agribrain/mesia/tests/ -v
```

### Run Full AgriBrain Multi-Layer Regression (L0 through L10 + MESIA):
```bash
py -3 -m pytest services/agribrain/layer0/tests services/agribrain/layer0_5/tests services/agribrain/layer1/tests services/agribrain/layer2/tests services/agribrain/layer3/tests services/agribrain/layer4/tests services/agribrain/layer5/tests services/agribrain/layer6/tests services/agribrain/layer7/tests services/agribrain/layer8/tests services/agribrain/layer9/tests services/agribrain/layer10_sire/tests services/agribrain/mesia/tests/ -q
```
