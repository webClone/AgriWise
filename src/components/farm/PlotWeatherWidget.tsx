"use client";

import { useEffect, useState } from "react";

interface WeatherData {
  temperature: number;
  feels_like: number;
  temp_min: number;
  temp_max: number;
  humidity: number;
  pressure: number;
  weather: string;
  description: string;
  icon: string;
  wind_speed: number;
  wind_direction: number;
  wind_gust?: number;
  clouds: number;
  visibility: number;
  uv_index?: number;
}

interface ForecastDay {
  date: string;
  temp_min: number;
  temp_max: number;
  weather: string;
  description: string;
  icon: string;
  humidity: number;
  wind_speed: number;
  pop: number;
}

interface PlotWeatherWidgetProps {
  lat: number;
  lng: number;
}

const WEATHER_ICONS: Record<string, string> = {
  'Clear': '☀️',
  'Clouds': '☁️',
  'Rain': '🌧️',
  'Drizzle': '🌦️',
  'Thunderstorm': '⛈️',
  'Snow': '❄️',
  'Mist': '🌫️',
  'Fog': '🌫️',
  'Haze': '🌫️',
  'Dust': '💨',
  'Sand': '💨',
};

export default function PlotWeatherWidget({ lat, lng }: PlotWeatherWidgetProps) {
  const [weather, setWeather] = useState<WeatherData | null>(null);
  const [forecast, setForecast] = useState<ForecastDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        setLoading(true);
        
        // Fetch current weather
        // Fetch current weather via Proxy
        const weatherRes = await fetch(`/api/proxy?path=/eo/weather&lat=${lat}&lng=${lng}`);
        const weatherData = await weatherRes.json();
        
        console.log("Weather API response:", weatherData);
        
        // Map nested backend response to flat frontend structure
        if (!weatherData.error && weatherData.temperature) {
          const mapped: WeatherData = {
            temperature: weatherData.temperature?.current || 0,
            feels_like: weatherData.temperature?.feels_like || 0,
            temp_min: weatherData.temperature?.min || 0,
            temp_max: weatherData.temperature?.max || 0,
            humidity: weatherData.humidity || 0,
            pressure: weatherData.pressure || 0,
            weather: weatherData.weather?.condition || "Clear",
            description: weatherData.weather?.description || "",
            icon: weatherData.weather?.icon || "01d",
            wind_speed: weatherData.wind?.speed_ms || 0,
            wind_direction: weatherData.wind?.direction_deg || 0,
            wind_gust: weatherData.wind?.gust_ms,
            clouds: weatherData.clouds_percent || 0,
            visibility: weatherData.visibility_m || 10000,
            uv_index: weatherData.uv_index
          };
          setWeather(mapped);
        }

        // Fetch forecast via Proxy
        const forecastRes = await fetch(`/api/proxy?path=/eo/forecast&lat=${lat}&lng=${lng}`);
        const forecastData = await forecastRes.json();
        
        if (forecastData.forecast && !forecastData.error) {
          setForecast(forecastData.forecast.slice(0, 7));
        }

        setError(null);
      } catch (err) {
        console.error("Weather fetch error:", err);
        setError("Could not load weather data");
      } finally {
        setLoading(false);
      }
    }

    if (lat && lng) {
      fetchData();
    }
  }, [lat, lng]);

  if (loading) {
    return (
      <div className="card" style={{ background: "linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%)", border: "1px solid #334155", padding: "1.5rem" }}>
        <div className="animate-pulse flex items-center gap-4">
          <div className="w-16 h-16 bg-slate-700/50 rounded-full"></div>
          <div className="flex-1">
            <div className="h-6 bg-slate-700/50 rounded w-1/2 mb-2"></div>
            <div className="h-4 bg-slate-700/50 rounded w-3/4"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !weather) {
    return (
      <div className="card" style={{ background: "#1e293b", border: "1px solid #334155", padding: "1.5rem", textAlign: "center", color: "#94a3b8" }}>
        <span style={{ fontSize: "2rem" }}>🌤️</span>
        <p style={{ marginTop: "0.5rem" }}>Weather data unavailable</p>
        <p style={{ fontSize: "0.75rem", opacity: 0.7 }}>Check API key configuration</p>
      </div>
    );
  }

  const weatherIcon = WEATHER_ICONS[weather.weather] || '🌤️';

  return (
    <div className="card fade-in" style={{ 
      background: "linear-gradient(135deg, #1e3a5f 0%, #0f172a 100%)", 
      border: "1px solid #334155", 
      padding: "1.5rem",
      color: "white"
    }}>
      <h3 style={{ margin: "0 0 1rem 0", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <span>🌤️</span> الطقس الحالي
      </h3>

      {/* Current Weather */}
      <div style={{ display: "flex", alignItems: "center", gap: "1.5rem", marginBottom: "1.5rem" }}>
        <div style={{ fontSize: "4rem", lineHeight: 1 }}>{weatherIcon}</div>
        <div>
          <div style={{ fontSize: "3rem", fontWeight: 700, lineHeight: 1 }}>
            {Math.round(weather.temperature)}°C
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.875rem" }}>
            {weather.description}
          </div>
          <div style={{ color: "#64748b", fontSize: "0.75rem", marginTop: "0.25rem" }}>
            الشعور: {Math.round(weather.feels_like)}°C
          </div>
        </div>
        <div style={{ marginRight: "auto", textAlign: "left" }}>
          <div style={{ display: "grid", gridTemplateColumns: "auto auto", gap: "0.5rem 1rem", fontSize: "0.75rem", color: "#94a3b8" }}>
            <span>💧 الرطوبة:</span><span style={{ color: "#60a5fa" }}>{weather.humidity}%</span>
            <span>💨 الرياح:</span><span style={{ color: "#60a5fa" }}>{weather.wind_speed} م/ث</span>
            <span>🌡️ الضغط:</span><span style={{ color: "#60a5fa" }}>{weather.pressure} hPa</span>
            {weather.uv_index !== undefined && (
              <>
                <span>☀️ UV:</span><span style={{ color: weather.uv_index > 6 ? "#f59e0b" : "#60a5fa" }}>{weather.uv_index}</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* 5-Day Forecast */}
        <>
          <div style={{ borderTop: "1px solid #334155", paddingTop: "1rem", marginTop: "1rem" }}>
            <div style={{ fontSize: "0.75rem", fontWeight: 600, color: "#94a3b8", marginBottom: "0.75rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              توقعات 7 أيام
            </div>
            <div style={{ 
                display: "grid", 
                gridTemplateColumns: "repeat(auto-fit, minmax(50px, 1fr))", 
                gap: "0.5rem" 
            }}>
              {forecast.map((day, i) => (
                <div key={i} style={{ 
                  textAlign: "center", 
                  padding: "0.75rem 0.25rem", 
                  background: "rgba(255,255,255,0.05)", 
                  borderRadius: "0.5rem",
                  border: "1px solid rgba(255,255,255,0.1)"
                }}>
                  <div style={{ fontSize: "0.65rem", color: "#64748b", marginBottom: "0.25rem" }}>
                    {new Date(day.date).toLocaleDateString('ar-DZ', { weekday: 'short' })}
                  </div>
                  <div style={{ fontSize: "1.25rem", marginBottom: "0.25rem" }}>
                    {WEATHER_ICONS[day.weather] || '🌤️'}
                  </div>
                  <div style={{ fontSize: "0.75rem", fontWeight: 600 }}>
                    {Math.round(day.temp_max)}°
                  </div>
                  <div style={{ fontSize: "0.65rem", color: "#64748b" }}>
                    {Math.round(day.temp_min)}°
                  </div>
                  {day.pop > 0 && (
                    <div style={{ fontSize: "0.6rem", color: "#60a5fa", marginTop: "0.25rem" }}>
                      💧{Math.round(day.pop * 100)}%
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </>
    </div>
  );
}
