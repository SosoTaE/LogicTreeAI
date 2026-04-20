from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, Session
from config import Config

Base = declarative_base()

class Settings(Base):
    """Key-value table for storing API keys"""
    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Settings(key='{self.key}')>"


class Conversation(Base):
    """Represents a single chat tree"""
    __tablename__ = 'conversations'

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship to messages
    messages = relationship('Message', back_populates='conversation', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Conversation(id={self.id}, title='{self.title}')>"


class Message(Base):
    """Core branching model using Adjacency List pattern"""
    __tablename__ = 'messages'

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('messages.id'), nullable=True)  # None for root messages
    role = Column(String(20), nullable=False)  # 'system', 'user', or 'assistant'
    content = Column(Text, nullable=False)
    model_used = Column(String(50), nullable=True)  # Which LLM was used (for assistant messages)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    conversation = relationship('Conversation', back_populates='messages')
    parent = relationship('Message', remote_side=[id], backref='children')

    def get_conversation_path(self, session):
        """
        Reconstruct the full conversation path from this message up to the root.
        Returns a list of messages ordered from root to current message.
        This is critical for providing the correct context window to the LLM.
        """
        path = []
        current = self

        # Traverse up the tree to the root
        while current is not None:
            path.append(current)
            if current.parent_id is not None:
                current = session.query(Message).filter_by(id=current.parent_id).first()
            else:
                current = None

        # Reverse to get root-to-current order
        path.reverse()
        return path

    def to_dict(self, include_children=False):
        """Convert message to dictionary for JSON serialization"""
        result = {
            'id': self.id,
            'conversation_id': self.conversation_id,
            'parent_id': self.parent_id,
            'role': self.role,
            'content': self.content,
            'model_used': self.model_used,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

        if include_children and hasattr(self, 'children'):
            result['children'] = [child.to_dict(include_children=True) for child in self.children]
            result['child_count'] = len(self.children)

        return result

    def __repr__(self):
        return f"<Message(id={self.id}, role='{self.role}', parent_id={self.parent_id})>"


# Database initialization
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)

def init_db():
    """Initialize the database and create all tables"""
    Base.metadata.create_all(engine)

    # Initialize default API key entries if they don't exist
    session = Session(engine)
    try:
        for key_name in ['openai_key', 'anthropic_key', 'gemini_key', 'local_endpoint_url', 'local_model_name']:
            existing = session.query(Settings).filter_by(key=key_name).first()
            if not existing:
                session.add(Settings(key=key_name, value=''))
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()

def get_session():
    """Get a new database session"""
    return Session(engine)
