from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, Outfit, Chat, RecommendationFeedback
import json
from openai import OpenAI
import os
from datetime import datetime

chat_bp = Blueprint('chat', __name__)

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

@chat_bp.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@chat_bp.route('/chat-history')
@login_required
def get_chat_history():
    chats = Chat.query.filter_by(user_id=current_user.id).order_by(Chat.updated_at.desc()).all()
    return jsonify({
        'chats': [chat.to_dict() for chat in chats]
    })

@chat_bp.route('/chat/<int:chat_id>')
@login_required
def get_chat(chat_id):
    chat = Chat.query.get_or_404(chat_id)
    if chat.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    return jsonify({
        'messages': chat.messages
    })

@chat_bp.route('/chat/<int:chat_id>', methods=['DELETE'])
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

@chat_bp.route('/chat', methods=['POST'])
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
            prompt = f"""As an AI fashion assistant, help the user with their outfit question: \"{message}\"\n\nUser's uploaded clothes:\n{json.dumps(outfits_info, indent=2)}\n\nUser's preferences and measurements:\n{json.dumps(current_user.preferences, indent=2)}\nHeight: {current_user.height}inches\nWeight: {current_user.weight}lbs\nGender: {current_user.gender}\n\nUser's AI Notes:\n{current_user.ai_notes or 'No additional notes provided.'}\n\nUser's past feedback on recommendations:\n{json.dumps(feedback_info, indent=2)}\n\nIMPORTANT: \n1. Only recommend outfits using the clothes the user has already uploaded.\n2. Consider the user's past feedback when making recommendations.\n3. Try to avoid recommending similar outfits that were previously disliked.\n4. Prioritize styles and combinations that were previously liked.\n\nPlease provide a VERY SHORT response (1-2 sentences maximum) that:\n1. Directly answers their question\n2. References specific items from their uploaded clothes\n3. Includes the image_url of the recommended items\n\nFormat your response as JSON with two fields:\n1. \"response\": your short answer\n2. \"image_urls\": list of image URLs for the recommended items\n\nResponse:"""
        else:
            prompt = f"""As an AI fashion assistant, help the user with their outfit question: \"{message}\"\n\nUser's uploaded clothes:\n{json.dumps(outfits_info, indent=2)}\n\nUser's preferences and measurements:\n{json.dumps(current_user.preferences, indent=2)}\nHeight: {current_user.height}inches\nWeight: {current_user.weight}lbs\nGender: {current_user.gender}\n\nUser's AI Notes:\n{current_user.ai_notes or 'No additional notes provided.'}\n\nUser's past feedback on recommendations:\n{json.dumps(feedback_info, indent=2)}\n\nYou can recommend both items the user owns and items they don't own yet. When suggesting items they don't own, clearly indicate this in your response.\n\nIMPORTANT: \n1. Consider the user's past feedback when making recommendations.\n2. Try to avoid recommending similar outfits that were previously disliked.\n3. Prioritize styles and combinations that were previously liked.\n\nPlease provide a VERY SHORT response (1-2 sentences maximum) that:\n1. Directly answers their question\n2. References specific items from their uploaded clothes (if applicable)\n3. Suggests additional items they don't own (if relevant)\n4. Includes the image_url of any recommended items they own\n\nIMPORTANT: Your response MUST be in valid JSON format with these exact fields:\n{{\n    \"response\": \"your short answer here\",\n    \"image_urls\": [\"list\", \"of\", \"image\", \"urls\", \"from\", \"user's\", \"wardrobe\"]\n}}\n\nResponse:"""

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