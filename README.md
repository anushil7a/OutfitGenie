# AI Outfit Finder

AI Outfit Finder is a web application that helps users manage their wardrobe, analyze clothing items using AI, and receive personalized outfit recommendations based on weather, occasion, and personal style. The app leverages OpenAI's vision and language models to analyze uploaded images, extract detailed clothing information, and generate concise descriptions for each item. Users can also chat with an AI stylist for fashion advice.

## Features

- **User Authentication:** Register and log in securely to manage your wardrobe and outfits.
- **AI-Powered Clothing Analysis:** Upload images of your outfits; the app uses OpenAI Vision to detect and describe each clothing item and accessory, extracting type, style, color, material, brand, and key features.
- **Wardrobe Management:** Each detected clothing item is saved as a separate record, allowing you to view, edit, and manage your wardrobe.
- **Outfit Gallery:** View all your uploaded outfits, each with detailed AI-generated analysis and item breakdowns.
- **Personalized Recommendations:** Get outfit suggestions tailored to your preferences, the occasion, and real-time weather data for your location.
- **Weather Integration:** The app fetches current weather data to recommend suitable outfits.
- **AI Stylist Chat:** Chat with an AI fashion assistant for advice, outfit ideas, or to ask style questions.
- **Feedback System:** Provide feedback on recommendations to improve future suggestions.
- **Data Privacy:** All your data is stored securely and only accessible to you.

## Data Model

- **User:** Stores user info, preferences, physical attributes, and AI notes.
- **Outfit:** Represents an uploaded outfit image, with AI analysis, occasion, weather, and a list of detected items.
- **ClothingItem:** Each detected item in an outfit, with fields for type, color, brand, material, key features, overall vibe, short description, and image link.
- **Chat:** Stores user-AI conversations for fashion advice.
- **RecommendationFeedback:** Stores user feedback on AI outfit recommendations.

## Technologies Used

- Python, Flask, Flask-Login, Flask-Migrate, Flask-WTF, Flask-CORS
- SQLAlchemy (ORM)
- OpenAI GPT-4 Vision API
- TailwindCSS, JavaScript
- SQLite (default, can be swapped for other DBs)

## Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd outfit_finder
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   Create a `.env` file in the root directory with:
   ```
   SECRET_KEY=your-secret-key
   OPENAI_API_KEY=your-openai-api-key
   WEATHER_API_KEY=your-openweather-api-key
   ```

5. **Initialize the database:**
   ```bash
   flask db upgrade
   ```
   (If running for the first time, you may need to run `flask db init` and `flask db migrate` before `flask db upgrade`.)

6. **Run the application:**
   ```bash
   python app.py
   ```

7. **Access the app:**
   Open your browser and go to `http://localhost:5000`

## Usage

1. **Register or log in** to your account.
2. **Upload an outfit image** via the upload form. The AI will analyze the image and extract each visible clothing item as a separate entry.
3. **View your wardrobe and outfits** in the "My Outfits" section. Each outfit displays detailed AI-generated analysis and a breakdown of items.
4. **Get recommendations** for what to wear based on the weather and your preferences.
5. **Chat with the AI stylist** for personalized fashion advice.
6. **Provide feedback** on recommendations to help improve the AI.

## Contributing

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 