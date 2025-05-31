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
from routes.ai_data import ai_data_bp
from utils.weather_utils import get_weather_data
from weather_recommendations import weather_recommendations

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
app.register_blueprint(ai_data_bp)
app.register_blueprint(weather_recommendations)

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
            weather_data = get_weather_data(city=location)
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
def get_recommendations():#isnt being usedd right now
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
def save_feedback(): #is it being used? no, not right now
    data = request.json
    outfit_id = data.get('outfit_id')
    rating = data.get('rating')
    
    outfit = Outfit.query.get(outfit_id)
    if outfit:
        outfit.rating = rating
        db.session.commit()
        return jsonify({'message': 'Feedback saved successfully'})
    
    return jsonify({'error': 'Outfit not found'}), 404

@app.route('/preferences', methods=['POST'])
@login_required
def save_preferences(): #is it being used? no, not right now
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
        weather_data = get_weather_data(city=location)
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

@app.after_request
def after_request(response):
    print(f"Response headers: {response.headers}")  # Debug print
    return response

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create uploads directory if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True, reloader_type='stat') 