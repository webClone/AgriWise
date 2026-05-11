import sys
import os

# Add services/agribrain to Python path so we can import eo.sentinel
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'services', 'agribrain')))

from eo.sentinel import fetch_soil_properties, fetch_openweather_data

def check_data():
    lat = 36.578
    lng = 2.954
    
    print(f"Checking data for lat={lat}, lng={lng}...\n")
    
    print("--- OpenWeather Data ---")
    try:
        weather = fetch_openweather_data(lat, lng)
        print(weather)
    except Exception as e:
        print(f"Error fetching weather: {e}")
        
    print("\n--- SoilGrids (ISRIC) Data ---")
    try:
        soil = fetch_soil_properties(lat, lng)
        print(soil)
    except Exception as e:
        print(f"Error fetching soil: {e}")

if __name__ == "__main__":
    check_data()
