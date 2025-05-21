import openai
from PIL import Image
import io
import os
from config import Config

def analyze_clothing_image(image_data):
    """
    Analyze a clothing image using OpenAI's Vision API
    """
    try:
        # Convert image data to base64
        if isinstance(image_data, bytes):
            image = Image.open(io.BytesIO(image_data))
        else:
            image = image_data

        # Prepare the image for OpenAI API
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = buffered.getvalue()

        # Call OpenAI Vision API
        response = openai.ChatCompletion.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this clothing item and provide details about: 1) Type of clothing, 2) Color, 3) Style, 4) Occasion appropriateness, 5) Season appropriateness. Format the response as JSON."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_str}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error analyzing image: {str(e)}")
        return None

def generate_outfit_recommendations(user_preferences, weather_data, occasion):
    """
    Generate outfit recommendations using OpenAI's API
    """
    try:
        prompt = f"""
        Generate outfit recommendations based on the following criteria:
        - User preferences: {user_preferences}
        - Weather conditions: {weather_data}
        - Occasion: {occasion}

        Provide recommendations in JSON format with the following structure:
        {{
            "outfits": [
                {{
                    "id": 1,
                    "items": ["item1", "item2", ...],
                    "occasion": "occasion",
                    "weather_appropriate": true/false,
                    "style": "style",
                    "confidence_score": 0.0-1.0
                }}
            ]
        }}
        """

        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a fashion expert AI assistant that provides personalized outfit recommendations."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=1000
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error generating recommendations: {str(e)}")
        return None

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
            model="gpt-4",
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
            model="gpt-4",
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