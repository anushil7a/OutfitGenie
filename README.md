# AI Outfit Finder

A web application that helps users find and manage their outfits using AI-powered analysis and recommendations.

## Features

- User authentication (login/register)
- Upload clothing items with AI analysis
- View uploaded outfits
- Delete outfits
- Get outfit recommendations based on occasion and weather
- Save outfit preferences

## Technologies Used

- Python/Flask
- SQLAlchemy
- OpenAI GPT-4 Vision API
- TailwindCSS
- JavaScript

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd outfit-finder
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
Create a `.env` file with the following variables:
```
SECRET_KEY=your-secret-key
OPENAI_API_KEY=your-openai-api-key
```

5. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

6. Run the application:
```bash
python app.py
```

## Usage

1. Register a new account or login
2. Upload clothing items from your wardrobe
3. View your uploaded outfits in the "My Outfits" section
4. Get outfit recommendations based on occasion and weather
5. Save your preferences for better recommendations

## Contributing

1. Fork the repository
2. Create a new branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 