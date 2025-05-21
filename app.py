from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
import os
from dotenv import load_dotenv
import openai
import requests
from datetime import datetime
import json
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import base64
from openai import OpenAI

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///outfit_finder.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

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
    preferences = db.Column(db.JSON)
    outfits = db.relationship('Outfit', backref='user', lazy=True)

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

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    return render_template('index.html')

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
        if file:
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
                return jsonify({'error': str(e)}), 500
    
    if uploaded_files:
        db.session.commit()
        return jsonify({
            'message': f'Successfully uploaded {len(uploaded_files)} images',
            'files': uploaded_files
        })
    
    return jsonify({'error': 'Invalid file'}), 400

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
        # Get all outfits for the current user
        outfits = Outfit.query.filter_by(user_id=current_user.id).order_by(Outfit.created_at.desc()).all()
        print(f"Found {len(outfits)} outfits for user {current_user.id}")  # Debug print
        
        # Check if the uploads directory exists
        uploads_dir = os.path.join(app.root_path, 'static', 'uploads', str(current_user.id))
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
            print(f"Created uploads directory: {uploads_dir}")  # Debug print
        
        return render_template('my_outfits.html', outfits=outfits)
    except Exception as e:
        print(f"Error in my_outfits route: {str(e)}")  # Debug print
        flash('Error loading outfits. Please try again.')
        return redirect(url_for('index'))

@app.route('/preferences', methods=['POST'])
@login_required
def save_preferences():
    data = request.json
    current_user.height = data.get('height')
    current_user.weight = data.get('weight')
    
    # Get selected styles
    styles = data.get('styles', [])
    
    # If there's a custom style, add it to the list and store it separately
    other_style = data.get('other_style')
    if other_style and other_style.strip():
        styles.append('other')  # Add 'other' to the styles list
        current_user.preferences = {
            'styles': styles,
            'custom_style': other_style.strip()
        }
    else:
        current_user.preferences = {
            'styles': styles
        }
    
    db.session.commit()
    return jsonify({'message': 'Preferences saved successfully'})

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

def get_weather_data():
    # Implement weather API integration
    # This is a placeholder
    return {
        'temperature': 20,
        'condition': 'sunny',
        'humidity': 60
    }

def analyze_clothing_image(image_data):
    try:
        # Call OpenAI Vision API to analyze the image
        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analyze this clothing item. Describe its type, color, style, and any notable features. Also suggest what occasions it would be suitable for."
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
        
        return response.choices[0].message.content
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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create uploads directory if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True) 