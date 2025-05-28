from flask import Blueprint, render_template, request, jsonify, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from models import db, Outfit
import base64
from openai import OpenAI
import json
import logging

outfits = Blueprint('outfits', __name__)
logger = logging.getLogger(__name__)

def analyze_clothing_image(image_data):
    try:
        # Call OpenAI Vision API to analyze the image
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
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

@outfits.route('/upload', methods=['POST'])
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
                user_upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], str(current_user.id))
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

@outfits.route('/my-outfits')
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
        uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads', str(current_user.id))
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
            print(f"Created uploads directory: {uploads_dir}")  # Debug print
        
        return render_template('my_outfits.html', outfits=outfits_pagination.items, pagination=outfits_pagination)
    except Exception as e:
        print(f"Error in my_outfits route: {str(e)}")  # Debug print
        flash('Error loading outfits. Please try again.')
        return redirect(url_for('index'))

@outfits.route('/delete-outfit/<int:outfit_id>', methods=['POST'])
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
                image_path = os.path.join(current_app.root_path, outfit.image_url.lstrip('/'))
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

@outfits.route('/update-outfit-description/<int:outfit_id>', methods=['POST'])
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
