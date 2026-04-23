"""
Branching LLM Chat Application - Flask Backend
"""
import logging
import time
from flask import Flask, request, jsonify, render_template, redirect, url_for, g, session
from flask_cors import CORS
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from logging_config import setup_logging
setup_logging()

from models import (
    init_db, get_session, create_user, get_user_api_keys,
    Settings, Conversation, Message, User,
    MultiAgentSession, MultiAgentTurn,
    SETTINGS_KEYS, VALID_ROLES, ROLE_USER,
)
from config import Config
from auth import (
    login_user, logout_user, load_current_user,
    login_required, admin_required,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, supports_credentials=True)

init_db()
logger.info("Database initialized at %s", Config.SQLALCHEMY_DATABASE_URI)

from llm_service import llm_service
from multi_agent_service import MultiAgentService

multi_agent_service = MultiAgentService(llm_service)


@app.before_request
def _log_request_start():
    g._request_started = time.perf_counter()


@app.after_request
def _log_request_end(response):
    # Skip static asset noise
    if request.path.startswith('/static/'):
        return response
    started = getattr(g, '_request_started', None)
    duration_ms = (time.perf_counter() - started) * 1000 if started else -1
    user = getattr(g, 'current_user', None)
    user_part = f"user_id={user.id}" if user else "user=anon"
    logger.info(
        "%s %s -> %s %s %.1fms",
        request.method, request.path, response.status_code, user_part, duration_ms,
    )
    return response


@app.errorhandler(Exception)
def _log_unhandled(exc):
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.path, exc)
    # Let Flask produce the normal error response
    raise exc


def _current_user():
    return g.current_user


# ==================== Pages ====================

@app.route('/')
def index():
    """Serve the main application page, redirecting unauthenticated users to login."""
    if load_current_user() is None:
        return redirect(url_for('login_page'))
    return render_template('index.html')


@app.route('/login')
def login_page():
    """Serve the login page. If already authenticated, redirect home."""
    if load_current_user() is not None:
        return redirect(url_for('index'))
    return render_template('login.html')


# ==================== Auth Endpoints ====================

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        logger.info("Login rejected (missing fields) from ip=%s", request.remote_addr)
        return jsonify({'status': 'error', 'message': 'Username and password required'}), 400

    db = get_session()
    try:
        user = db.query(User).filter_by(username=username).first()
        if user is None or not user.check_password(password):
            logger.warning(
                "Login failed: username=%s ip=%s reason=%s",
                username, request.remote_addr,
                'no-such-user' if user is None else 'bad-password',
            )
            return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401
        login_user(user)
        return jsonify({'status': 'success', 'user': user.to_dict()})
    finally:
        db.close()


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    logout_user()
    return jsonify({'status': 'success'})


@app.route('/api/auth/me', methods=['GET'])
@login_required
def auth_me():
    return jsonify(_current_user().to_dict())


# ==================== User Management (admin only) ====================

@app.route('/api/users', methods=['GET'])
@admin_required
def list_users():
    db = get_session()
    try:
        users = db.query(User).order_by(User.created_at.asc()).all()
        return jsonify([u.to_dict() for u in users])
    finally:
        db.close()


@app.route('/api/users', methods=['POST'])
@admin_required
def create_new_user():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    role = (data.get('role') or ROLE_USER).strip()

    if role not in VALID_ROLES:
        return jsonify({'status': 'error', 'message': 'Invalid role'}), 400
    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Username and password required'}), 400
    if len(password) < 6:
        return jsonify({'status': 'error', 'message': 'Password must be at least 6 characters'}), 400

    db = get_session()
    try:
        user = create_user(db, username, password, role=role)
        db.commit()
        logger.info(
            "User created by admin: new_user_id=%s new_username=%s role=%s by_admin=%s",
            user.id, user.username, user.role, _current_user().username,
        )
        return jsonify({'status': 'success', 'user': user.to_dict()}), 201
    except ValueError as e:
        db.rollback()
        logger.info("User creation rejected by admin=%s: %s", _current_user().username, e)
        return jsonify({'status': 'error', 'message': str(e)}), 400
    except Exception as e:
        db.rollback()
        logger.exception("User creation failed")
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    current = _current_user()
    if user_id == current.id:
        logger.warning("Admin %s attempted to delete self", current.username)
        return jsonify({'status': 'error', 'message': 'Cannot delete yourself'}), 400

    db = get_session()
    try:
        target = db.query(User).filter_by(id=user_id).first()
        if target is None:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404
        target_name = target.username
        db.delete(target)
        db.commit()
        logger.info(
            "User deleted by admin: user_id=%s username=%s by_admin=%s",
            user_id, target_name, current.username,
        )
        return jsonify({'status': 'success'})
    except Exception as e:
        db.rollback()
        logger.exception("User delete failed for user_id=%s", user_id)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


# ==================== Settings Endpoints ====================

@app.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    """Fetch the current user's API keys."""
    user = _current_user()
    db = get_session()
    try:
        rows = db.query(Settings).filter_by(user_id=user.id).all()
        result = {k: '' for k in SETTINGS_KEYS}
        for row in rows:
            result[row.key] = row.value or ''
        return jsonify(result)
    finally:
        db.close()


@app.route('/api/settings', methods=['POST'])
@login_required
def update_settings():
    """Update the current user's API keys."""
    user = _current_user()
    data = request.json or {}
    db = get_session()
    try:
        updated_keys = []
        for key_name in SETTINGS_KEYS:
            if key_name in data:
                setting = db.query(Settings).filter_by(user_id=user.id, key=key_name).first()
                if setting:
                    setting.value = data[key_name]
                else:
                    db.add(Settings(user_id=user.id, key=key_name, value=data[key_name]))
                updated_keys.append(key_name)
        db.commit()
        # Log which keys were updated but never the values themselves.
        logger.info(
            "Settings updated: user_id=%s keys=%s", user.id, ','.join(updated_keys) or 'none',
        )
        return jsonify({'status': 'success', 'message': 'Settings updated'})
    except Exception as e:
        db.rollback()
        logger.exception("Settings update failed for user_id=%s", user.id)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/models', methods=['GET'])
@login_required
def get_models():
    """Fetch available models using the current user's keys."""
    user = _current_user()
    db = get_session()
    try:
        user_keys = get_user_api_keys(db, user.id)
    finally:
        db.close()

    try:
        models = llm_service.get_available_models(user_keys)
        return jsonify(models)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ==================== Conversation Endpoints ====================

@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    user = _current_user()
    db = get_session()
    try:
        conversations = (
            db.query(Conversation)
            .filter_by(user_id=user.id)
            .order_by(Conversation.created_at.desc())
            .all()
        )
        result = [{
            'id': c.id,
            'title': c.title,
            'created_at': c.created_at.isoformat(),
        } for c in conversations]
        return jsonify(result)
    finally:
        db.close()


@app.route('/api/conversations', methods=['POST'])
@login_required
def create_conversation():
    user = _current_user()
    data = request.json or {}
    title = data.get('title', f'New Chat {datetime.now().strftime("%Y-%m-%d %H:%M")}')

    db = get_session()
    try:
        conversation = Conversation(title=title, user_id=user.id)
        db.add(conversation)
        db.commit()
        logger.info("Conversation created: id=%s user_id=%s", conversation.id, user.id)
        return jsonify({
            'id': conversation.id,
            'title': conversation.title,
            'created_at': conversation.created_at.isoformat(),
        }), 201
    except Exception as e:
        db.rollback()
        logger.exception("Conversation create failed user_id=%s", user.id)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/conversations/<int:conversation_id>/tree', methods=['GET'])
@login_required
def get_conversation_tree(conversation_id):
    user = _current_user()
    db = get_session()
    try:
        conversation = db.query(Conversation).filter_by(id=conversation_id, user_id=user.id).first()
        if not conversation:
            return jsonify({'status': 'error', 'message': 'Conversation not found'}), 404

        messages = db.query(Message).filter_by(conversation_id=conversation_id).all()
        root_messages = [msg for msg in messages if msg.parent_id is None]

        def build_tree(message):
            msg_dict = message.to_dict(include_children=False)
            children = [child for child in messages if child.parent_id == message.id]
            msg_dict['children'] = [build_tree(child) for child in children]
            msg_dict['child_count'] = len(children)
            return msg_dict

        tree = [build_tree(root) for root in root_messages]
        return jsonify({
            'conversation_id': conversation_id,
            'title': conversation.title,
            'tree': tree,
        })
    finally:
        db.close()


@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation(conversation_id):
    user = _current_user()
    db = get_session()
    try:
        conversation = db.query(Conversation).filter_by(id=conversation_id, user_id=user.id).first()
        if not conversation:
            return jsonify({'status': 'error', 'message': 'Conversation not found'}), 404
        db.delete(conversation)
        db.commit()
        logger.info("Conversation deleted: id=%s user_id=%s", conversation_id, user.id)
        return jsonify({'status': 'success', 'message': 'Conversation deleted'})
    except Exception as e:
        db.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


# ==================== Message Endpoints ====================

@app.route('/api/messages', methods=['POST'])
@login_required
def create_message():
    """Create a new message, broadcast to selected models, save responses."""
    user = _current_user()
    data = request.json or {}
    conversation_id = data.get('conversation_id')
    parent_id = data.get('parent_id')
    content = data.get('content')

    target_models = data.get('target_models')
    if not target_models:
        single_model = data.get('target_model', 'gpt-4o')
        target_models = [single_model]
    if not isinstance(target_models, list):
        target_models = [target_models]

    if not conversation_id or not content:
        return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

    db = get_session()
    try:
        conversation = db.query(Conversation).filter_by(id=conversation_id, user_id=user.id).first()
        if not conversation:
            return jsonify({'status': 'error', 'message': 'Conversation not found'}), 404

        if parent_id:
            parent = db.query(Message).filter_by(id=parent_id, conversation_id=conversation_id).first()
            if not parent:
                return jsonify({'status': 'error', 'message': 'Parent message not found'}), 404

        user_message = Message(
            conversation_id=conversation_id,
            parent_id=parent_id,
            role='user',
            content=content,
            model_used=None,
        )
        db.add(user_message)
        db.commit()
        logger.info(
            "Message posted: user_id=%s conv_id=%s msg_id=%s parent_id=%s chars=%d models=%s",
            user.id, conversation_id, user_message.id, parent_id, len(content), target_models,
        )

        conversation_path = user_message.get_conversation_path(db)
        user_keys = get_user_api_keys(db, user.id)

        assistant_messages = []
        errors = []

        def call_and_save(target_model):
            try:
                response = llm_service.call_llm(conversation_path, target_model, user_keys)
                return (target_model, response, None)
            except ValueError as e:
                return (target_model, None, {'model': target_model, 'error': str(e), 'type': 'config'})
            except Exception as e:
                return (target_model, None, {'model': target_model, 'error': str(e), 'type': 'api'})

        broadcast_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=len(target_models) or 1) as executor:
            future_to_model = {executor.submit(call_and_save, m): m for m in target_models}
            for future in as_completed(future_to_model):
                target_model, response, err = future.result()
                if err:
                    errors.append(err)
                else:
                    assistant_message = Message(
                        conversation_id=conversation_id,
                        parent_id=user_message.id,
                        role='assistant',
                        content=response,
                        model_used=target_model,
                    )
                    db.add(assistant_message)
                    db.flush()
                    assistant_messages.append(assistant_message)

        db.commit()
        assistant_messages_dicts = [msg.to_dict() for msg in assistant_messages]
        broadcast_duration = time.perf_counter() - broadcast_started

        logger.info(
            "Broadcast complete: user_id=%s conv_id=%s msg_id=%s ok=%d failed=%d duration=%.2fs",
            user.id, conversation_id, user_message.id,
            len(assistant_messages_dicts), len(errors), broadcast_duration,
        )
        if errors:
            for e in errors:
                logger.warning(
                    "Broadcast error: user_id=%s msg_id=%s model=%s type=%s err=%s",
                    user.id, user_message.id, e['model'], e['type'], e['error'],
                )

        response_data = {
            'status': 'success' if assistant_messages_dicts else 'partial_failure',
            'user_message': user_message.to_dict(),
            'assistant_messages': assistant_messages_dicts,
            'errors': errors if errors else None,
        }
        return jsonify(response_data), 201 if assistant_messages_dicts else 400

    except Exception as e:
        db.rollback()
        logger.exception("create_message failed user_id=%s conv_id=%s", user.id, conversation_id)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


# ==================== Multi-Agent Conversation Endpoints ====================

@app.route('/api/multi-agent/sessions', methods=['GET'])
@login_required
def get_multi_agent_sessions():
    """List all multi-agent sessions for the current user."""
    user = _current_user()
    db = get_session()
    try:
        sessions = (
            db.query(MultiAgentSession)
            .filter_by(user_id=user.id)
            .order_by(MultiAgentSession.created_at.desc())
            .all()
        )
        result = [session.to_dict(include_turns=False) for session in sessions]
        return jsonify(result)
    finally:
        db.close()


@app.route('/api/multi-agent/sessions', methods=['POST'])
@login_required
def create_multi_agent_session():
    """Create a new multi-agent discussion session."""
    user = _current_user()
    data = request.json or {}

    title = data.get('title', f'Multi-Agent Discussion {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    initial_problem = data.get('initial_problem', '').strip()
    participating_models = data.get('participating_models', [])
    model_roles = data.get('model_roles')  # Optional dict
    max_rounds = data.get('max_rounds', 3)
    conversation_mode = data.get('conversation_mode', 'sequential')  # sequential or parallel
    auto_start = data.get('auto_start', True)

    if not initial_problem:
        return jsonify({'status': 'error', 'message': 'initial_problem is required'}), 400
    if not participating_models or len(participating_models) < 2:
        return jsonify({'status': 'error', 'message': 'At least 2 models required'}), 400
    if max_rounds < 1 or max_rounds > 30:
        return jsonify({'status': 'error', 'message': 'max_rounds must be between 1 and 30'}), 400
    if conversation_mode not in ['sequential', 'parallel']:
        return jsonify({'status': 'error', 'message': 'conversation_mode must be sequential or parallel'}), 400

    db = get_session()
    try:
        # Create the session
        session_obj = MultiAgentSession(
            user_id=user.id,
            title=title,
            initial_problem=initial_problem,
            participating_models=participating_models,
            model_roles=model_roles,
            max_rounds=max_rounds,
            conversation_mode=conversation_mode,
            status='active',
        )
        db.add(session_obj)
        db.commit()

        logger.info(
            "Multi-agent session created: session_id=%s user_id=%s models=%s rounds=%d mode=%s",
            session_obj.id, user.id, participating_models, max_rounds, conversation_mode,
        )

        # Optionally run the first turn/round immediately
        if auto_start:
            user_keys = get_user_api_keys(db, user.id)

            if conversation_mode == 'sequential':
                # Run sequential conversation
                # For auto_start, we'll just run the first turn
                result = multi_agent_service.run_sequential_conversation(
                    initial_problem=initial_problem,
                    participating_models=participating_models,
                    total_turns=1,  # Just first turn for auto_start
                    user_keys=user_keys,
                    model_roles=model_roles,
                )

                # Save turns
                for turn in result['turns']:
                    turn_obj = MultiAgentTurn(
                        session_id=session_obj.id,
                        turn_number=turn['turn_number'],
                        model_name=turn['model_name'],
                        model_role=turn.get('role'),
                        content=turn['content'],
                        duration=turn.get('duration'),
                    )
                    db.add(turn_obj)

                # Save errors
                for error in result.get('errors', []):
                    turn_obj = MultiAgentTurn(
                        session_id=session_obj.id,
                        turn_number=error['turn_number'],
                        model_name=error['model_name'],
                        content='',
                        error=error['error'],
                    )
                    db.add(turn_obj)

                session_obj.current_round = 1

            else:  # parallel mode
                round_result = multi_agent_service.run_discussion_round(
                    initial_problem=initial_problem,
                    participating_models=participating_models,
                    discussion_history=[],
                    round_number=1,
                    user_keys=user_keys,
                    model_roles=model_roles,
                )

                # Save the round results
                for response in round_result['responses']:
                    turn = MultiAgentTurn(
                        session_id=session_obj.id,
                        turn_number=response['round_number'],
                        model_name=response['model_name'],
                        model_role=response.get('role'),
                        content=response['content'],
                        duration=response.get('duration'),
                    )
                    db.add(turn)

                # Save errors as turns with error field populated
                for error in round_result['errors']:
                    turn = MultiAgentTurn(
                        session_id=session_obj.id,
                        turn_number=error['round_number'],
                        model_name=error['model_name'],
                        content='',
                        error=error['error'],
                    )
                    db.add(turn)

                session_obj.current_round = 1

            db.commit()

            logger.info(
                "Multi-agent session started: session_id=%s mode=%s",
                session_obj.id, conversation_mode,
            )

        return jsonify({
            'status': 'success',
            'session': session_obj.to_dict(include_turns=True),
        }), 201

    except Exception as e:
        db.rollback()
        logger.exception("Multi-agent session creation failed: user_id=%s", user.id)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/multi-agent/sessions/<int:session_id>', methods=['GET'])
@login_required
def get_multi_agent_session(session_id):
    """Get a specific multi-agent session with all turns."""
    user = _current_user()
    db = get_session()
    try:
        session_obj = db.query(MultiAgentSession).filter_by(id=session_id, user_id=user.id).first()
        if not session_obj:
            return jsonify({'status': 'error', 'message': 'Session not found'}), 404

        return jsonify(session_obj.to_dict(include_turns=True))
    finally:
        db.close()


@app.route('/api/multi-agent/sessions/<int:session_id>/continue', methods=['POST'])
@login_required
def continue_multi_agent_session(session_id):
    """Continue a multi-agent session by running the next round."""
    user = _current_user()
    db = get_session()
    try:
        session_obj = db.query(MultiAgentSession).filter_by(id=session_id, user_id=user.id).first()
        if not session_obj:
            return jsonify({'status': 'error', 'message': 'Session not found'}), 404

        if session_obj.status != 'active':
            return jsonify({'status': 'error', 'message': f'Session is {session_obj.status}'}), 400

        if session_obj.current_round >= session_obj.max_rounds:
            session_obj.status = 'completed'
            session_obj.completed_at = datetime.utcnow()
            db.commit()
            return jsonify({
                'status': 'error',
                'message': 'Session has reached max rounds',
                'session': session_obj.to_dict(include_turns=True),
            }), 400

        # Get discussion history
        discussion_history = [turn.to_dict() for turn in session_obj.turns if not turn.error]

        # Run the next turn/round
        next_turn_num = session_obj.current_round + 1
        user_keys = get_user_api_keys(db, user.id)

        if session_obj.conversation_mode == 'sequential':
            # Sequential: Determine which model's turn it is
            # Models rotate in order
            model_index = (next_turn_num - 1) % len(session_obj.participating_models)
            current_model = session_obj.participating_models[model_index]
            role = session_obj.model_roles.get(current_model) if session_obj.model_roles else None

            # Create conversation prompt
            prompt = multi_agent_service.create_conversation_prompt(
                initial_problem=session_obj.initial_problem,
                conversation_history=discussion_history,
                current_model=current_model,
                role=role
            )

            messages = [{"role": "user", "content": prompt}]

            # Call the LLM
            try:
                from datetime import datetime as dt
                start_time = dt.now()
                response_content = multi_agent_service.llm_service.call_llm(
                    messages=messages,
                    target_model=current_model,
                    user_keys=user_keys
                )
                duration = (dt.now() - start_time).total_seconds()

                turn_obj = MultiAgentTurn(
                    session_id=session_obj.id,
                    turn_number=next_turn_num,
                    model_name=current_model,
                    model_role=role,
                    content=response_content,
                    duration=duration,
                )
                db.add(turn_obj)

                result = {
                    'turns': [{
                        'turn_number': next_turn_num,
                        'model_name': current_model,
                        'content': response_content,
                        'role': role,
                        'duration': duration
                    }],
                    'errors': []
                }

            except Exception as e:
                turn_obj = MultiAgentTurn(
                    session_id=session_obj.id,
                    turn_number=next_turn_num,
                    model_name=current_model,
                    content='',
                    error=str(e),
                )
                db.add(turn_obj)

                result = {
                    'turns': [],
                    'errors': [{
                        'turn_number': next_turn_num,
                        'model_name': current_model,
                        'error': str(e)
                    }]
                }

            result_key = 'turn'

        else:  # parallel mode
            result = multi_agent_service.run_discussion_round(
                initial_problem=session_obj.initial_problem,
                participating_models=session_obj.participating_models,
                discussion_history=discussion_history,
                round_number=next_turn_num,
                user_keys=user_keys,
                model_roles=session_obj.model_roles,
            )

            # Save the round results
            for response in result['responses']:
                turn = MultiAgentTurn(
                    session_id=session_obj.id,
                    turn_number=response['round_number'],
                    model_name=response['model_name'],
                    model_role=response.get('role'),
                    content=response['content'],
                    duration=response.get('duration'),
                )
                db.add(turn)

            for error in result['errors']:
                turn = MultiAgentTurn(
                    session_id=session_obj.id,
                    turn_number=error['round_number'],
                    model_name=error['model_name'],
                    content='',
                    error=error['error'],
                )
                db.add(turn)

            result_key = 'round'

        session_obj.current_round = next_turn_num

        # Check if this was the last turn
        if next_turn_num >= session_obj.max_rounds:
            session_obj.status = 'completed'
            session_obj.completed_at = datetime.utcnow()

        db.commit()

        logger.info(
            "Multi-agent session turn %d completed: session_id=%s mode=%s",
            next_turn_num, session_obj.id, session_obj.conversation_mode,
        )

        return jsonify({
            'status': 'success',
            result_key: result,
            'session': session_obj.to_dict(include_turns=True),
        })

    except Exception as e:
        db.rollback()
        logger.exception("Multi-agent session continue failed: session_id=%s", session_id)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/multi-agent/sessions/<int:session_id>/stop', methods=['POST'])
@login_required
def stop_multi_agent_session(session_id):
    """Stop a multi-agent session early."""
    user = _current_user()
    db = get_session()
    try:
        session_obj = db.query(MultiAgentSession).filter_by(id=session_id, user_id=user.id).first()
        if not session_obj:
            return jsonify({'status': 'error', 'message': 'Session not found'}), 404

        if session_obj.status != 'active':
            return jsonify({'status': 'error', 'message': f'Session is already {session_obj.status}'}), 400

        session_obj.status = 'stopped'
        session_obj.completed_at = datetime.utcnow()
        db.commit()

        logger.info("Multi-agent session stopped: session_id=%s user_id=%s", session_id, user.id)

        return jsonify({
            'status': 'success',
            'message': 'Session stopped',
            'session': session_obj.to_dict(include_turns=True),
        })

    except Exception as e:
        db.rollback()
        logger.exception("Multi-agent session stop failed: session_id=%s", session_id)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/multi-agent/sessions/<int:session_id>/synthesize', methods=['POST'])
@login_required
def synthesize_multi_agent_session(session_id):
    """Synthesize a multi-agent discussion using a specified model."""
    user = _current_user()
    data = request.json or {}
    synthesis_model = data.get('synthesis_model', 'gpt-4o')

    db = get_session()
    try:
        session_obj = db.query(MultiAgentSession).filter_by(id=session_id, user_id=user.id).first()
        if not session_obj:
            return jsonify({'status': 'error', 'message': 'Session not found'}), 404

        # Get discussion history (exclude errors)
        discussion_history = [turn.to_dict() for turn in session_obj.turns if not turn.error]

        if not discussion_history:
            return jsonify({'status': 'error', 'message': 'No discussion to synthesize'}), 400

        user_keys = get_user_api_keys(db, user.id)

        synthesis_result = multi_agent_service.synthesize_discussion(
            initial_problem=session_obj.initial_problem,
            discussion_history=discussion_history,
            synthesis_model=synthesis_model,
            user_keys=user_keys,
        )

        logger.info(
            "Multi-agent session synthesized: session_id=%s synthesis_model=%s",
            session_id, synthesis_model,
        )

        return jsonify({
            'status': 'success',
            'synthesis': synthesis_result,
        })

    except Exception as e:
        logger.exception("Multi-agent session synthesis failed: session_id=%s", session_id)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/multi-agent/sessions/<int:session_id>', methods=['DELETE'])
@login_required
def delete_multi_agent_session(session_id):
    """Delete a multi-agent session."""
    user = _current_user()
    db = get_session()
    try:
        session_obj = db.query(MultiAgentSession).filter_by(id=session_id, user_id=user.id).first()
        if not session_obj:
            return jsonify({'status': 'error', 'message': 'Session not found'}), 404

        db.delete(session_obj)
        db.commit()

        logger.info("Multi-agent session deleted: session_id=%s user_id=%s", session_id, user.id)

        return jsonify({'status': 'success', 'message': 'Session deleted'})

    except Exception as e:
        db.rollback()
        logger.exception("Multi-agent session delete failed: session_id=%s", session_id)
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        db.close()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
