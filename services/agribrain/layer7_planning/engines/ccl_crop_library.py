from dataclasses import dataclass, field
from typing import Dict, List, Optional
from layer7_planning.schema import SuitabilityDriver

@dataclass
class CultivarOption:
    name: str # e.g. "Spunta", "Desiree"
    maturity_days: int # Days from plant to harvest
    base_yield_t_ha: float
    disease_resistance: List[str] # e.g. ["late_blight", "nematode"]
    water_demand_class: str # "HIGH", "MODERATE", "LOW"

@dataclass
class CropProfile:
    id: str # internal key
    display_name: str
    
    # Thermal Requirements
    base_temp_c: float
    optimal_temp_min_c: float
    optimal_temp_max_c: float
    frost_sensitivity_c: float
    flowering_heat_stress_c: float
    target_gdd: float # Growing degree days required to mature
    
    # Soil & Operations
    preferred_soil_type: List[str]
    max_planting_rain_7d_mm: float # Workability limit (compaction / rot risk)
    min_planting_temp_c: float # Required for sprouting/germination
    
    # Calendars (Agro-climatic regions mapping -> [start_month, end_month])
    planting_windows: Dict[str, List[Dict[str, int]]] 
    
    # Cultivars available
    varieties: List[CultivarOption]
    
    # Economics (Base defaults, overridden by user context)
    default_price_per_ton: float 
    base_production_cost_per_ha: float 

# Compact factory to avoid massive file size
def _build_crop(id, name, tbase, tmin, tmax, frost, heat, gdd, soils, max_rain, min_ptemp, price, cost, base_yield=15.0):
    return CropProfile(
        id=id, display_name=name, base_temp_c=tbase, optimal_temp_min_c=tmin, optimal_temp_max_c=tmax,
        frost_sensitivity_c=frost, flowering_heat_stress_c=heat, target_gdd=gdd,
        preferred_soil_type=soils, max_planting_rain_7d_mm=max_rain, min_planting_temp_c=min_ptemp,
        planting_windows={"north_africa": [{"start_month": 1, "end_month": 12}]}, # Simplified for now
        varieties=[CultivarOption("Standard", 120, base_yield, [], "MODERATE")],
        default_price_per_ton=price, base_production_cost_per_ha=cost
    )

_CROP_DATA = [
    # MENA & Mediterranean Focus
    ("potato", "Potato", 7.0, 15.0, 25.0, -1.0, 28.0, 1400.0, ["loam", "sandy loam"], 40.0, 8.0, 400.0, 3000.0, 35.0),
    ("wheat", "Wheat", 0.0, 10.0, 25.0, -8.0, 30.0, 2000.0, ["loam", "clay loam"], 55.0, 4.0, 300.0, 800.0, 5.0),
    ("barley", "Barley", 0.0, 12.0, 25.0, -9.0, 32.0, 1800.0, ["loam", "sandy loam"], 50.0, 4.0, 250.0, 700.0, 4.5),
    ("olive", "Olive", 10.0, 15.0, 30.0, -5.0, 35.0, 3000.0, ["loam", "sandy loam", "clay loam"], 60.0, 12.0, 1200.0, 1500.0, 8.0),
    ("date_palm", "Date Palm", 18.0, 25.0, 40.0, -3.0, 45.0, 4000.0, ["sandy loam", "sand"], 30.0, 20.0, 2000.0, 2500.0),
    ("fig", "Fig", 10.0, 18.0, 32.0, -8.0, 38.0, 2500.0, ["loam", "clay loam"], 50.0, 15.0, 1500.0, 1800.0),
    ("almond", "Almond", 7.0, 15.0, 30.0, -6.0, 35.0, 2200.0, ["loam", "sandy loam"], 45.0, 12.0, 4000.0, 2000.0),
    ("grape", "Grape", 10.0, 15.0, 30.0, -5.0, 35.0, 2500.0, ["loam", "clay loam", "sandy loam"], 40.0, 12.0, 800.0, 2500.0),
    ("pomegranate", "Pomegranate", 10.0, 25.0, 35.0, -10.0, 40.0, 2800.0, ["loam", "clay loam"], 45.0, 15.0, 1000.0, 1600.0),
    ("citrus_orange", "Orange", 13.0, 22.0, 32.0, -2.0, 38.0, 3200.0, ["sandy loam", "loam"], 50.0, 15.0, 600.0, 2200.0),
    ("citrus_lemon", "Lemon", 13.0, 20.0, 30.0, -1.0, 35.0, 3000.0, ["sandy loam", "loam"], 50.0, 15.0, 800.0, 2500.0),
    ("pistachio", "Pistachio", 7.0, 25.0, 35.0, -10.0, 40.0, 2600.0, ["sandy loam", "loam"], 40.0, 15.0, 5000.0, 2000.0),
    ("chickpea", "Chickpea", 5.0, 15.0, 28.0, -4.0, 32.0, 1500.0, ["loam", "sandy loam"], 35.0, 10.0, 800.0, 600.0),
    ("lentil", "Lentil", 5.0, 15.0, 25.0, -6.0, 30.0, 1400.0, ["loam", "clay loam"], 40.0, 8.0, 900.0, 500.0),
    ("fava_bean", "Fava Bean", 5.0, 15.0, 22.0, -5.0, 28.0, 1600.0, ["loam", "clay loam"], 45.0, 8.0, 600.0, 700.0),
    ("garlic", "Garlic", 4.0, 12.0, 24.0, -8.0, 28.0, 1800.0, ["loam", "sandy loam"], 40.0, 8.0, 1500.0, 2000.0),
    ("onion", "Onion", 5.0, 15.0, 25.0, -4.0, 30.0, 1600.0, ["loam", "sandy loam", "silt loam"], 40.0, 10.0, 500.0, 1500.0),
    ("cumin", "Cumin", 9.0, 20.0, 30.0, -2.0, 35.0, 1400.0, ["loam", "sandy loam"], 30.0, 12.0, 3000.0, 800.0),
    ("coriander", "Coriander", 5.0, 15.0, 25.0, -3.0, 30.0, 1200.0, ["loam", "silt loam"], 40.0, 10.0, 1200.0, 600.0),
    ("saffron", "Saffron", 5.0, 15.0, 25.0, -15.0, 30.0, 1800.0, ["loam", "sandy loam", "clay loam"], 35.0, 10.0, 50000.0, 5000.0),
    ("carob", "Carob", 10.0, 20.0, 32.0, -4.0, 38.0, 2800.0, ["loam", "clay loam", "sandy loam"], 50.0, 15.0, 800.0, 1000.0),
    ("argan", "Argan", 12.0, 22.0, 35.0, -2.0, 45.0, 3500.0, ["sandy loam", "sand", "loam"], 30.0, 15.0, 10000.0, 1500.0),
    
    # Tropical & Sub-Saharan Focus
    ("cassava", "Cassava", 18.0, 25.0, 32.0, 2.0, 38.0, 3500.0, ["sandy loam", "loam"], 50.0, 20.0, 150.0, 800.0),
    ("yam", "Yam", 20.0, 25.0, 30.0, 5.0, 35.0, 3000.0, ["loam", "sandy loam"], 45.0, 22.0, 250.0, 1000.0),
    ("sweet_potato", "Sweet Potato", 15.0, 22.0, 28.0, 2.0, 35.0, 2000.0, ["sandy loam", "loam"], 40.0, 18.0, 300.0, 1200.0),
    ("sorghum", "Sorghum", 10.0, 25.0, 35.0, -1.0, 40.0, 2500.0, ["loam", "clay loam", "sandy loam"], 35.0, 15.0, 200.0, 600.0),
    ("pearl_millet", "Pearl Millet", 12.0, 28.0, 38.0, 0.0, 42.0, 2200.0, ["sandy loam", "sand", "loam"], 30.0, 18.0, 180.0, 500.0),
    ("finger_millet", "Finger Millet", 10.0, 25.0, 35.0, 0.0, 40.0, 2300.0, ["loam", "clay loam"], 35.0, 15.0, 220.0, 550.0),
    ("cowpea", "Cowpea", 12.0, 25.0, 35.0, 1.0, 40.0, 1800.0, ["loam", "sandy loam"], 35.0, 18.0, 400.0, 600.0),
    ("groundnut", "Groundnut (Peanut)", 14.0, 25.0, 30.0, 2.0, 38.0, 2200.0, ["sandy loam", "loam"], 40.0, 18.0, 800.0, 900.0),
    ("plantain", "Plantain", 15.0, 25.0, 32.0, 5.0, 38.0, 4000.0, ["loam", "clay loam"], 60.0, 20.0, 300.0, 1500.0),
    ("banana", "Banana", 15.0, 26.0, 32.0, 4.0, 38.0, 4200.0, ["loam", "clay loam", "silt loam"], 60.0, 20.0, 400.0, 1800.0),
    ("cocoa", "Cocoa", 18.0, 25.0, 30.0, 10.0, 35.0, 4500.0, ["loam", "clay loam"], 50.0, 22.0, 2500.0, 1200.0),
    ("coffee_arabica", "Coffee (Arabica)", 15.0, 18.0, 24.0, 2.0, 30.0, 3000.0, ["loam", "clay loam", "silt loam"], 50.0, 18.0, 3500.0, 1800.0),
    ("coffee_robusta", "Coffee (Robusta)", 18.0, 24.0, 30.0, 5.0, 35.0, 3500.0, ["loam", "clay loam"], 55.0, 20.0, 2000.0, 1500.0),
    ("tea", "Tea", 12.0, 18.0, 25.0, -2.0, 32.0, 2800.0, ["loam", "clay loam", "silt loam"], 60.0, 15.0, 2500.0, 2000.0),
    ("sugarcane", "Sugarcane", 15.0, 25.0, 35.0, -1.0, 40.0, 4500.0, ["loam", "clay loam", "silt loam"], 55.0, 20.0, 50.0, 1500.0),
    ("pineapple", "Pineapple", 15.0, 25.0, 32.0, 2.0, 38.0, 3800.0, ["sandy loam", "loam"], 40.0, 20.0, 400.0, 1500.0),
    ("mango", "Mango", 15.0, 25.0, 35.0, 0.0, 45.0, 3500.0, ["loam", "sandy loam", "clay loam"], 45.0, 20.0, 600.0, 1200.0),
    ("papaya", "Papaya", 18.0, 25.0, 32.0, 5.0, 38.0, 3000.0, ["loam", "sandy loam"], 50.0, 20.0, 300.0, 1000.0),
    ("avocado", "Avocado", 10.0, 20.0, 28.0, -2.0, 35.0, 2800.0, ["loam", "sandy loam"], 45.0, 15.0, 1500.0, 2500.0),
    ("cashew", "Cashew", 15.0, 25.0, 35.0, 5.0, 40.0, 3200.0, ["sandy loam", "loam", "sand"], 40.0, 20.0, 1200.0, 1000.0),
    ("macadamia", "Macadamia", 10.0, 20.0, 28.0, -1.0, 35.0, 3000.0, ["loam", "sandy loam", "clay loam"], 45.0, 15.0, 3000.0, 2200.0),
    ("sesame", "Sesame", 15.0, 25.0, 35.0, 5.0, 40.0, 1800.0, ["loam", "sandy loam"], 35.0, 20.0, 1500.0, 600.0),
    ("teff", "Teff", 10.0, 20.0, 28.0, 0.0, 35.0, 1600.0, ["loam", "clay loam", "silt loam"], 40.0, 15.0, 800.0, 500.0),
    ("okra", "Okra", 15.0, 25.0, 35.0, 5.0, 40.0, 1800.0, ["loam", "sandy loam", "clay loam"], 45.0, 18.0, 600.0, 1200.0),
    ("taro", "Taro", 15.0, 25.0, 32.0, 5.0, 38.0, 3500.0, ["loam", "clay loam", "silt loam"], 60.0, 20.0, 500.0, 1500.0),
    ("bambara_groundnut", "Bambara Groundnut", 15.0, 25.0, 35.0, 5.0, 40.0, 2000.0, ["sandy loam", "sand", "loam"], 35.0, 20.0, 600.0, 700.0),
    ("pigeon_pea", "Pigeon Pea", 15.0, 25.0, 35.0, 0.0, 40.0, 2200.0, ["loam", "sandy loam", "clay loam"], 40.0, 18.0, 700.0, 800.0),

    # Major Global Commodities & General
    ("corn", "Corn", 10.0, 20.0, 30.0, -1.0, 35.0, 2700.0, ["loam", "silt loam"], 50.0, 12.0, 180.0, 1200.0),
    ("tomato", "Tomato", 10.0, 18.0, 28.0, 0.0, 32.0, 1200.0, ["loam"], 35.0, 15.0, 800.0, 5000.0),
    ("cotton", "Cotton", 15.0, 25.0, 35.0, 2.0, 38.0, 2200.0, ["loam", "sandy loam"], 45.0, 18.0, 1500.0, 1800.0),
    ("soybean", "Soybean", 10.0, 20.0, 30.0, -2.0, 35.0, 1800.0, ["loam", "clay loam"], 40.0, 15.0, 400.0, 600.0),
    ("apple", "Apple", 5.0, 18.0, 25.0, -15.0, 35.0, 2200.0, ["loam", "clay loam"], 50.0, 8.0, 600.0, 3000.0),
    ("pear", "Pear", 5.0, 18.0, 25.0, -15.0, 35.0, 2300.0, ["loam", "clay loam"], 50.0, 8.0, 700.0, 3000.0),
    ("strawberry", "Strawberry", 5.0, 15.0, 25.0, -5.0, 30.0, 1500.0, ["loam", "sandy loam"], 35.0, 10.0, 2500.0, 6000.0),
    ("blueberry", "Blueberry", 5.0, 18.0, 25.0, -15.0, 30.0, 2000.0, ["loam", "sandy loam"], 40.0, 10.0, 4000.0, 5000.0),
    ("raspberry", "Raspberry", 5.0, 18.0, 25.0, -10.0, 30.0, 1800.0, ["loam", "sandy loam"], 40.0, 10.0, 3500.0, 4500.0),
    ("blackberry", "Blackberry", 5.0, 18.0, 25.0, -10.0, 30.0, 1900.0, ["loam", "sandy loam"], 40.0, 10.0, 3000.0, 4000.0),
    ("cabbage", "Cabbage", 0.0, 15.0, 22.0, -5.0, 28.0, 1200.0, ["loam", "clay loam"], 45.0, 5.0, 200.0, 1500.0),
    ("broccoli", "Broccoli", 0.0, 15.0, 20.0, -3.0, 26.0, 1100.0, ["loam", "clay loam"], 45.0, 5.0, 600.0, 2000.0),
    ("cauliflower", "Cauliflower", 0.0, 15.0, 20.0, -3.0, 26.0, 1200.0, ["loam", "clay loam"], 45.0, 5.0, 700.0, 2200.0),
    ("carrot", "Carrot", 5.0, 15.0, 22.0, -2.0, 28.0, 1400.0, ["loam", "sandy loam"], 40.0, 8.0, 300.0, 1800.0),
    ("beetroot", "Beetroot", 5.0, 15.0, 22.0, -2.0, 28.0, 1300.0, ["loam", "sandy loam"], 40.0, 8.0, 250.0, 1500.0),
    ("radish", "Radish", 5.0, 15.0, 22.0, -4.0, 28.0, 800.0, ["loam", "sandy loam"], 35.0, 8.0, 300.0, 1000.0),
    ("turnip", "Turnip", 0.0, 12.0, 20.0, -5.0, 26.0, 1000.0, ["loam", "sandy loam"], 40.0, 5.0, 200.0, 1200.0),
    ("spinach", "Spinach", 0.0, 12.0, 20.0, -6.0, 26.0, 800.0, ["loam", "sandy loam"], 40.0, 5.0, 600.0, 1800.0),
    ("lettuce", "Lettuce", 0.0, 15.0, 20.0, -2.0, 26.0, 900.0, ["loam", "sandy loam"], 35.0, 5.0, 500.0, 2000.0),
    ("celery", "Celery", 5.0, 15.0, 22.0, -1.0, 28.0, 1600.0, ["loam", "clay loam", "muck"], 50.0, 10.0, 800.0, 300.0),
    ("asparagus", "Asparagus", 5.0, 18.0, 25.0, -10.0, 35.0, 2500.0, ["sandy loam", "loam"], 40.0, 12.0, 2500.0, 5000.0),
    ("artichoke", "Artichoke", 5.0, 15.0, 25.0, -3.0, 32.0, 2000.0, ["loam", "clay loam"], 45.0, 10.0, 1200.0, 2500.0),
    ("eggplant", "Eggplant", 12.0, 22.0, 30.0, 0.0, 35.0, 1800.0, ["loam", "sandy loam"], 40.0, 18.0, 600.0, 2500.0),
    ("bell_pepper", "Bell Pepper", 12.0, 20.0, 28.0, 0.0, 35.0, 1600.0, ["loam", "sandy loam"], 40.0, 18.0, 800.0, 3000.0),
    ("chili_pepper", "Chili Pepper", 12.0, 22.0, 30.0, 0.0, 38.0, 1800.0, ["loam", "sandy loam"], 40.0, 18.0, 1000.0, 2500.0),
    ("cucumber", "Cucumber", 12.0, 22.0, 28.0, 0.0, 35.0, 1400.0, ["loam", "sandy loam"], 40.0, 18.0, 500.0, 2000.0),
    ("zucchini", "Zucchini", 10.0, 20.0, 28.0, 0.0, 35.0, 1200.0, ["loam", "sandy loam"], 40.0, 15.0, 400.0, 1800.0),
    ("pumpkin", "Pumpkin", 10.0, 20.0, 30.0, 0.0, 35.0, 1800.0, ["loam", "sandy loam"], 45.0, 15.0, 200.0, 1500.0),
    ("watermelon", "Watermelon", 15.0, 25.0, 32.0, 2.0, 38.0, 2200.0, ["sandy loam", "loam"], 35.0, 18.0, 300.0, 2000.0),
    ("melon", "Melon", 15.0, 25.0, 32.0, 2.0, 38.0, 2000.0, ["sandy loam", "loam"], 35.0, 18.0, 400.0, 2200.0),
    ("sunflower", "Sunflower", 6.0, 20.0, 28.0, -2.0, 35.0, 2000.0, ["loam", "clay loam", "sandy loam"], 45.0, 10.0, 500.0, 600.0),
    ("safflower", "Safflower", 4.0, 18.0, 28.0, -5.0, 38.0, 1800.0, ["loam", "clay loam", "sandy loam"], 35.0, 8.0, 600.0, 500.0),
    ("canola", "Canola", 0.0, 15.0, 25.0, -4.0, 30.0, 1600.0, ["loam", "clay loam"], 45.0, 5.0, 550.0, 700.0),
    ("mustard", "Mustard", 0.0, 15.0, 25.0, -3.0, 30.0, 1400.0, ["loam", "sandy loam"], 40.0, 5.0, 450.0, 500.0),
    ("flax", "Flax", 5.0, 18.0, 28.0, -4.0, 32.0, 1500.0, ["loam", "clay loam"], 40.0, 8.0, 600.0, 450.0),
    ("hemp", "Hemp", 5.0, 18.0, 25.0, -2.0, 30.0, 1800.0, ["loam", "sandy loam", "clay loam"], 45.0, 10.0, 800.0, 1000.0),
    ("jute", "Jute", 15.0, 25.0, 35.0, 5.0, 40.0, 2200.0, ["loam", "clay loam", "silt loam"], 50.0, 20.0, 400.0, 800.0),
    ("sisal", "Sisal", 15.0, 25.0, 35.0, 2.0, 45.0, 4000.0, ["sandy loam", "loam", "sand"], 30.0, 20.0, 500.0, 1200.0),
    ("rubber", "Rubber", 18.0, 26.0, 32.0, 10.0, 38.0, 5000.0, ["loam", "clay loam"], 60.0, 22.0, 1500.0, 2000.0)
]

CROP_DATABASE: Dict[str, CropProfile] = {
    row[0]: _build_crop(*row) for row in _CROP_DATA
}

def get_crop_profile(crop_id: str) -> Optional[CropProfile]:
    """Retrieve the core agronomic priors for a specific crop."""
    return CROP_DATABASE.get(crop_id.lower().strip(), None)
