from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import timezone

from .database import Base

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    salla_user_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    store_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="user")
    auth_sessions: Mapped[List["AuthSession"]] = relationship(back_populates="user")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id: Mapped[str] = mapped_column(String, primary_key=True) # session_id (uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False, default="New Conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    role: Mapped[str] = mapped_column(String) # user, assistant
    content: Mapped[str] = mapped_column(Text) # JSON string or text
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")

class AuthSession(Base):
    __tablename__ = "auth_sessions"
    
    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    access_token: Mapped[str] = mapped_column(String)
    refresh_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    scope: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    merchant_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    user: Mapped[Optional["User"]] = relationship(back_populates="auth_sessions")
