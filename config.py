import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')
    DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///outfit_finder.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # OpenAI settings
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Weather API settings
    WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
    
    # File upload settings
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Application settings
    OUTFIT_CATEGORIES = [
        'casual',
        'formal',
        'business',
        'sporty',
        'bohemian',
        'evening',
        'beach',
        'winter',
        'summer'
    ]
    
    WEATHER_CONDITIONS = [
        'sunny',
        'rainy',
        'cloudy',
        'snowy',
        'windy',
        'foggy'
    ]
    
    # Recommendation settings
    MAX_RECOMMENDATIONS = 5
    MIN_RATING_THRESHOLD = 0.5
    
    @staticmethod
    def init_app(app):
        # Create upload folder if it doesn't exist
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        
        # Additional initialization if needed
        pass

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False
    
    # Production-specific settings
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Production-specific initialization
        import logging
        from logging.handlers import RotatingFileHandler
        
        # Set up logging
        handler = RotatingFileHandler('logs/outfit_finder.log', maxBytes=10000, backupCount=1)
        handler.setLevel(logging.INFO)
        app.logger.addHandler(handler)

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
} 