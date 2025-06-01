import requests
import os
from config import Config

def get_weather_data(latitude=None, longitude=None, city=None):
    """
    Get weather data for a specific location (returns Fahrenheit, mph, icon URL, and all important info)
    """
    try:
        # Use OpenWeatherMap API
        api_key = Config.WEATHER_API_KEY
        base_url = "http://api.openweathermap.org/data/2.5/weather"

        # Build query parameters
        params = {
            'appid': api_key,
            'units': 'imperial'  # Use imperial units (Fahrenheit, mph)
        }

        if latitude and longitude:
            params['lat'] = latitude
            params['lon'] = longitude
            #print(f"[DEBUG] Querying weather for lat/lon: {latitude}, {longitude}")
        elif city:
            params['q'] = city
            #print(f"[DEBUG] Querying weather for city: {city}")
        else:
            # Default to a major city if no location provided
            params['q'] = 'Dubai'
            #print("[DEBUG] Querying weather for default city: Dubai")

        #print(f"[DEBUG] Weather API URL: {base_url}")
        #print(f"[DEBUG] Weather API params: {params}")

        # Make API request
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        #print(f"[DEBUG] Raw weather API response: {data}")

        # Extract relevant weather information
        weather_data = {
            'temperature': round(data['main']['temp']),
            'feels_like': round(data['main']['feels_like']),
            'condition': data['weather'][0]['main'].lower(),
            'description': data['weather'][0]['description'],
            'icon': f"http://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png",
            'humidity': data['main']['humidity'],
            'wind_speed': round(data['wind']['speed']),  # Already in mph
        }
        #print(f"[DEBUG] Parsed weather data: {weather_data}")

        return weather_data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching weather data: {str(e)}")
        return None

def get_weather_recommendations(weather_data):
    """
    Get clothing recommendations based on weather conditions
    """
    if not weather_data:
        return None

    temp = weather_data['temperature']
    condition = weather_data['condition']
    humidity = weather_data['humidity']

    recommendations = {
        'temperature_based': [],
        'condition_based': [],
        'humidity_based': []
    }

    # Temperature-based recommendations
    if temp < 10:
        recommendations['temperature_based'].extend([
            'Heavy winter coat',
            'Thermal underwear',
            'Warm gloves',
            'Winter boots'
        ])
    elif temp < 15:
        recommendations['temperature_based'].extend([
            'Light jacket',
            'Long-sleeved shirts',
            'Jeans or warm pants',
            'Closed-toe shoes'
        ])
    elif temp < 20:
        recommendations['temperature_based'].extend([
            'Light sweater',
            'Long-sleeved shirts',
            'Comfortable pants',
            'Light jacket (optional)'
        ])
    elif temp < 25:
        recommendations['temperature_based'].extend([
            'T-shirts',
            'Light pants or shorts',
            'Comfortable shoes',
            'Light layers'
        ])
    else:
        recommendations['temperature_based'].extend([
            'Light, breathable clothing',
            'Shorts or light pants',
            'Sandals or breathable shoes',
            'Sun protection'
        ])

    # Weather condition-based recommendations
    if condition == 'rain':
        recommendations['condition_based'].extend([
            'Waterproof jacket',
            'Umbrella',
            'Waterproof shoes',
            'Quick-dry clothing'
        ])
    elif condition == 'snow':
        recommendations['condition_based'].extend([
            'Waterproof winter boots',
            'Snow jacket',
            'Warm gloves',
            'Thermal layers'
        ])
    elif condition == 'wind':
        recommendations['condition_based'].extend([
            'Windbreaker',
            'Layered clothing',
            'Secure hat',
            'Sturdy shoes'
        ])
    elif condition == 'sunny':
        recommendations['condition_based'].extend([
            'Sunglasses',
            'Sun hat',
            'Sunscreen',
            'Light, breathable clothing'
        ])

    # Humidity-based recommendations
    if humidity > 70:
        recommendations['humidity_based'].extend([
            'Moisture-wicking clothing',
            'Breathable fabrics',
            'Quick-dry materials',
            'Light layers'
        ])
    elif humidity < 30:
        recommendations['humidity_based'].extend([
            'Moisturizing lotion',
            'Lip balm',
            'Hydrating products',
            'Layered clothing'
        ])

    return recommendations

def get_weather_icon_url(icon_code):
    """
    Get the URL for a weather icon
    """
    return f"http://openweathermap.org/img/wn/{icon_code}@2x.png" 