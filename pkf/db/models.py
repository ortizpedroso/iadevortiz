from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email: Mapped[str | None] = mapped_column(String(320), unique=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(120), default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    projects: Mapped[list[Project]] = relationship(back_populates="user")
    chat_sessions: Mapped[list[ChatSession]] = relationship(back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    workspace_path: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_utcnow
    )

    user: Mapped[User] = relationship(back_populates="projects")
    specs: Mapped[list[SpecRecord]] = relationship(back_populates="project")
    chat_sessions: Mapped[list[ChatSession]] = relationship(back_populates="project")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    phase: Mapped[str] = mapped_column(String(32), default="IDLE")
    active_spec: Mapped[str | None] = mapped_column(String(120), nullable=True)
    spec_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    session_handoffs: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_utcnow
    )

    user: Mapped[User] = relationship(back_populates="chat_sessions")
    project: Mapped[Project | None] = relationship(back_populates="chat_sessions")
    messages: Mapped[list[Message]] = relationship(back_populates="session", order_by="Message.created_at")
    task_trees: Mapped[list[TaskTree]] = relationship(back_populates="session")
    file_changes: Mapped[list[FileChange]] = relationship(back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text, default="")
    agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class SpecRecord(Base):
    __tablename__ = "specs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="pending_approval")
    suggested_stack: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    confirmed_stack: Mapped[dict] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_utcnow
    )

    project: Mapped[Project | None] = relationship(back_populates="specs")


class TaskTree(Base):
    __tablename__ = "task_trees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    tree: Mapped[list] = mapped_column(JSON().with_variant(JSONB, "postgresql"), default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=_utcnow
    )

    session: Mapped[ChatSession] = relationship(back_populates="task_trees")


class FileChange(Base):
    __tablename__ = "file_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    path: Mapped[str] = mapped_column(String(500))
    action: Mapped[str] = mapped_column(String(32))
    snippet: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped[ChatSession | None] = relationship(back_populates="file_changes")
