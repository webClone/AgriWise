# Layer 6 Audit: Yield Forecast Engine (layer6_yield)

## 1. Executive Summary & Verification Status
This sub-module of Layer 6 is responsible for modeling the final harvest yield and economic outcomes. It projects final crop dry matter yields using hybrid biophysical indices and computes crop-specific harvest windows.
* **Code Integrity:** High. Standard mathematical interfaces.
* **Test Status:** Core forecasting logic passes regression checks.
* **Integration Status:** Feeds decision logic back to planning templates.

---

## 2. Granular Engine Inventory & Mapping
1. **YieldForecastEngine** ([yield_forecast.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_yield/yield_forecast.py)): Formulates potential and restricted crop yields using baseline biomass values, harvest indexes, and stress loss factors.
2. **HarvestOptimizer** ([harvest_optimizer.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_yield/harvest_optimizer.py)): Prescribes optimal harvest timing based on crop moisture and upcoming weather.
3. **ProfitabilityEngine** ([profitability.py](file:///c:/Users/E-C/Desktop/agriwise/services/agribrain/layer6_yield/profitability.py)): Projects economic profitability profiles, gross margins, and return on investment.

---

## 3. Inputs & Outputs (Contracts)
* **Inputs Ingested:**
  - Crop type, total seasonal simulated biomass (kg/ha), and cumulative stress loss factors (water, nutrient, disease).
* **Outputs Generated:**
  - Aligned yield predictions (`yield_mean_t_ha`, `yield_p10`, `yield_p90`), trust levels, and loss attribution splits.
  - Optimal harvest scheduling and profit estimates.

---

## 4. Key Mathematical Formulations

### A. Hybrid Yield Prediction Model
Predicts the final grain or dry matter yield using potential yield scaled by stress coefficients:
$$Y_{final} = Y_{potential} \cdot (1 - \text{TotalLoss})$$
Where:
* $Y_{potential} = \text{Biomass}_{final} \cdot \frac{HI}{1000.0}$ (with $HI$ representing the crop-specific Harvest Index).
* $\text{TotalLoss} = 1.0 - (1 - l_{water}) \cdot (1 - l_{nutrient}) \cdot (1 - l_{disease})$ (capped at $0.70$ max reduction unless complete crop failure is confirmed).

### B. Yield Uncertainty Propagation
Computes the standard deviation of yield prediction based on biomass and stress confidences:
$$CV = 0.1 + (1 - \text{Confidence}_{biomass}) \cdot 0.2 + (1 - \text{Confidence}_{stress}) \cdot 0.15$$
$$\sigma = Y_{final} \cdot CV$$
$$Y_{p10} = Y_{final} - 1.645 \cdot \sigma$$
$$Y_{p90} = Y_{final} + 1.645 \cdot \sigma$$

### C. Profitability Net Margin
$$\text{Net Profit} = \left(Y_{final} \cdot \text{CropPrice}\right) - \sum \text{InputCosts} - \text{FixedOperationalCosts}$$

---

## 5. Audit Recommendations
1. **Calibrate Harvest Indexes ($HI$):** Dynamically adjust $HI$ based on early-season moisture deficit impacts on crop seedheads.
2. **Dynamic Price Feeds:** Integrate real-time market crop price feeds to make economic profitability projections more reactive.
