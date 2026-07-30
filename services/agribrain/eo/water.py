"""
EO Water Balance Module
Handles evapotranspiration, water balance, rainfall climatology, drought analysis.
Extracted from sentinel.py for separation of concerns.
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, Optional

from eo.auth import EO_REQUEST_TIMEOUT

# ============================================================================
# Configuration
# ============================================================================

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_CURRENT_URL = "https://api.open-meteo.com/v1/forecast"


# ============================================================================
# Water Balance (FAO-56)
# ============================================================================

def fetch_water_balance(lat: float, lng: float, days_past: int = 30, days_future: int = 7) -> Optional[Dict]:
    """
    Fetches daily Reference Evapotranspiration (ET0) and Precipitation
    for the past X days and future Y days to calculate Water Balance.
    
    Data Source: Open-Meteo (Archive for past, Forecast for future).
    """
    try:
        today = datetime.now().date()
        start_date = today - timedelta(days=days_past)
        end_date = today - timedelta(days=1) # Yesterday
        
        # 1. Fetch Historical Data (Archive)
        history_params = {
            "latitude": lat,
            "longitude": lng,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "daily": ["et0_fao_evapotranspiration", "precipitation_sum"],
            "timezone": "auto"
        }
        
        hist_res = requests.get(OPEN_METEO_ARCHIVE_URL, params=history_params, timeout=8)
        hist_data = hist_res.json() if hist_res.status_code == 200 else {}
        
        # 2. Fetch Forecast Data (Current)
        forecast_params = {
            "latitude": lat,
            "longitude": lng,
            "daily": ["et0_fao_evapotranspiration", "precipitation_sum"],
            "forecast_days": days_future + 1, # Include today
            "timezone": "auto"
        }
        
        fore_res = requests.get(OPEN_METEO_CURRENT_URL, params=forecast_params, timeout=EO_REQUEST_TIMEOUT)
        fore_data = fore_res.json() if fore_res.status_code == 200 else {}
        
        # 3. Merge Datasets
        combined_records = []
        cumulative_deficit = 0
        
        # Process History
        if "daily" in hist_data and "time" in hist_data["daily"]:
            daily = hist_data["daily"]
            for i, date_str in enumerate(daily["time"]):
                et0 = daily["et0_fao_evapotranspiration"][i] or 0
                precip = daily["precipitation_sum"][i] or 0
                balance = precip - et0
                cumulative_deficit += balance
                
                combined_records.append({
                    "date": date_str,
                    "type": "historical",
                    "et0": round(et0, 2),
                    "precip": round(precip, 2),
                    "balance": round(balance, 2),
                    "cumulative_deficit": round(cumulative_deficit, 2)
                })
        
        # Process Forecast (starting from today)
        if "daily" in fore_data and "time" in fore_data["daily"]:
            daily = fore_data["daily"]
            for i, date_str in enumerate(daily["time"]):
                # Skip if date matches last history date (overlap check)
                if combined_records and combined_records[-1]["date"] == date_str:
                    continue
                    
                et0 = daily["et0_fao_evapotranspiration"][i] or 0
                precip = daily["precipitation_sum"][i] or 0
                balance = precip - et0
                cumulative_deficit += balance
                
                combined_records.append({
                    "date": date_str,
                    "type": "forecast",
                    "et0": round(et0, 2),
                    "precip": round(precip, 2),
                    "balance": round(balance, 2),
                    "cumulative_deficit": round(cumulative_deficit, 2)
                })
                
        return {
            "location": {"lat": lat, "lng": lng},
            "records": combined_records,
            "summary": {
                "total_precip_mm": round(sum(r["precip"] for r in combined_records), 2),
                "total_et0_mm": round(sum(r["et0"] for r in combined_records), 2),
                "final_deficit_mm": round(cumulative_deficit, 2),
                "stress_index": max(0, min(100, abs(min(0, cumulative_deficit)) * 0.5))
            },
            "source": "open-meteo-fao56"
        }

    except Exception as e:
        print(f"fetch_water_balance error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# Rainfall Climatology & Drought Analysis
# ============================================================================

def fetch_rainfall_climatology(lat: float, lng: float) -> Optional[Dict]:
    """
    Fetches 30-year monthly rainfall normals (1991-2020).
    """
    try:
        params = {
            "latitude": lat,
            "longitude": lng,
            "start_date": "1991-01-01",
            "end_date": "2020-12-31",
            "daily": ["precipitation_sum"],
            "timezone": "auto"
        }
        
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=60)
        
        if response.status_code != 200:
            print(f"Climatology API Error: {response.text}")
            return None
        
        data = response.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        precip = daily.get("precipitation_sum", [])
        
        if not dates:
            return None
        
        monthly_totals = {m: [] for m in range(1, 13)}
        annual_totals = {}
        
        for i, date in enumerate(dates):
            if precip[i] is not None:
                month = int(date[5:7])
                year = int(date[:4])
                monthly_totals[month].append(precip[i])
                
                if year not in annual_totals:
                    annual_totals[year] = 0
                annual_totals[year] += precip[i]
        
        monthly_means = {}
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        
        for month in range(1, 13):
            values = monthly_totals[month]
            if values:
                total_mass = sum(values)
                monthly_means[month_names[month-1]] = round(total_mass / 30, 1)
            else:
                monthly_means[month_names[month-1]] = 0
        
        annual_values = list(annual_totals.values())
        annual_mean = sum(annual_values) / len(annual_values) if annual_values else 0
        
        return {
            "location": {"lat": lat, "lng": lng},
            "reference_period": "1991-2020",
            "monthly_normals_mm": monthly_means,
            "annual_normal_mm": round(annual_mean, 1),
            "total_years": len(annual_values),
            "source": "era5-open-meteo-climatology"
        }
        
    except Exception as e:
        print(f"Rainfall climatology error: {e}")
        return None


def fetch_rainfall_history(lat: float, lng: float, years: int = 30) -> Optional[Dict]:
    """
    Fetches annual rainfall totals for the past N years.
    """
    try:
        end_year = datetime.now().year - 1
        start_year = end_year - years + 1
        
        params = {
            "latitude": lat,
            "longitude": lng,
            "start_date": f"{start_year}-01-01",
            "end_date": f"{end_year}-12-31",
            "daily": ["precipitation_sum"],
            "timezone": "auto"
        }
        
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=60)
        
        if response.status_code != 200:
            print(f"Rainfall history API Error: {response.text}")
            return None
        
        data = response.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        precip = daily.get("precipitation_sum", [])
        
        if not dates:
            return None
        
        annual_totals = {}
        for i, date in enumerate(dates):
            if precip[i] is not None:
                year = int(date[:4])
                if year not in annual_totals:
                    annual_totals[year] = 0
                annual_totals[year] += precip[i]
        
        years_list = sorted(annual_totals.keys())
        values = [annual_totals[y] for y in years_list]
        mean_rainfall = sum(values) / len(values) if values else 0
        
        annual_records = []
        for year in years_list:
            total = annual_totals[year]
            pct_of_mean = (total / mean_rainfall * 100) if mean_rainfall > 0 else 100
            
            if pct_of_mean < 75:
                classification = "drought"
            elif pct_of_mean < 90:
                classification = "dry"
            elif pct_of_mean <= 110:
                classification = "normal"
            elif pct_of_mean <= 125:
                classification = "wet"
            else:
                classification = "very_wet"
            
            annual_records.append({
                "year": year,
                "total_mm": round(total, 1),
                "pct_of_mean": round(pct_of_mean, 1),
                "classification": classification
            })
        
        if len(values) >= 5:
            n = len(values)
            x_mean = sum(range(n)) / n
            y_mean = mean_rainfall
            
            numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            
            slope = numerator / denominator if denominator != 0 else 0
            trend = "increasing" if slope > 1 else "decreasing" if slope < -1 else "stable"
            trend_mm_per_year = round(slope, 2)
        else:
            trend = "insufficient_data"
            trend_mm_per_year = 0
        
        return {
            "location": {"lat": lat, "lng": lng},
            "period": {"start": start_year, "end": end_year},
            "mean_annual_mm": round(mean_rainfall, 1),
            "min_year": {"year": years_list[values.index(min(values))], "mm": round(min(values), 1)},
            "max_year": {"year": years_list[values.index(max(values))], "mm": round(max(values), 1)},
            "trend": trend,
            "trend_mm_per_year": trend_mm_per_year,
            "annual_records": annual_records,
            "source": "era5-open-meteo-history"
        }
        
    except Exception as e:
        print(f"Rainfall history error: {e}")
        return None


def calculate_drought_frequency(lat: float, lng: float, years: int = 30) -> Optional[Dict]:
    """
    Calculates drought frequency and risk based on historical rainfall.
    """
    try:
        history = fetch_rainfall_history(lat, lng, years)
        if not history:
            return None
        
        records = history.get("annual_records", [])
        mean = history.get("mean_annual_mm", 0)
        
        drought_years = [r for r in records if r["classification"] == "drought"]
        dry_years = [r for r in records if r["classification"] == "dry"]
        
        drought_count = len(drought_years)
        dry_count = len(dry_years)
        total_years = len(records)
        
        drought_frequency = drought_count / total_years if total_years > 0 else 0
        
        if drought_frequency >= 0.3:
            risk_level = "high"
            risk_score = min(100, int(drought_frequency * 200))
        elif drought_frequency >= 0.15:
            risk_level = "moderate"
            risk_score = int(drought_frequency * 150)
        else:
            risk_level = "low"
            risk_score = int(drought_frequency * 100)
        
        recent_records = [r for r in records if r["year"] >= datetime.now().year - 10]
        recent_droughts = len([r for r in recent_records if r["classification"] == "drought"])
        recent_dry = len([r for r in recent_records if r["classification"] == "dry"])
        
        return {
            "location": {"lat": lat, "lng": lng},
            "analysis_period": {"start": records[0]["year"] if records else None, 
                               "end": records[-1]["year"] if records else None},
            "total_years_analyzed": total_years,
            "drought_years_count": drought_count,
            "dry_years_count": dry_count,
            "drought_frequency": round(drought_frequency * 100, 1),
            "drought_return_period": round(1/drought_frequency, 1) if drought_frequency > 0 else None,
            "risk_level": risk_level,
            "risk_score": risk_score,
            "recent_10_years": {
                "drought_count": recent_droughts,
                "dry_count": recent_dry
            },
            "drought_years_list": [d["year"] for d in drought_years],
            "source": "era5-drought-analysis"
        }
        
    except Exception as e:
        print(f"Drought frequency error: {e}")
        return None


def get_current_rainfall_anomaly(lat: float, lng: float) -> Optional[Dict]:
    """
    Compares current year's rainfall to 30-year baseline.
    """
    try:
        climatology = fetch_rainfall_climatology(lat, lng)
        if not climatology:
            return None
        
        monthly_normals = climatology.get("monthly_normals_mm", {})
        annual_normal = climatology.get("annual_normal_mm", 0)
        
        current_year = datetime.now().year
        current_month = datetime.now().month
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        params = {
            "latitude": lat,
            "longitude": lng,
            "start_date": f"{current_year}-01-01",
            "end_date": yesterday,
            "daily": ["precipitation_sum"],
            "timezone": "auto"
        }
        
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=EO_REQUEST_TIMEOUT)
        
        if response.status_code != 200:
            print(f"Current rainfall API Error: {response.text}")
            return None
        
        data = response.json()
        daily = data.get("daily", {})
        dates = daily.get("time", [])
        precip = daily.get("precipitation_sum", [])
        
        if not dates:
            return None
        
        ytd_rainfall = sum(p for p in precip if p is not None)
        
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        expected_ytd = sum(monthly_normals.get(month_names[m], 0) for m in range(current_month))
        
        if expected_ytd > 0:
            anomaly_pct = ((ytd_rainfall - expected_ytd) / expected_ytd) * 100
        else:
            anomaly_pct = 0
        
        if anomaly_pct <= -30:
            status = "severe_deficit"
            status_ar = "نقص حاد"
        elif anomaly_pct <= -15:
            status = "moderate_deficit"
            status_ar = "نقص معتدل"
        elif anomaly_pct <= 15:
            status = "normal"
            status_ar = "طبيعي"
        elif anomaly_pct <= 30:
            status = "above_normal"
            status_ar = "فوق الطبيعي"
        else:
            status = "excess"
            status_ar = "فائض"
        
        return {
            "location": {"lat": lat, "lng": lng},
            "year": current_year,
            "days_elapsed": len(dates),
            "ytd_rainfall_mm": round(ytd_rainfall, 1),
            "expected_ytd_mm": round(expected_ytd, 1),
            "anomaly_mm": round(ytd_rainfall - expected_ytd, 1),
            "anomaly_pct": round(anomaly_pct, 1),
            "status": status,
            "status_ar": status_ar,
            "annual_normal_mm": annual_normal,
            "projected_annual_mm": round(ytd_rainfall * (12 / current_month), 1) if current_month > 0 else 0,
            "source": "era5-rainfall-anomaly"
        }
        
    except Exception as e:
        print(f"Rainfall anomaly error: {e}")
        return None
