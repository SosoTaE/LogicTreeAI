from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    ForeignKey, UniqueConstraint, Float, JSON, inspect, text,
)
from sqlalchemy.orm import declarative_base, relationship, Session
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

Base = declarative_base()

# Keys supported per-user for LLM configuration
SETTINGS_KEYS = [
    'openai_key',
    'anthropic_key',
    'gemini_key',
    'local_endpoint_url',
    'local_model_name',
]

ROLE_ADMIN = 'admin'
ROLE_USER = 'user'
VALID_ROLES = {ROLE_ADMIN, ROLE_USER}


class User(Base):
    """Application user with role-based access"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default=ROLE_USER)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    settings = relationship(
        'Settings', back_populates='user',
        cascade='all, delete-orphan',
    )
    conversations = relationship(
        'Conversation', back_populates='user',
        cascade='all, delete-orphan',
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class Settings(Base):
    """Per-user key-value table for storing API keys"""
    __tablename__ = 'settings'
    __table_args__ = (UniqueConstraint('user_id', 'key', name='uq_settings_user_key'),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    key = Column(String(50), nullable=False)
    value = Column(Text, nullable=True)

    user = relationship('User', back_populates='settings')

    def __repr__(self):
        return f"<Settings(user_id={self.user_id}, key='{self.key}')>"


class Conversation(Base):
    """Represents a single chat tree owned by a user"""
    __tablename__ = 'conversations'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship('User', back_populates='conversations')
    messages = relationship(
        'Message', back_populates='conversation',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f"<Conversation(id={self.id}, title='{self.title}')>"


class Message(Base):
    """Core branching model using Adjacency List pattern"""
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('messages.id'), nullable=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    model_used = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship('Conversation', back_populates='messages')
    parent = relationship('Message', remote_side=[id], backref='children')

    def get_conversation_path(self, session):
        """
        Reconstruct the full conversation path from this message up to the root.
        Returns a list of messages ordered from root to current message.
        """
        path = []
        current = self
        while current is not None:
            path.append(current)
            if current.parent_id is not None:
                current = session.query(Message).filter_by(id=current.parent_id).first()
            else:
                current = None
        path.reverse()
        return path

    def to_dict(self, include_children=False):
        result = {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'parent_id': self.parent_id,
            'role': self.role,
            'content': self.content,
            'model_used': self.model_used,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if include_children and hasattr(self, 'children'):
            result['children'] = [child.to_dict(include_children=True) for child in self.children]
            result['child_count'] = len(self.children)
        return result

    def __repr__(self):
        return f"<Message(id={self.id}, role='{self.role}', parent_id={self.parent_id})>"


class MultiAgentSession(Base):
    """Represents a multi-agent discussion session where multiple LLMs collaborate"""
    __tablename__ = 'multi_agent_sessions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(200), nullable=False)
    initial_problem = Column(Text, nullable=False)
    participating_models = Column(JSON, nullable=False)  # List of model names
    model_roles = Column(JSON, nullable=True)  # Dict mapping model to role
    max_rounds = Column(Integer, nullable=False, default=3)
    current_round = Column(Integer, nullable=False, default=0)
    conversation_mode = Column(String(20), nullable=False, default='sequential')  # sequential or parallel
    moderator_model = Column(String(100), nullable=True)  # Optional LLM that picks the next speaker; null = round-robin
    status = Column(String(20), nullable=False, default='active')  # active, completed, stopped
    synthesis = Column(Text, nullable=True)  # Synthesized conclusion of the discussion
    synthesis_model = Column(String(100), nullable=True)  # Model used for synthesis
    synthesized_at = Column(DateTime, nullable=True)  # When synthesis was created
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    user = relationship('User')
    turns = relationship(
        'MultiAgentTurn', back_populates='session',
        cascade='all, delete-orphan',
        order_by='MultiAgentTurn.turn_number, MultiAgentTurn.created_at'
    )

    def to_dict(self, include_turns=False):
        result = {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'initial_problem': self.initial_problem,
            'participating_models': self.participating_models,
            'model_roles': self.model_roles,
            'max_rounds': self.max_rounds,
            'current_round': self.current_round,
            'conversation_mode': self.conversation_mode,
            'moderator_model': self.moderator_model,
            'status': self.status,
            'synthesis': self.synthesis,
            'synthesis_model': self.synthesis_model,
            'synthesized_at': self.synthesized_at.isoformat() if self.synthesized_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
        if include_turns:
            result['turns'] = [turn.to_dict() for turn in self.turns]
            result['turns_by_round'] = self._group_turns_by_round()
        return result

    def _group_turns_by_round(self):
        """Group turns by round/turn number for easier display"""
        rounds = {}
        for turn in self.turns:
            turn_num = turn.turn_number
            if turn_num not in rounds:
                rounds[turn_num] = []
            rounds[turn_num].append(turn.to_dict())
        return rounds

    def __repr__(self):
        return f"<MultiAgentSession(id={self.id}, title='{self.title}', status='{self.status}')>"


class MultiAgentTurn(Base):
    """Represents a single turn/response in a multi-agent discussion"""
    __tablename__ = 'multi_agent_turns'

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('multi_agent_sessions.id', ondelete='CASCADE'), nullable=False)
    turn_number = Column(Integer, nullable=False)  # Sequential turn or round number
    model_name = Column(String(100), nullable=False)
    model_role = Column(String(200), nullable=True)
    content = Column(Text, nullable=False)
    duration = Column(Float, nullable=True)  # Time taken for LLM response
    error = Column(Text, nullable=True)  # Error message if failed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship('MultiAgentSession', back_populates='turns')

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'turn_number': self.turn_number,
            'round_number': self.turn_number,  # Alias for backwards compatibility
            'model_name': self.model_name,
            'model_role': self.model_role,
            'content': self.content,
            'duration': self.duration,
            'error': self.error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<MultiAgentTurn(id={self.id}, turn={self.turn_number}, model='{self.model_name}')>"


engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)


def init_db():
    """Initialize the database and create all tables"""
    Base.metadata.create_all(engine)
    _apply_lightweight_migrations()


def _apply_lightweight_migrations():
    """
    SQLAlchemy create_all only creates missing tables, never altering
    existing ones. Add columns introduced after a table was first
    created so existing chat_app.db files don't need a manual reset.
    Each entry is idempotent: it checks the live schema before issuing
    ALTER TABLE.
    """
    additions = [
        ('multi_agent_sessions', 'moderator_model', 'VARCHAR(100)'),
    ]
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table_name, column_name, column_type in additions:
            if not inspector.has_table(table_name):
                continue
            existing = {c['name'] for c in inspector.get_columns(table_name)}
            if column_name in existing:
                continue
            conn.execute(text(
                f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}'
            ))


def get_session():
    """Get a new database session"""
    return Session(engine)


def seed_user_settings(session, user_id):
    """Create empty setting rows for a newly created user."""
    for key_name in SETTINGS_KEYS:
        existing = session.query(Settings).filter_by(user_id=user_id, key=key_name).first()
        if not existing:
            session.add(Settings(user_id=user_id, key=key_name, value=''))


def get_user_api_keys(session, user_id):
    """Return dict of {key: value} for a user's API keys."""
    rows = session.query(Settings).filter_by(user_id=user_id).all()
    keys = {k: None for k in SETTINGS_KEYS}
    for row in rows:
        keys[row.key] = row.value if row.value else None
    return keys


def create_user(session, username, password, role=ROLE_USER):
    """Create a new user and seed their settings. Raises on duplicate username."""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")
    if not username or not password:
        raise ValueError("Username and password are required")

    existing = session.query(User).filter_by(username=username).first()
    if existing:
        raise ValueError(f"User '{username}' already exists")

    user = User(username=username, role=role)
    user.set_password(password)
    session.add(user)
    session.flush()  # assign id
    seed_user_settings(session, user.id)
    return user
