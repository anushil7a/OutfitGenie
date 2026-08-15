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
from models import db, User, Outfit, Chat, RecommendationFeedback, ClothingItem
from routes.chat import chat_bp
from routes.ai_data import ai_data_bp
from routes.insights import insights_bp
from utils.color_utils import build_spectrum, hex_for
from utils.wardrobe_insights import dedupe_pieces
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
app.register_blueprint(insights_bp)
app.register_blueprint(weather_recommendations)

# The model client lives in utils/llm.py and is built lazily on first use.
from utils.llm import base_url as _llm_base_url, chat_model as _llm_model
logger.info("Model: %s via %s | API key: %s",
            _llm_model(), _llm_base_url() or "api.openai.com",
            "set" if os.getenv('OPENAI_API_KEY') else "MISSING")

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

# Templates resolve a garment's swatch through this, so a missing or malformed
# colour always renders as a neutral rather than breaking the page.
app.jinja_env.globals['item_hex'] = hex_for

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.context_processor
def inject_spectrum():
    """Make the wardrobe spectrum available to every template.

    The band sits under the nav on every page, so it is injected here rather
    than threaded through each route. One grouped query, not one row per
    garment. Wrapped in no_autoflush because views that decorate ORM objects
    for display (my_outfits does) would otherwise have those edits flushed by
    this query during rendering.
    """
    empty = {'spectrum': [], 'wardrobe_count': 0}
    if not current_user.is_authenticated:
        return empty
    try:
        with db.session.no_autoflush:
            items = [i.to_dict() for i in
                     ClothingItem.query.filter_by(user_id=current_user.id).all()]
        # Deduped: the same shirt photographed in four outfits is four rows,
        # and counting it four times overstates that colour in the band.
        unique = dedupe_pieces(items)
        rows = [(i.get('color'), i.get('color_hex'), 1) for i in unique]
        return {
            'spectrum': build_spectrum(rows),
            'wardrobe_count': len(unique),
        }
    except Exception as e:
        # A missing color_hex column (migration not yet run) must not take
        # down every page. Render the neutral empty state instead.
        logger.warning(f"Spectrum unavailable: {e}")
        db.session.rollback()
        return empty

# Routes
@app.route('/')
def index():
    try:
        # Get location from session or default to None
        location = session.get('location')
        weather_data = session.get('weather_data')
        weather_timestamp = session.get('weather_timestamp')
        
        #logger.info(f"[DEBUG] Session data - Location: {location}")
        #logger.info(f"[DEBUG] Session data - Weather data: {weather_data}")
        #logger.info(f"[DEBUG] Session data - Weather timestamp: {weather_timestamp}")

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

        #logger.info(f"[DEBUG] Final weather data being sent to template: {weather_data}")
        return render_template('index.html',
                             weather=weather_data,
                             recommendations=None,  # Set recommendations to None
                             current_location=location)
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        return render_template('index.html', current_location=location)

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

@app.route('/update-location', methods=['POST'])
def update_location():
    try:
        #logger.info("[UPDATE LOCATION] Starting location update")
        data = request.json
        location = data.get('location')
        #logger.info(f"[UPDATE LOCATION] Received location: {location}")
        
        if not location:
            #logger.error("[UPDATE LOCATION] No location provided in request")
            return jsonify({'error': 'Location is required'}), 400
        
        #logger.info(f"[UPDATE LOCATION] Fetching weather data for {location}")
        
        # Fetch weather data first
        weather_data = get_weather_data(city=location)
        if not weather_data:
            logger.error(f"[UPDATE LOCATION] Failed to get weather data for {location}")
            return jsonify({'error': 'Failed to get weather data for this location'}), 400
            
        #logger.info(f"[UPDATE LOCATION] Successfully got weather data: {weather_data}")
            
        # Update session data
        session['location'] = location
        session['weather_data'] = weather_data
        session['weather_timestamp'] = datetime.utcnow().isoformat()
        
        # Force session to be saved
        session.modified = True
        
        #logger.info(f"[UPDATE LOCATION] Successfully updated session with location: {location}")
        #logger.info(f"[UPDATE LOCATION] Weather data cached: {weather_data}")
        
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