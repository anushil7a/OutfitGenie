from flask import Blueprint, jsonify, session
from flask_login import login_required, current_user
from models import db, ClothingItem, RecommendationFeedback, User, Outfit
from openai import OpenAI
import os
import json
import logging
import re

weather_recommendations = Blueprint('weather_recommendations', __name__)
logger = logging.getLogger(__name__)

def get_weather_recommendations(user_id, weather_data):
    """Get AI-generated outfit recommendations based on weather and user's wardrobe."""
    #print(f"Getting weather recommendations for user {user_id} with weather data: {weather_data}")
    try:
        # Get user's clothing items
        clothing_items = ClothingItem.query.filter_by(user_id=user_id).all()
        
        
        # Get user's feedback history
        feedback = RecommendationFeedback.query.filter_by(user_id=user_id).all()
        
        # Get user preferences
        user = User.query.get(user_id)
        
        # Prepare the data for the AI
        wardrobe_data = {
            'clothing_items': [item.to_dict() for item in clothing_items], 
            'feedback_history': [
                {
                    'question': f.question,
                    'recommendation': f.recommendation,
                    'feedback': f.feedback
                } for f in feedback
            ],
            'user_preferences': user.preferences if user.preferences else {},
            'weather': weather_data
        }
        #print(f"Wardrobe data: {wardrobe_data.get('clothing_items')}")
        
        # Call OpenAI API
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        prompt_content = (
            "Given this data about the user's wardrobe, feedback history, and current weather:\n"
            f"{json.dumps(wardrobe_data, indent=2)}\n\n"
            "Recommend 3 weather-appropriate outfits using only the clothes the user has.\n"
            "For each outfit:\n"
            "1. List the specific items to wear\n"
            "2. Explain why it's suitable for the current weather\n"
            "3. Consider the user's feedback history to avoid disliked combinations\n\n"
            "Format your response as a JSON array of outfits, each with:\n"
            "- items: list of clothing items to wear\n"
            "- explanation: why this outfit works for the weather\n"
            "- confidence: number between 0-1 indicating how confident you are in this recommendation\n\n"
            "- image_url: the url of the image of the outfit (a url for each item in the outfit)\n"
            "Respond ONLY with a valid JSON array. Do NOT include any text, code block markers, or explanations—just the raw JSON.\n\n"
            "Example format:\n"
            "[\n"
            "    {\n"
            "        \"items\": [\"Blue Jeans\", \"White T-shirt\", \"Black Shoes\"],\n"
            "        \"explanation\": \"This outfit works because...\",\n"
            "        \"confidence\": 0.9\n"
            "        \"image_url\": [{\"id\": 1, \"url\": \"linkforimage\"}, {\"id\": 2, \"url\": \"linkforimage\"}, {\"id\": 3, \"url\": \"linkforimage\"}]\n"
            "    }\n"
            "]"
            
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a fashion expert AI that recommends outfits based on weather and user's wardrobe.\nConsider the user's feedback history and preferences when making recommendations.\nFocus on practical, weather-appropriate outfits using only the clothes the user has."
                },
                {
                    "role": "user",
                    "content": prompt_content
                }
            ],
            max_tokens=900
        )
        
        # Parse the response
        raw_content = response.choices[0].message.content.strip()
        if raw_content.startswith("```"):
            raw_content = re.sub(r"^```[a-zA-Z]*\n?", "", raw_content)
            raw_content = re.sub(r"\n?```$", "", raw_content)
        try:
            recommendations = json.loads(raw_content)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing AI response: {e}")
            logger.error(f"Raw content: {raw_content}")
            return []
        #print(f"Recommendations: {recommendations}")
        
        # Attach image_url and outfit_id to each item in each recommendation

        clothing_items_dict = {item.type: item for item in clothing_items}
        #print(f"Clothing items dict: {clothing_items_dict}")
        user_outfits = {o.id: o.image_url for o in Outfit.query.filter_by(user_id=user_id).all()}
        #print(f"User outfits: {user_outfits}")

        for rec in recommendations:
            items = rec.get('items', [])
            image_urls = rec.get('image_url', [])
            new_items = []
            for idx, item_name in enumerate(items):
                image_url = None
                item_id = None
                if idx < len(image_urls):
                    image_url = image_urls[idx].get('url')
                    item_id = image_urls[idx].get('id')
                new_items.append({
                    'name': item_name,
                    'image_url': image_url,
                    'id': item_id
                })
            rec['items'] = new_items
            rec.pop('image_url', None)
        return recommendations
        
    except Exception as e:
        logger.error(f"Error getting weather recommendations: {str(e)}")
        return []

@weather_recommendations.route('/get-weather-recommendations')
@login_required
def get_recommendations():
    try:
        # Get weather data from session
        weather_data = session.get('weather_data')
        if not weather_data:
            return jsonify({
                'error': 'Please set your location first to get weather-based recommendations.',
                'status': 'location_required'
            }), 400
            
        # Get recommendations
        recommendations = get_weather_recommendations(current_user.id, weather_data)
        
        return jsonify({
            'recommendations': recommendations,
            'weather': weather_data
        })
        
    except Exception as e:
        logger.error(f"Error in weather recommendations route: {str(e)}")
        return jsonify({'error': 'Failed to get recommendations'}), 500 