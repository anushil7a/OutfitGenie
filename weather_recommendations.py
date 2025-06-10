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
            'user_notes': user.ai_notes if user.ai_notes else "",
            'weather': weather_data
        }
        #print(f"Wardrobe data: {wardrobe_data.get('clothing_items')}")
        print(f"User preferences: {user.preferences}")
        #print(f"User notes: {user.ai_notes}")
        
        # Call OpenAI API
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        prompt_content = (
            "Here’s the user’s wardrobe, preferences, past outfit feedback, and the current weather (in Fahrenheit):\n"
            "wardrobe_data includes clothes they own, with stuff like name, type (top, pants, etc.) and image_url.\n"
            "user.preferences shows what they actually like—like only wearing formal outfits, avoiding certain colors, or liking loose fits.\n"
            "user_notes might include stuff like how they run hot/cold, if they’ve worn something recently, or things they just don’t vibe with.\n"
            f"{json.dumps(wardrobe_data, indent=2)}\n\n"
            "Give back 3 outfit ideas that match the weather *and* the user’s style. Use only what they already have.\n"
            "Make sure you:\n"
            "1. Only recommend outfits that match the user’s vibe. If they prefer formal, keep it clean—even if it’s hot. Pick lighter formal stuff, like short-sleeve shirts or slacks.\n"
            "2. Each outfit should:\n"
            "   - Have 3 to 6 pieces max, but make each piece's are different from the others and makes sense\n"
            "   - Match the weather (don’t throw in a hoodie if it’s 90°F out)\n"
            "   - Be different from the others—switch up tops, bottoms, shoes, or accessories so each look feels fresh\n"
            "   - Actually make sense (don’t suggest two pairs of pants or weird layers unless there’s a good reason)\n"
            "3. Keep the explanation chill. Write like you’re helping a friend pick an outfit, not giving a robot report. Talk about why it works for the weather, what they like, and what they’ve worn before.\n"
            "4. Confidence (0–1) means how good the match is based on all that info.\n"
            "5. If there’s no image for something, just drop null or a placeholder.\n\n"
            "Return only a valid JSON array. Each outfit should include:\n"
            "- items: list of clothing item names\n"
            "- explanation: a short, chill reason this outfit works for today (mention the weather and temperature, the user's preferences, and the user's wardrobe)\n"
            "- confidence: a number between 0 and 1\n"
            "- image_url: list of objects like {\"id\": item_id, \"url\": \"image_link\"} (or null)\n\n"
            "Nothing else—just the JSON array.\n\n"
            "Example format:\n"
            "[\n"
            "  {\n"
            "    \"items\": [\"Tan Chinos\", \"Light Blue Button-Up\", \"White Sneakers\"],\n"
            "    \"explanation\": \"This one's a go-to look for warm weather. The button-up keeps it sharp but breathable, and the sneakers keep it comfy without looking too casual.\",\n"
            "    \"confidence\": 0.93,\n"
            "    \"image_url\": [\n"
            "      {\"id\": 1, \"url\": \"link_to_image1\"},\n"
            "      {\"id\": 2, \"url\": \"link_to_image2\"},\n"
            "      {\"id\": 3, \"url\": \"link_to_image3\"}\n"
            "    ]\n"
            "  }\n"
            "]"
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a fashion expert AI that recommends outfits based on weather (in Fahrenheit) and user's wardrobe.\nConsider the user's feedback history and preferences when making recommendations.\nFocus on practical, weather-appropriate outfits using only the clothes the user has. Make sure to use the weather information to make the recommendations."
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
                    img = image_urls[idx]
                    if isinstance(img, dict):
                        image_url = img.get('url')
                        item_id = img.get('id')
                    elif isinstance(img, str):
                        image_url = img
                        item_id = None
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