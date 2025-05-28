from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_cors import CORS
import os
from dotenv import load_dotenv
import openai
import requests
from datetime import datetime, timedelta
import json
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import base64
from openai import OpenAI
import logging

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
db = SQLAlchemy(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    gender = db.Column(db.String(20))
    preferences = db.Column(db.JSON)
    ai_notes = db.Column(db.Text)  # Add AI notes field
    outfits = db.relationship('Outfit', backref='user', lazy=True)
    chats = db.relationship('Chat', backref='user', lazy=True)
    feedback = db.relationship('RecommendationFeedback', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Outfit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_url = db.Column(db.String(255))
    analysis = db.Column(db.Text)
    items = db.Column(db.JSON)
    occasion = db.Column(db.String(50))
    weather = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    rating = db.Column(db.Integer)

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    messages = db.Column(db.JSON)  # List of messages with sender and text
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'preview': self.messages[0]['text'][:50] + '...' if self.messages else 'New Chat',
            'timestamp': self.created_at.isoformat()
        }

class RecommendationFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recommendation = db.Column(db.Text, nullable=False)  # The recommendation text
    question = db.Column(db.Text, nullable=False)  # The user's question that led to the recommendation
    feedback = db.Column(db.String(10), nullable=False)  # 'like' or 'dislike'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    context = db.Column(db.JSON)  # Store context like occasion, weather, etc.

    def to_dict(self):
        return {
            'id': self.id,
            'recommendation': self.recommendation,
            'question': self.question,
            'feedback': self.feedback,
            'created_at': self.created_at.isoformat(),
            'context': self.context
        }

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

        # Comment out recommendations for now
        # recommendations = None
        # if weather_data and current_user.is_authenticated:
        #     try:
        #         recommendations = get_weather_recommendations(weather_data, current_user.preferences)
        #         if not recommendations:
        #             recommendations = {
        #                 "outfit": "A comfortable layered outfit suitable for the current weather.",
        #                 "reasoning": "This outfit is chosen based on the current temperature and conditions.",
        #                 "items": ["Item 1", "Item 2", "Item 3"]
        #             }
        #     except Exception as e:
        #         logger.error(f"Error getting recommendations: {str(e)}")
        #         recommendations = {
        #             "outfit": "A comfortable layered outfit suitable for the current weather.",
        #             "reasoning": "This outfit is chosen based on the current temperature and conditions.",
        #             "items": ["Item 1", "Item 2", "Item 3"]
        #         }

        logger.info(f"[DEBUG] Final weather data being sent to template: {weather_data}")
        return render_template('index.html',
                             weather=weather_data,
                             recommendations=None,  # Set recommendations to None
                             current_location=location)
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        return render_template('index.html', current_location=location)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
            
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
@login_required
def upload_clothing():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    
    files = request.files.getlist('image')
    if not files or files[0].filename == '':
        return jsonify({'error': 'No selected file'}), 400

    uploaded_files = []
    for file in files:
        if file and file.filename:
            try:
                filename = secure_filename(file.filename)
                # Create user-specific upload directory
                user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
                os.makedirs(user_upload_dir, exist_ok=True)
                
                # Save file
                filepath = os.path.join(user_upload_dir, filename)
                file.save(filepath)
                
                # Process image with OpenAI Vision API
                try:
                    with open(filepath, 'rb') as img_file:
                        analysis = analyze_clothing_image(img_file.read())
                        
                        # Create new outfit record
                        outfit = Outfit(
                            user_id=current_user.id,
                            image_url=url_for('static', filename=f'uploads/{current_user.id}/{filename}'),
                            analysis=analysis,
                            created_at=datetime.utcnow()
                        )
                        db.session.add(outfit)
                        uploaded_files.append({
                            'message': 'Image uploaded successfully',
                            'analysis': analysis,
                            'image_url': outfit.image_url
                        })
                except Exception as e:
                    print(f"Error processing image: {str(e)}")
                    # If there's an error processing the image, still save the file
                    outfit = Outfit(
                        user_id=current_user.id,
                        image_url=url_for('static', filename=f'uploads/{current_user.id}/{filename}'),
                        created_at=datetime.utcnow()
                    )
                    db.session.add(outfit)
                    uploaded_files.append({
                        'message': 'Image uploaded successfully (processing failed)',
                        'image_url': outfit.image_url
                    })
            except Exception as e:
                print(f"Error saving file: {str(e)}")
                return jsonify({'error': f'Error saving file: {str(e)}'}), 500
    
    if uploaded_files:
        try:
            db.session.commit()
            return jsonify({
                'message': f'Successfully uploaded {len(uploaded_files)} images',
                'files': uploaded_files
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Database error: {str(e)}'}), 500
    
    return jsonify({'error': 'No valid files uploaded'}), 400

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
        preferences = {
            'styles': data.get('styles', []),
            'skin_tone_color': data.get('skin_tone_color'),
            'skin_tone_text': data.get('skin_tone_text'),
            'hair_color': data.get('hair_color'),
            'hair_color_text': data.get('other_hair_color') if data.get('hair_color') == 'other' else None,
        }
        other_style = data.get('other_style')
        if other_style and other_style.strip():
            if 'other' not in preferences['styles']:
                preferences['styles'].append('other')
            preferences['custom_style'] = other_style.strip()

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

def analyze_clothing_image(image_data):
    try:
        # Call OpenAI Vision API to analyze the image
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Analyze this clothing item and provide a natural, flowing description in the following format:

For each clothing item that is visible in the image, describe it in a natural paragraph that includes:
- Type and style (e.g., "loose-fitting crewneck t-shirt", "straight-fit cargo pants")
- Color and material (1/2 words)
- Key features and design elements
- overall vibe (1/2 words)

Format your response EXACTLY like this example (including the line breaks), but ONLY include sections that are visible in the image:

<strong>Top:</strong> [Description]<br>
<strong>Bottom:</strong> [Description]<br>
<strong>Shoes/Accessories:</strong> [Description]

Keep descriptions concise but detailed enough for AI outfit matching. Focus on the overall look and feel while including specific details about style, fit, and features. ONLY describe items that are clearly visible in the image."""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64.b64encode(image_data).decode('utf-8')}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )
        
        # Get the response content
        content = response.choices[0].message.content.strip()
        
        # Format the headers in bold and add proper line breaks
        sections = ['Top:', 'Bottom:', 'Shoes/Accessories:']
        formatted_content = content
        
        for section in sections:
            if section in formatted_content:
                # Replace the section header with a bold version
                formatted_content = formatted_content.replace(section, f"<strong>{section}</strong>")
                # Add a single line break after the section if it's not the last one
                if section != sections[-1]:
                    formatted_content = formatted_content.replace(f"<strong>{section}</strong>", f"<strong>{section}</strong><br>")
        
        return formatted_content
    except Exception as e:
        print(f"Error analyzing image: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error details: {e.__dict__ if hasattr(e, '__dict__') else 'No details available'}")
        return "Error analyzing image. Please try again."

def generate_outfit_recommendations(occasion, weather, user_preferences):
    # Implement OpenAI API call for outfit recommendations
    # This is a placeholder
    return {
        'outfits': [
            {
                'id': 1,
                'items': ['blue shirt', 'khaki pants', 'brown shoes'],
                'occasion': occasion,
                'weather_appropriate': True
            }
        ]
    }

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@app.route('/chat-history')
@login_required
def get_chat_history():
    chats = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.updated_at.desc()).all()
    return jsonify({
        'chats': [chat.to_dict() for chat in chats]
    })

@app.route('/chat/<int:chat_id>')
@login_required
def get_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    if chat.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    return jsonify({
        'messages': chat.messages
    })

@app.route('/chat/<int:chat_id>', methods=['DELETE'])
@login_required
def delete_chat(chat_id):
    try:
        chat = Chat.query.get_or_404(chat_id)
        if chat.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        db.session.delete(chat)
        db.session.commit()
        return jsonify({'message': 'Chat deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
@login_required
def chat_message():
    data = request.json
    message = data.get('message', '').strip()
    chat_id = data.get('chat_id')  # Get chat_id from request if it exists
    wardrobe_only = data.get('wardrobe_only', False)  # Get wardrobe_only flag
    print(f"wardrobe_only: {wardrobe_only}")
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400

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

        # Get user's past feedback
        feedback = RecommendationFeedback.query.filter_by(user_id=current_user.id).all()
        feedback_info = []
        for entry in feedback:
            feedback_info.append({
                'recommendation': entry.recommendation,
                'feedback': entry.feedback,
                'context': entry.context
            })

        # Create a prompt for the AI based on the mode
        print(f"wardrobe_only: {wardrobe_only}")
        if wardrobe_only:
            prompt = f"""As an AI fashion assistant, help the user with their outfit question: "{message}"

User's uploaded clothes:
{json.dumps(outfits_info, indent=2)}

User's preferences and measurements:
{json.dumps(current_user.preferences, indent=2)}
Height: {current_user.height}inches
Weight: {current_user.weight}lbs
Gender: {current_user.gender}

User's AI Notes:
{current_user.ai_notes or 'No additional notes provided.'}

User's past feedback on recommendations:
{json.dumps(feedback_info, indent=2)}

IMPORTANT: 
1. Only recommend outfits using the clothes the user has already uploaded.
2. Consider the user's past feedback when making recommendations.
3. Try to avoid recommending similar outfits that were previously disliked.
4. Prioritize styles and combinations that were previously liked.

Please provide a VERY SHORT response (1-2 sentences maximum) that:
1. Directly answers their question
2. References specific items from their uploaded clothes
3. Includes the image_url of the recommended items

Format your response as JSON with two fields:
1. "response": your short answer
2. "image_urls": list of image URLs for the recommended items

Response:"""
        else:
            prompt = f"""As an AI fashion assistant, help the user with their outfit question: "{message}"

User's uploaded clothes:
{json.dumps(outfits_info, indent=2)}

User's preferences and measurements:
{json.dumps(current_user.preferences, indent=2)}
Height: {current_user.height}inches
Weight: {current_user.weight}lbs
Gender: {current_user.gender}

User's AI Notes:
{current_user.ai_notes or 'No additional notes provided.'}

User's past feedback on recommendations:
{json.dumps(feedback_info, indent=2)}

You can recommend both items the user owns and items they don't own yet. When suggesting items they don't own, clearly indicate this in your response.

IMPORTANT: 
1. Consider the user's past feedback when making recommendations.
2. Try to avoid recommending similar outfits that were previously disliked.
3. Prioritize styles and combinations that were previously liked.

Please provide a VERY SHORT response (1-2 sentences maximum) that:
1. Directly answers their question
2. References specific items from their uploaded clothes (if applicable)
3. Suggests additional items they don't own (if relevant)
4. Includes the image_url of any recommended items they own

IMPORTANT: Your response MUST be in valid JSON format with these exact fields:
{{
    "response": "your short answer here",
    "image_urls": ["list", "of", "image", "urls", "from", "user's", "wardrobe"]
}}

Response:"""

        # Get AI response
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a concise fashion assistant. Keep responses to 1-2 sentences maximum. Always format your response as valid JSON with 'response' and 'image_urls' fields."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150
        )

        ai_response = response.choices[0].message.content.strip()

        try:
            # Try to parse the response as JSON
            response_data = json.loads(ai_response)
            
            # Validate response format
            if not isinstance(response_data, dict) or 'response' not in response_data or 'image_urls' not in response_data:
                raise json.JSONDecodeError("Invalid response format", ai_response, 0)
            
            # Ensure image_urls is a list
            if not isinstance(response_data['image_urls'], list):
                response_data['image_urls'] = []
            
            # Get or create chat
            if chat_id:
                chat = Chat.query.get(chat_id)
                if not chat or chat.user_id != current_user.id:
                    chat = Chat(user_id=current_user.id, messages=[])
            else:
                chat = Chat(user_id=current_user.id, messages=[])
            
            # Add new messages
            chat.messages.extend([
                {'sender': 'You', 'text': message},
                {'sender': 'AI', 'text': response_data['response'], 'image_urls': response_data['image_urls']}
            ])
            
            db.session.add(chat)
            db.session.commit()
            
            # Add chat_id to response
            response_data['chat_id'] = chat.id
            
            return jsonify(response_data)
        except json.JSONDecodeError as e:
            print(f"Error parsing AI response: {str(e)}")
            print(f"Raw AI response: {ai_response}")
            # If parsing fails, try to extract a meaningful response
            try:
                # Try to find JSON-like structure in the response
                import re
                json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                if json_match:
                    response_data = json.loads(json_match.group())
                else:
                    # If no JSON found, create a structured response
                    response_data = {
                        'response': ai_response,
                        'image_urls': []
                    }
            except:
                # If all parsing attempts fail, return a clean error response
                response_data = {
                    'response': 'I apologize, but I had trouble formatting my response. Please try asking your question again.',
                    'image_urls': []
                }
            
            return jsonify(response_data)

    except Exception as e:
        print(f"Error in chat_message: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error details: {e.__dict__ if hasattr(e, '__dict__') else 'No details available'}")
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