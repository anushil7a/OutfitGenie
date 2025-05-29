from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from models import db, Outfit, RecommendationFeedback
from datetime import datetime
import logging

ai_data_bp = Blueprint('ai_data', __name__)
logger = logging.getLogger(__name__)

@ai_data_bp.route('/ai-data')
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

@ai_data_bp.route('/update-ai-notes', methods=['POST'])
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

@ai_data_bp.route('/recommendation-feedback', methods=['POST'])
@login_required
def save_recommendation_feedback():
    try:
        data = request.json
        logger.info(f"Received feedback data: {data}")
        
        recommendation = data.get('recommendation')
        question = data.get('question')
        feedback = data.get('feedback')  # 'like', 'dislike', or 'remove'
        context = data.get('context', {})  # Optional context data
        
        if not recommendation:
            logger.error("No recommendation provided")
            return jsonify({'error': 'No recommendation provided'}), 400
            
        if not question:
            logger.error("No question provided")
            return jsonify({'error': 'No question provided'}), 400
            
        if feedback == 'remove':
            # Remove feedback entry if it exists
            existing_feedback = RecommendationFeedback.query.filter_by(
                user_id=current_user.id,
                recommendation=recommendation,
                question=question
            ).first()
            if existing_feedback:
                db.session.delete(existing_feedback)
                db.session.commit()
                logger.info(f"Deleted feedback for user {current_user.id}")
                return jsonify({'message': 'Feedback removed successfully'})
            else:
                return jsonify({'error': 'Feedback not found'}), 404
        
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

@ai_data_bp.route('/recommendation-feedback/<int:feedback_id>', methods=['DELETE'])
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