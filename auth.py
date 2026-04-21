"""
Authentication helpers: session-backed login, decorators, current-user lookup.
"""
import logging
from functools import wraps
from flask import session, jsonify, g, request
from models import User, get_session, ROLE_ADMIN


SESSION_USER_KEY = 'user_id'
logger = logging.getLogger(__name__)


def login_user(user):
    """Persist the user id in the Flask session."""
    session.clear()
    session[SESSION_USER_KEY] = user.id
    session.permanent = True
    logger.info("Login success: user_id=%s username=%s role=%s", user.id, user.username, user.role)


def logout_user():
    """Clear the session."""
    uid = session.get(SESSION_USER_KEY)
    session.clear()
    if uid:
        logger.info("Logout: user_id=%s", uid)


def load_current_user():
    """Load the current user from the session into flask.g. Returns User or None."""
    if hasattr(g, 'current_user'):
        return g.current_user

    user_id = session.get(SESSION_USER_KEY)
    if not user_id:
        g.current_user = None
        return None

    db = get_session()
    try:
        user = db.query(User).filter_by(id=user_id).first()
    finally:
        db.close()

    if user is None:
        # Session references a deleted user; clear it.
        logger.warning("Session referenced missing user_id=%s; clearing session", user_id)
        session.clear()
    g.current_user = user
    return user


def login_required(view):
    """Require an authenticated user for the decorated view."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = load_current_user()
        if user is None:
            logger.info("Unauthorized access attempt: %s %s", request.method, request.path)
            return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    """Require an authenticated admin user for the decorated view."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = load_current_user()
        if user is None:
            logger.info("Unauthorized access attempt: %s %s", request.method, request.path)
            return jsonify({'status': 'error', 'message': 'Authentication required'}), 401
        if user.role != ROLE_ADMIN:
            logger.warning(
                "Forbidden (non-admin) access attempt: user_id=%s username=%s %s %s",
                user.id, user.username, request.method, request.path,
            )
            return jsonify({'status': 'error', 'message': 'Admin privileges required'}), 403
        return view(*args, **kwargs)
    return wrapper
