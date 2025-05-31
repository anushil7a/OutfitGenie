from flask import Blueprint, render_template, request, jsonify, url_for, current_app, flash, redirect
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from models import db, Outfit, ClothingItem
import base64
from openai import OpenAI
import json
import logging

outfits = Blueprint('outfits', __name__)
logger = logging.getLogger(__name__)

def analyze_clothing_image(image_data):
    try:
        # Call OpenAI Vision API
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": '''Analyze all clothing items and accessories in the image and provide a natural, flowing description in the following format:

For each clothing item that is visible in the image, describe short descriptive bullet points that includes:
- Type and style (e.g., "loose-fitting crewneck t-shirt", "straight-fit cargo pants")
- Color and material (e.g., "blue", "white", "cotton", "polyester", etc.)
- Key features and design elements (e.g., "striped", "logo", "ripped knees", words on the shirt, etc.)
- overall vibe (e.g., "casual", "sporty", "business casual", "formal", etc.)
- brand or what its related to (if you see Barcelona logo, it's related to Barcelona, if you see Nike logo, it's related to Nike, etc.) (if visible, else null)
- if its a pair of shoes, describe the type of shoes (e.g., "sneakers", "boots", "sandals", "flip flops", etc.) 
- Do the same for accessories and clothes that are visible in the image.
- Other imporantant information that you think is relevant to the item.

Format your response EXACTLY like this example (including the line breaks), but ONLY include sections that are visible in the image:

<strong>Barcelona Jersey:</strong><br>
- Type and style: Short-sleeved sports jersey<br>
- Color and material: Blue with pink accents, polyester<br>
- Key features and design elements: Features a Barcelona logo, colorful abstract patterns<br>
- Overall vibe: Sporty<br>
- Brand or what it's related to: FC Barcelona<br>
<br>
<strong>Black Backpack:</strong><br>
- Type and style: Casual backpack<br>
- Color and material: Black, synthetic material<br>
- Key features and design elements: Multiple compartments, adjustable straps<br>
- Overall vibe: Casual and functional<br>
- Brand or what it's related to: null<br>
<br>
<strong>Wireless Earbuds:</strong><br>
- Type and style: In-ear wireless earbuds<br>
- Color and material: White, plastic<br>
- Key features and design elements: Compact design, noise isolation<br>
- Overall vibe: Modern and practical<br>
- Brand or what it's related to: null

Keep descriptions concise but detailed enough for AI outfit matching. 
Focus on the overall look and feel while including specific details about style, fit, and features. 
ONLY describe items that are clearly visible in the image.
I want you to describe the items in a way that is easy to understand and use for AI outfit matching and recommendations (bullet points are fine).

---

After the natural language description, ALSO return a JSON array called items_json. For each visible clothing and accessory item, include:
- type (e.g., "t-shirt", "jeans", "hat", "shoes", "accessory", "earbuds", etc.)
- color (e.g., "blue", "white", etc.)
- brand or what its related to (if you see Barcelona logo, it's related to Barcelona, if you see Nike logo, it's related to Nike, etc.) (if visible, else null)
- material (if visible, else null)
- key_features (e.g., "striped", "logo", "ripped knees", words on the shirt, etc.)
- overall_vibe (e.g., "casual", "sporty", "business casual", "formal", etc.)

Format Example:
items_json = [
  {
    "type": "Sleeveless sports t-shirt",
    "color": "Gray and white",
    "brand": "FC Barcelona",
    "material": "Polyester",
    "key_features": "Features word "HERNDON" in bold red letters, an illustration of a hornet, and the word "Hornets" beneath",
    "overall_vibe": "Casual and sporty"
  },
  ...
]

If a field is not visible, set it to null.
Return the natural language description first, then the JSON array as shown above.'''
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
            max_tokens=1000
        )
        
        # Get the response content
        content = response.choices[0].message.content.strip()
        
        # Split the response into bullet points and items_json
        bullet_points = content
        items = None
        if 'items_json =' in content:
            parts = content.split('items_json =', 1)
            bullet_points = parts[0].strip()
            import re
            match = re.search(r'items_json\s*=\s*(\[.*\])', content, re.DOTALL)
            if match:
                items_str = match.group(1)
                try:
                    items = json.loads(items_str)
                except Exception as e:
                    print(f"Error parsing items_json: {str(e)}")
                    items = None
        
        return bullet_points, items
    except Exception as e:
        print(f"Error analyzing image: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error details: {e.__dict__ if hasattr(e, '__dict__') else 'No details available'}")
        return "Error analyzing image. Please try again.", None

def generate_short_description(item):
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        prompt = f"""Given these details about a clothing item:
        Type: {item['type']}
        Color: {item['color']}
        Brand: {item['brand']}
        Material: {item['material']}
        Key Features: {item['key_features']}
        Overall Vibe: {item['overall_vibe']}
        
        Write a short, natural 1-2 sentence description that captures the essence of this item."""
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a fashion expert who writes concise, engaging descriptions of clothing items."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating description: {str(e)}")
        return None

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
                        bullet_points, items = analyze_clothing_image(img_file.read())
                        
                        # Create the outfit
                        outfit = Outfit(
                            user_id=current_user.id,
                            image_url=url_for('static', filename=f'uploads/{current_user.id}/{filename}'),
                            analysis=bullet_points,
                            items=items,
                            created_at=datetime.utcnow()
                        )
                        db.session.add(outfit)
                        db.session.flush()  # Get the outfit ID
                        
                        # Create clothing items
                        if items:
                            for item in items:
                                # Generate short description
                                short_description = generate_short_description(item)
                                
                                clothing_item = ClothingItem(
                                    user_id=current_user.id,
                                    outfit_id=outfit.id,
                                    type=item.get('type'),
                                    color=item.get('color'),
                                    brand=item.get('brand'),
                                    material=item.get('material'),
                                    key_features=item.get('key_features'),
                                    overall_vibe=item.get('overall_vibe'),
                                    short_description=short_description,
                                    image_url=outfit.image_url,  # Store the image link directly in the clothing_item table
                                    created_at=datetime.utcnow()
                                )
                                db.session.add(clothing_item)
                        
                        uploaded_files.append({
                            'message': 'Image uploaded successfully',
                            'analysis': bullet_points,
                            'items': items,
                            'image_url': outfit.image_url
                        })
                except Exception as e:
                    print(f"Error processing image: {str(e)}")
                    # If there's an error processing the image, still save the file, but do NOT add another Outfit
                    uploaded_files.append({
                        'message': 'Image uploaded successfully (processing failed)',
                        'image_url': url_for('static', filename=f'uploads/{current_user.id}/{filename}')
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
        print("Accessing /my-outfits route")  # Debug print
        # Get page number from query parameters, default to 1
        page = request.args.get('page', 1, type=int)
        per_page = 6  # Number of items per page
        
        # Get outfits for the current user with pagination
        outfits_pagination = Outfit.query.filter_by(user_id=current_user.id)\
            .order_by(Outfit.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        # Get clothing items for each outfit
        for outfit in outfits_pagination.items:
            clothing_items = ClothingItem.query.filter_by(outfit_id=outfit.id).all()
            print(f"Clothing items for outfit {outfit.id}: {clothing_items}")
            if clothing_items:
                outfit.items = [item.to_dict() for item in clothing_items]
        
        # Check if the uploads directory exists
        uploads_dir = os.path.join(current_app.root_path, 'static', 'uploads', str(current_user.id))
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
            print(f"Created uploads directory: {uploads_dir}")  # Debug print
        
        return render_template('my_outfits.html', outfits=outfits_pagination.items, pagination=outfits_pagination)
    except Exception as e:
        import traceback
        print("Error in my_outfits route:", str(e))
        traceback.print_exc()
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
