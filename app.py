from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS
import os
from dotenv import load_dotenv
import openai
import requests
from datetime import datetime, timedelta
import json
from werkzeug.utils import secure_filename
import base64
from openai import OpenAI
import logging
from auth import auth
from outfits import outfits
from models import db, User, Outfit, Chat, RecommendationFeedback
from routes.chat import chat_bp

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Configure CORS to be more permissive during development
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///outfit_finder.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'

# Register blueprints
app.register_blueprint(auth)
app.register_blueprint(outfits)
app.register_blueprint(chat_bp)

# Configure OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
print("OpenAI API Key configured:", "Yes" if os.getenv('OPENAI_API_KEY') else "No")

# Weather API configuration
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"

# Custom JSON encoder for datetime objects
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

app.json_encoder = CustomJSONEncoder

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    try:
        # Get location from session or default to None
        location = session.get('location')
        weather_data = session.get('weather_data')
        weather_timestamp = session.get('weather_timestamp')
        
        logger.info(f"[DEBUG] Session data - Location: {location}")
        logger.info(f"[DEBUG] Session data - Weather data: {weather_data}")
        logger.info(f"[DEBUG] Session data - Weather timestamp: {weather_timestamp}")

        # If we have a location but no weather data, or weather data is old, fetch new weather
        if location and (not weather_data or not weather_timestamp or 
           (datetime.utcnow() - datetime.fromisoformat(weather_timestamp)) > timedelta(minutes=30)):
            logger.info(f"[WEATHER CACHE MISS] Fetching new weather data for {location}")
            weather_data = get_weather_data(location)
            if weather_data:
                session['weather_data'] = weather_data
                session['weather_timestamp'] = datetime.utcnow().isoformat()
                session.modified = True
                logger.info(f"[DEBUG] Updated session with new weather data: {weather_data}")
        elif weather_data:
            logger.info(f"[WEATHER CACHE HIT] Using cached weather data: {weather_data}")

        logger.info(f"[DEBUG] Final weather data being sent to template: {weather_data}")
        return render_template('index.html',
                             weather=weather_data,
                             recommendations=None,  # Set recommendations to None
                             current_location=location)
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        return render_template('index.html', current_location=location)

@app.route('/recommend', methods=['POST'])
@login_required
def get_recommendations():
    data = request.json
    occasion = data.get('occasion')
    weather = data.get('weather')
    
    # Get weather data if not provided
    if not weather:
        weather = get_weather_data()
    
    # Generate outfit recommendations using OpenAI
    recommendations = generate_outfit_recommendations(
        occasion=occasion,
        weather=weather,
        user_preferences=current_user.preferences
    )
    
    return jsonify(recommendations)

@app.route('/feedback', methods=['POST'])
@login_required
def save_feedback():
    data = request.json
    outfit_id = data.get('outfit_id')
    rating = data.get('rating')
    
    outfit = Outfit.query.get(outfit_id)
    if outfit:
        outfit.rating = rating
        db.session.commit()
        return jsonify({'message': 'Feedback saved successfully'})
    
    return jsonify({'error': 'Outfit not found'}), 404

@app.route('/my-outfits')
@login_required
def my_outfits():
    try:
        # Get page number from query parameters, default to 1
        page = request.args.get('page', 1, type=int)
        per_page = 6  # Number of items per page
        
        # Get outfits for the current user with pagination
        outfits_pagination = Outfit.query.filter_by(user_id=current_user.id)\
            .order_by(Outfit.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        # Check if the uploads directory exists
        uploads_dir = os.path.join(app.root_path, 'static', 'uploads', str(current_user.id))
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
            print(f"Created uploads directory: {uploads_dir}")  # Debug print
        
        return render_template('my_outfits.html', outfits=outfits_pagination.items, pagination=outfits_pagination)
    except Exception as e:
        print(f"Error in my_outfits route: {str(e)}")  # Debug print
        flash('Error loading outfits. Please try again.')
        return redirect(url_for('index'))

@app.route('/preferences', methods=['POST'])
@login_required
def save_preferences():
    try:
        print("=== Preferences Save Request Start ===")
        data = request.json
        print("Received data:", data)
        
        if not data:
            print("Error: No data provided")
            return jsonify({'error': 'No data provided'}), 400

        # Update physical attributes directly on the user
        current_user.height = data.get('height')
        current_user.weight = data.get('weight')
        current_user.gender = data.get('gender')

        # Only style-related fields go in preferences
        styles = data.get('styles', [])
        preferences = {
            'styles': styles,
            'skin_tone_color': data.get('skin_tone_color'),
            'skin_tone_text': data.get('skin_tone_text'),
            'hair_color': data.get('hair_color'),
            'hair_color_text': data.get('other_hair_color') if data.get('hair_color') == 'other' else None,
        }
        # Only save custom_style if 'other' is in styles
        other_style = data.get('other_style')
        if 'other' in styles and other_style and other_style.strip():
            preferences['custom_style'] = other_style.strip()
        # If 'other' is not checked, do not save custom_style

        current_user.preferences = preferences
        try:
            db.session.commit()
            print("Successfully saved preferences to database")
            print("Updated user preferences:", current_user.preferences)
            return jsonify({'message': 'Preferences saved successfully'})
        except Exception as e:
            db.session.rollback()
            print("Database error:", str(e))
            return jsonify({'error': 'Failed to save preferences to database'}), 500
    except Exception as e:
        print("Unexpected error:", str(e))
        return jsonify({'error': 'An unexpected error occurred while saving preferences'}), 500
    finally:
        print("=== Preferences Save Request End ===")

@app.route('/delete-outfit/<int:outfit_id>', methods=['POST'])
@login_required
def delete_outfit(outfit_id):
    print(f"Attempting to delete outfit {outfit_id} for user {current_user.id}")
    try:
        outfit = Outfit.query.get_or_404(outfit_id)
        print(f"Found outfit: {outfit.id}, owned by user {outfit.user_id}")
        
        # Verify ownership
        if outfit.user_id != current_user.id:
            print(f"Unauthorized: outfit belongs to user {outfit.user_id}, current user is {current_user.id}")
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Delete the image file
        if outfit.image_url:
            try:
                # Convert URL to filesystem path
                image_path = os.path.join(app.root_path, outfit.image_url.lstrip('/'))
                print(f"Attempting to delete image file: {image_path}")
                if os.path.exists(image_path):
                    os.remove(image_path)
                    print(f"Successfully deleted image file: {image_path}")
                else:
                    print(f"Image file not found: {image_path}")
            except Exception as e:
                print(f"Error deleting image file: {str(e)}")
                # Continue with database deletion even if file deletion fails
        
        # Delete from database
        print("Deleting outfit from database")
        db.session.delete(outfit)
        db.session.commit()
        print("Successfully deleted outfit from database")
        
        return jsonify({'message': 'Outfit deleted successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting outfit: {str(e)}")
        return jsonify({'error': f'Failed to delete outfit: {str(e)}'}), 500

def get_weather_data(location="London"):
    """Get weather data for a specific location"""
    try:
        logger.info(f"[WEATHER API CALL] Fetching weather data for {location}")
        params = {
            'q': location,
            'appid': WEATHER_API_KEY,
            'units': 'imperial'  # Use Fahrenheit
        }
        response = requests.get(WEATHER_API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # Create a dictionary with all required fields
        weather_data = {
            'temperature': int(round(data['main']['temp'])),
            'feels_like': int(round(data['main']['feels_like'])),
            'condition': str(data['weather'][0]['main']),
            'description': str(data['weather'][0]['description']),
            'icon': f"http://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png",
            'humidity': int(data['main']['humidity']),
            'wind_speed': int(round(data['wind']['speed'] * 2.237))  # Convert m/s to mph
        }
        
        logger.info(f"[WEATHER DATA] Successfully fetched weather data: {weather_data}")
        return weather_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching weather data: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_weather_data: {str(e)}")
        return None

def get_weather_recommendations(weather_data, user_preferences=None):
    """Generate outfit recommendations based on weather and user's uploaded clothes."""
    try:
        # Get user's uploaded outfits
        user_outfits = Outfit.query.filter_by(user_id=current_user.id).all()
        outfits_info = []
        for outfit in user_outfits:
            outfits_info.append({
                'image_url': outfit.image_url,
                'analysis': outfit.analysis,
                'occasion': outfit.occasion,
                'weather': outfit.weather
            })

        # Create a prompt for the AI
        prompt = f"""Based on the current weather conditions and the user's uploaded clothes, recommend the perfect outfit.

Current Weather:
- Temperature: {weather_data['temperature']}°F
- Feels like: {weather_data['feels_like']}°F
- Condition: {weather_data['description']}
- Humidity: {weather_data['humidity']}%
- Wind Speed: {weather_data['wind_speed']} mph

User's uploaded clothes:
{json.dumps(outfits_info, indent=2)}

User's preferences:
{json.dumps(user_preferences, indent=2) if user_preferences else 'No preferences set'}

Please recommend an outfit using ONLY the clothes the user has uploaded. Format your response as JSON with these fields:
1. "outfit": A brief description of the recommended outfit
2. "reasoning": Why this outfit is suitable for the current weather
3. "items": List of specific items from the user's uploaded clothes that make up this outfit

Response:"""

        # Return placeholder recommendation for now
        return {
            "outfit": "A comfortable layered outfit suitable for the current weather.",
            "reasoning": "This outfit is chosen based on the current temperature and conditions.",
            "items": ["Item 1", "Item 2", "Item 3"]
        }

        # Comment out GPT call for now
        # try:
        #     response = client.chat.completions.create(
        #         model="gpt-4o-mini",
        #         messages=[
        #             {"role": "system", "content": "You are a fashion assistant that recommends outfits based on weather conditions and available clothes."},
        #             {"role": "user", "content": prompt}
        #         ],
        #         max_tokens=300
        #     )
        #     return json.loads(response.choices[0].message.content)
        # except Exception as e:
        #     logger.error(f"Error with GPT call: {str(e)}")
        #     return None

    except Exception as e:
        logger.error(f"Error generating weather recommendations: {str(e)}")
        return None

@app.route('/update-location', methods=['POST'])
def update_location():
    try:
        logger.info("[UPDATE LOCATION] Starting location update")
        data = request.json
        location = data.get('location')
        logger.info(f"[UPDATE LOCATION] Received location: {location}")
        
        if not location:
            logger.error("[UPDATE LOCATION] No location provided in request")
            return jsonify({'error': 'Location is required'}), 400
        
        logger.info(f"[UPDATE LOCATION] Fetching weather data for {location}")
        
        # Fetch weather data first
        weather_data = get_weather_data(location)
        if not weather_data:
            logger.error(f"[UPDATE LOCATION] Failed to get weather data for {location}")
            return jsonify({'error': 'Failed to get weather data for this location'}), 400
            
        logger.info(f"[UPDATE LOCATION] Successfully got weather data: {weather_data}")
            
        # Update session data
        session['location'] = location
        session['weather_data'] = weather_data
        session['weather_timestamp'] = datetime.utcnow().isoformat()
        
        # Force session to be saved
        session.modified = True
        
        logger.info(f"[UPDATE LOCATION] Successfully updated session with location: {location}")
        logger.info(f"[UPDATE LOCATION] Weather data cached: {weather_data}")
        
        return jsonify({
            'success': True, 
            'message': 'Location updated successfully',
            'weather': weather_data
        })
    except Exception as e:
        logger.error(f"[UPDATE LOCATION] Error updating location: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/ai-data')
@login_required
def ai_data():
    # Get page numbers from query parameters, default to 1
    outfits_page = request.args.get('outfits_page', 1, type=int)
    feedback_page = request.args.get('feedback_page', 1, type=int)
    per_page = 8  # Number of items per page
    
    # Get user's outfits with pagination
    outfits_pagination = Outfit.query.filter_by(user_id=current_user.id)\
        .order_by(Outfit.created_at.desc())\
        .paginate(page=outfits_page, per_page=per_page, error_out=False)
    
    # Get recommendation feedback with pagination
    feedback_pagination = RecommendationFeedback.query.filter_by(user_id=current_user.id)\
        .order_by(RecommendationFeedback.created_at.desc())\
        .paginate(page=feedback_page, per_page=per_page, error_out=False)
    
    # Get location and weather from session
    location = session.get('location')
    weather = session.get('weather_data')
    
    return render_template('ai_data.html',
                         outfits=outfits_pagination.items,
                         outfits_pagination=outfits_pagination,
                         feedback=feedback_pagination.items,
                         feedback_pagination=feedback_pagination,
                         location=location,
                         weather=weather,
                         preferences=current_user.preferences)

@app.route('/update-ai-notes', methods=['POST'])
@login_required
def update_ai_notes():
    try:
        data = request.json
        notes = data.get('notes', '').strip()
        
        current_user.ai_notes = notes
        db.session.commit()
        
        return jsonify({'message': 'Notes updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/update-outfit-description/<int:outfit_id>', methods=['POST'])
@login_required
def update_outfit_description(outfit_id):
    outfit = Outfit.query.get_or_404(outfit_id)
    if outfit.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    if not data or 'description' not in data:
        return jsonify({'error': 'No description provided'}), 400
    
    outfit.analysis = data['description']
    db.session.commit()
    
    return jsonify({'success': True}), 200

@app.route('/recommendation-feedback', methods=['POST'])
@login_required
def save_recommendation_feedback():
    try:
        data = request.json
        logger.info(f"Received feedback data: {data}")
        
        recommendation = data.get('recommendation')
        question = data.get('question')
        feedback = data.get('feedback')  # 'like' or 'dislike'
        context = data.get('context', {})  # Optional context data
        
        if not recommendation:
            logger.error("No recommendation provided")
            return jsonify({'error': 'No recommendation provided'}), 400
            
        if not question:
            logger.error("No question provided")
            return jsonify({'error': 'No question provided'}), 400
            
        if not feedback or feedback not in ['like', 'dislike']:
            logger.error(f"Invalid feedback value: {feedback}")
            return jsonify({'error': 'Invalid feedback value'}), 400
        
        try:
            # Check if feedback already exists for this recommendation
            existing_feedback = RecommendationFeedback.query.filter_by(
                user_id=current_user.id,
                recommendation=recommendation
            ).first()
            
            if existing_feedback:
                # Update existing feedback
                existing_feedback.feedback = feedback
                existing_feedback.context = context
                existing_feedback.created_at = datetime.utcnow()
                logger.info(f"Updated existing feedback for user {current_user.id}")
            else:
                # Create new feedback
                feedback_entry = RecommendationFeedback(
                    user_id=current_user.id,
                    recommendation=recommendation,
                    question=question,
                    feedback=feedback,
                    context=context
                )
                db.session.add(feedback_entry)
                logger.info(f"Created new feedback for user {current_user.id}")
            
            db.session.commit()
            return jsonify({'message': 'Feedback saved successfully'})
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error: {str(db_error)}")
            return jsonify({'error': f'Database error: {str(db_error)}'}), 500
            
    except Exception as e:
        logger.error(f"Error in save_recommendation_feedback: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/recommendation-feedback/<int:feedback_id>', methods=['DELETE'])
@login_required
def delete_recommendation_feedback(feedback_id):
    try:
        feedback = RecommendationFeedback.query.get_or_404(feedback_id)
        if feedback.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
            
        db.session.delete(feedback)
        db.session.commit()
        return jsonify({'message': 'Feedback deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.after_request
def after_request(response):
    print(f"Response headers: {response.headers}")  # Debug print
    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create uploads directory if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True) 