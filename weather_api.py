import requests
import time
import urllib.parse
from threading import Lock

class WeatherAPI:
    def __init__(self):
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        self._lock = Lock()

    def get_weather(self, city_name: str) -> dict:
        """
        Fetches live weather for a given city using Open-Meteo (no API key required).
        Returns a dict with temperature, windspeed, weathercode, and city name.
        """
        city_key = city_name.strip().lower()
        
        with self._lock:
            # Check cache
            if city_key in self._cache:
                data, timestamp = self._cache[city_key]
                if time.time() - timestamp < self._cache_ttl:
                    return data

        try:
            # 1. Geocode the city
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city_key)}&count=1"
            geo_resp = requests.get(geo_url, timeout=5)
            geo_data = geo_resp.json()
            
            if not geo_data.get("results"):
                return {"error": f"City '{city_name}' not found."}
                
            location = geo_data["results"][0]
            lat = location["latitude"]
            lon = location["longitude"]
            resolved_city = f"{location.get('name')}, {location.get('country')}"

            # 2. Fetch weather
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            weather_resp = requests.get(weather_url, timeout=5)
            weather_data = weather_resp.json()
            
            if "current_weather" not in weather_data:
                return {"error": "Weather data unavailable."}
                
            current = weather_data["current_weather"]
            
            result = {
                "city": resolved_city,
                "temperature": current.get("temperature", 20.0),
                "windspeed": current.get("windspeed", 10.0),
                "weathercode": current.get("weathercode", 0)
            }
            
            # Update cache
            with self._lock:
                self._cache[city_key] = (result, time.time())
                
            return result
            
        except Exception as e:
            return {"error": f"API Error: {str(e)}"}

# Global singleton instance
weather_client = WeatherAPI()
