"""
Branching LLM Chat Application - Flask Backend
"""
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from models import init_db, get_session, Settings, Conversation, Message
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Initialize database BEFORE importing llm_service
init_db()

# Import llm_service AFTER database initialization
from llm_service import llm_service


@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html')


# ==================== Settings Endpoints ====================

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Fetch all API keys (values are sent to client)"""
    session = get_session()
    try:
        settings = session.query(Settings).all()
        result = {s.key: s.value or '' for s in settings}
        return jsonify(result)
    finally:
        session.close()


@app.route('/api/models', methods=['GET'])
def get_models():
    """Fetch available models for each configured provider"""
    try:
        models = llm_service.get_available_models()
        return jsonify(models)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update API keys"""
    data = request.json
    session = get_session()

    try:
        for key_name in ['openai_key', 'anthropic_key', 'gemini_key', 'local_endpoint_url', 'local_model_name']:
            if key_name in data:
                setting = session.query(Settings).filter_by(key=key_name).first()
                if setting:
                    setting.value = data[key_name]
                else:
                    session.add(Settings(key=key_name, value=data[key_name]))

        session.commit()
        return jsonify({'status': 'success', 'message': 'Settings updated'})
    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()


# ==================== Conversation Endpoints ====================

@app.route('/api/conversations', methods=['GET'])
def get_conversations():
    """List all chat trees"""
    session = get_session()
    try:
        conversations = session.query(Conversation).order_by(Conversation.created_at.desc()).all()
        result = [{
            'id': c.id,
            'title': c.title,
            'created_at': c.created_at.isoformat()
        } for c in conversations]
        return jsonify(result)
    finally:
        session.close()


@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    """Create a new chat tree"""
    data = request.json
    title = data.get('title', f'New Chat {datetime.now().strftime("%Y-%m-%d %H:%M")}')

    session = get_session()
    try:
        conversation = Conversation(title=title)
        session.add(conversation)
        session.commit()

        return jsonify({
            'id': conversation.id,
            'title': conversation.title,
            'created_at': conversation.created_at.isoformat()
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()


@app.route('/api/conversations/<int:conversation_id>/tree', methods=['GET'])
def get_conversation_tree(conversation_id):
    """Return the entire message tree for a conversation, structured hierarchically"""
    session = get_session()
    try:
        # Verify conversation exists
        conversation = session.query(Conversation).filter_by(id=conversation_id).first()
        if not conversation:
            return jsonify({'status': 'error', 'message': 'Conversation not found'}), 404

        # Get all messages for this conversation
        messages = session.query(Message).filter_by(conversation_id=conversation_id).all()

        # Build a map of messages by ID for quick lookup
        message_map = {msg.id: msg for msg in messages}

        # Find root messages (those with no parent)
        root_messages = [msg for msg in messages if msg.parent_id is None]

        # Recursive function to build tree structure
        def build_tree(message):
            msg_dict = message.to_dict(include_children=False)
            children = [child for child in messages if child.parent_id == message.id]
            msg_dict['children'] = [build_tree(child) for child in children]
            msg_dict['child_count'] = len(children)
            return msg_dict

        # Build the tree starting from root messages
        tree = [build_tree(root) for root in root_messages]

        return jsonify({
            'conversation_id': conversation_id,
            'title': conversation.title,
            'tree': tree
        })
    finally:
        session.close()


# ==================== Message Endpoints ====================

@app.route('/api/messages', methods=['POST'])
def create_message():
    """
    Create a new message and get LLM response(s).
    Accepts: conversation_id, parent_id, content, target_models (array)
    Multi-Model Broadcast Logic:
    1. Save the user message
    2. Reconstruct context history from parent_id to root
    3. Call each selected LLM with the same conversation history
    4. Save each LLM response as a separate child node of the user message
    5. Return user message and array of assistant messages (including partial failures)
    """
    data = request.json
    conversation_id = data.get('conversation_id')
    parent_id = data.get('parent_id')  # None for root message
    content = data.get('content')

    # Support both single model (backward compatibility) and multiple models
    target_models = data.get('target_models')
    if not target_models:
        # Fallback to single model for backward compatibility
        single_model = data.get('target_model', 'gpt-4o')
        target_models = [single_model]

    if not isinstance(target_models, list):
        target_models = [target_models]

    if not conversation_id or not content:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    session = get_session()
    try:
        # Verify conversation exists
        conversation = session.query(Conversation).filter_by(id=conversation_id).first()
        if not conversation:
            return jsonify({'status': 'error', 'message': 'Conversation not found'}), 404

        # Verify parent exists if provided
        if parent_id:
            parent = session.query(Message).filter_by(id=parent_id).first()
            if not parent:
                return jsonify({'status': 'error', 'message': 'Parent message not found'}), 404

        # Create user message
        user_message = Message(
            conversation_id=conversation_id,
            parent_id=parent_id,
            role='user',
            content=content,
            model_used=None
        )
        session.add(user_message)
        session.commit()  # Commit to get the ID

        # Reconstruct conversation history from this point
        conversation_path = user_message.get_conversation_path(session)

        # Multi-Model Broadcast: Call each LLM with the same context
        assistant_messages = []
        errors = []

        def call_and_save(target_model):
            try:
                llm_response = llm_service.call_llm(conversation_path, target_model)
                return (target_model, llm_response, None)
            except ValueError as e:
                return (target_model, None, {'model': target_model, 'error': str(e), 'type': 'config'})
            except Exception as e:
                return (target_model, None, {'model': target_model, 'error': str(e), 'type': 'api'})

        with ThreadPoolExecutor(max_workers=len(target_models) or 1) as executor:
            future_to_model = {executor.submit(call_and_save, model): model for model in target_models}
            for future in as_completed(future_to_model):
                target_model, response, err = future.result()
                if err:
                    errors.append(err)
                else:
                    # Save response to DB using a thread-local session or standard session carefully
                    # SQLAlchemy session is not thread-safe, so we commit after all threads finish
                    # Or better yet, we just collect results and commit in the main thread
                    assistant_message = Message(
                        conversation_id=conversation_id,
                        parent_id=user_message.id,
                        role='assistant',
                        content=response,
                        model_used=target_model
                    )
                    session.add(assistant_message)
                    session.flush() # assign an ID
                    assistant_messages.append(assistant_message)

        session.commit()
        assistant_messages = [msg.to_dict() for msg in assistant_messages]

        # Return results even if some models failed
        response_data = {
            'status': 'success' if assistant_messages else 'partial_failure',
            'user_message': user_message.to_dict(),
            'assistant_messages': assistant_messages,
            'errors': errors if errors else None
        }

        return jsonify(response_data), 201 if assistant_messages else 400

    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()


@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
def delete_conversation(conversation_id):
    """Delete a conversation and all its messages"""
    session = get_session()
    try:
        conversation = session.query(Conversation).filter_by(id=conversation_id).first()
        if not conversation:
            return jsonify({'status': 'error', 'message': 'Conversation not found'}), 404

        session.delete(conversation)
        session.commit()
        return jsonify({'status': 'success', 'message': 'Conversation deleted'})
    except Exception as e:
        session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        session.close()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
