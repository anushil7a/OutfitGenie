import openai
from PIL import Image
import io
import os
from config import Config

def get_weather_recommendations(weather_data):
    """
    Get weather-appropriate clothing recommendations
    """
    try:
        prompt = f"""
        Based on the following weather conditions:
        Temperature: {weather_data.get('temperature')}°C
        Condition: {weather_data.get('condition')}
        Humidity: {weather_data.get('humidity')}%

        Provide clothing recommendations that would be appropriate for these conditions.
        Format the response as JSON with the following structure:
        {{
            "recommendations": [
                {{
                    "type": "clothing_type",
                    "reason": "explanation",
                    "priority": "high/medium/low"
                }}
            ]
        }}
        """

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a weather-aware fashion expert that provides appropriate clothing recommendations based on weather conditions."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=500
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error getting weather recommendations: {str(e)}")
        return None

def process_user_feedback(outfit_id, rating, user_preferences):
    """
    Process user feedback to improve future recommendations
    """
    try:
        prompt = f"""
        Based on the user's feedback:
        - Outfit ID: {outfit_id}
        - Rating: {rating}
        - Current preferences: {user_preferences}

        Update the user's style preferences to better match their taste.
        Format the response as JSON with the following structure:
        {{
            "updated_preferences": {{
                "style_preferences": ["preference1", "preference2", ...],
                "color_preferences": ["color1", "color2", ...],
                "avoided_items": ["item1", "item2", ...]
            }}
        }}
        """

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a fashion expert AI that learns from user feedback to improve outfit recommendations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=500
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error processing feedback: {str(e)}")
        return None 