# Copilot Instructions for Outfit Finder

## Architecture Overview

**Outfit Finder** is a Flask-based web application that leverages OpenAI Vision API to analyze clothing items from outfit images and generates personalized outfit recommendations based on weather, user preferences, and past feedback.

### Core Data Flow

1. **Image Upload & Analysis** → User uploads outfit image → OpenAI Vision analyzes image → `ClothingItem` records created
2. **Wardrobe Management** → `ClothingItem` records stored by user → Used for outfit matching
3. **Recommendations Engine** → `weather_recommendations.py` retrieves user's wardrobe + preferences + feedback history → Calls OpenAI to generate context-aware recommendations
4. **Chat System** → User chats with AI stylist (`Chat` model) → Stores conversation history

### Database Models (Key Fields)

- **User**: `username`, `email`, `password_hash`, `height`, `weight`, `gender`, `preferences` (JSON), `ai_notes`, relationships to `Outfit`, `Chat`, `RecommendationFeedback`
- **Outfit**: `user_id`, `image_url`, `analysis` (text), `items` (JSON), `occasion`, `weather` (JSON), `created_at`, `rating`
- **ClothingItem**: `user_id`, `outfit_id`, `type`, `color`, `brand`, `material`, `key_features`, `overall_vibe`, `short_description`, `image_url` (NEW: separate from outfit)
- **Chat**: `user_id`, `messages` (JSON list with sender/text), timestamps
- **RecommendationFeedback**: Tracks user feedback on AI recommendations for improvement

## Critical Files & Workflows

### Outfit Upload & Item Extraction (`outfits.py`)

**Key Function**: `analyze_clothing_image(image_data)` (lines 17-116)
- Uses OpenAI `gpt-4o-mini` with Vision to extract **structured clothing data**
- **Important**: Expects response with natural language description + JSON array called `items_json`
- Each item must include: `type`, `color`, `brand`, `material`, `key_features`, `overall_vibe`
- Saves both `Outfit` record and individual `ClothingItem` records to database
- **Pattern**: Items are split apart—one `ClothingItem` per clothing piece, linked to `outfit_id`

### Recommendations Engine (`weather_recommendations.py`)

**Key Function**: `get_weather_recommendations(user_id, weather_data)` (lines 14-80+)
- **Context Assembly**: Combines wardrobe + user preferences + feedback history + current weather
- **Why This Matters**: AI makes recommendations only from items user actually owns
- **User Preferences**: Stored in `User.preferences` (JSON)—can include style preferences, fit preferences, color restrictions
- **Feedback Loop**: Uses `RecommendationFeedback` table to understand what user liked/disliked previously
- **AI Notes**: `User.ai_notes` captures personal style notes (runs hot/cold, recent wear, vibe preferences)
- **Output Format**: Returns JSON array with 3 outfit recommendations, each with `items`, `explanation`, `confidence`, `image_url` list
- **Key Detail**: Explanations should mention temperature, user's style vibe, and wardrobe context (lines 42-61)

### Chat System (`routes/chat.py`)

- `Chat` model stores messages as JSON list: `[{"sender": "user"|"assistant", "text": "..."}, ...]`
- `/chat-history` endpoint returns paginated chat previews (first 50 chars)
- `/chat/<id>` shows full conversation; `/chat` POST creates/updates chats
- **Pattern**: Each message includes sender and text; AI responses come from OpenAI API

### AI Data Management (`routes/ai_data.py`)

- Displays paginated user outfits + recommendation feedback (8 items per page)
- `POST /update-ai-notes` updates `User.ai_notes` for style context
- `POST /recommendation-feedback` saves feedback ('like'/'dislike') for training the recommendations engine

## Development Workflows

### Database Migrations
```bash
flask db init          # First time only
flask db migrate       # Create migration files after model changes
flask db upgrade       # Apply migrations to SQLite DB
```

### Running the App
```bash
# Ensure `.env` has: SECRET_KEY, OPENAI_API_KEY, WEATHER_API_KEY
python app.py          # Starts Flask dev server at http://localhost:5000
```

### Key Environment Variables
- `OPENAI_API_KEY`: Required for Vision & chat endpoints
- `WEATHER_API_KEY`: Required for weather data (OpenWeatherMap or similar)
- `SECRET_KEY`: Flask session secret
- `FLASK_DEBUG`: Set to 'true' for dev mode (default in `config.py`)

## Project-Specific Patterns

### JSON Serialization for Models
- Models use `.to_dict()` methods (e.g., `ClothingItem.to_dict()`, `Chat.to_dict()`) to convert to JSON
- Used for API responses and AI prompt construction (see `weather_recommendations.py` line 40)

### Image Storage
- Uploaded images saved to `static/uploads/<user_id>/` (auto-created)
- **Important Change**: `image_url` now stored directly in `ClothingItem` table (migration: `4f0e91e4265e_add_image_url_to_clothing_item_table.py`)
- ClothingItem records also have independent `image_url` for direct item linking

### AI Prompting Pattern
- **Vision Analysis**: Asks for both natural language AND structured JSON in same response (outfits.py lines 29-95)
- **Recommendations**: Passes full context as JSON blob to prompt (weather_recommendations.py lines 40-61)
- **Chat**: System prompt frames assistant as "fashion expert" for style advice

### Frontend-Backend Communication
- CSRF protection enabled (`Flask-WTF`)
- CORS configured to allow all origins in dev (app.py line 31)
- File uploads: `MAX_CONTENT_LENGTH` = 16MB; allowed extensions: `{png, jpg, jpeg, gif}`

## Common Tasks & Code Locations

| Task | File(s) |
|------|---------|
| Add new user field | `models.py` → `User` class + migration |
| Change AI prompt behavior | `outfits.py` (line 29+) or `weather_recommendations.py` (line 42+) |
| Adjust recommendation logic | `weather_recommendations.py` (entire function) |
| Add new clothing item field | `models.py` → `ClothingItem` + `ClothingItem.to_dict()` |
| Store new user feedback type | `models.py` → `RecommendationFeedback` feedback field options |
| Debug API calls | Check `logger` output (Flask logging configured app.py line 24) |

## Conventions & Considerations

1. **JSON Fields**: Use JSON for flexible data (preferences, items list, chat messages). Always convert to dict in `.to_dict()` methods.
2. **User Isolation**: All queries filter by `user_id` to ensure data privacy—never miss this.
3. **OpenAI API**: Uses `gpt-4o-mini` (cost-optimized) for Vision analysis and recommendations.
4. **Database**: SQLite by default; configured for `outfit_finder.db` in app directory.
5. **Error Handling**: Routes use try-except with `db.session.rollback()` on failure.

## Quick Reference: Key Imports

```python
from models import db, User, Outfit, ClothingItem, Chat, RecommendationFeedback
from openai import OpenAI
from flask import Blueprint, jsonify, request, session
from flask_login import login_required, current_user
```
