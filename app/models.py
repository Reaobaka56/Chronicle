"""Database models for PR Changelog Generator."""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, ForeignKey, 
    Boolean, JSON, Enum, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()


class Tone(str, PyEnum):
    TECHNICAL = "technical"
    USER_FACING = "user_facing"
    MARKETING = "marketing"


class PlanTier(str, PyEnum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    github_id = Column(Integer, unique=True, nullable=False, index=True)
    github_login = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    plan_tier = Column(Enum(PlanTier), default=PlanTier.FREE, nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    repos = relationship("Repo", back_populates="owner", cascade="all, delete-orphan")
    installations = relationship("Installation", back_populates="user")


class Installation(Base):
    __tablename__ = "installations"

    id = Column(Integer, primary_key=True)
    github_installation_id = Column(Integer, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_login = Column(String(255), nullable=False)
    account_type = Column(String(50), default="User")  # User or Organization
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="installations")


class Repo(Base):
    __tablename__ = "repos"

    id = Column(Integer, primary_key=True)
    github_repo_id = Column(Integer, unique=True, nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    installation_id = Column(Integer, ForeignKey("installations.id"), nullable=True)

    full_name = Column(String(255), nullable=False, index=True)  # owner/repo
    name = Column(String(255), nullable=False)
    owner_login = Column(String(255), nullable=False)
    default_branch = Column(String(255), default="main")

    # Settings
    tone = Column(Enum(Tone), default=Tone.TECHNICAL)
    custom_template = Column(Text, nullable=True)  # Team tier
    slack_webhook_url = Column(String(512), nullable=True)
    auto_publish = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="repos")
    merged_prs = relationship("MergedPR", back_populates="repo", cascade="all, delete-orphan")
    releases = relationship("Release", back_populates="repo", cascade="all, delete-orphan")
    subscribers = relationship("Subscriber", back_populates="repo", cascade="all, delete-orphan")


class MergedPR(Base):
    __tablename__ = "merged_prs"
    __table_args__ = (
        UniqueConstraint("repo_id", "github_pr_number", name="uq_repo_pr"),
        Index("idx_merged_prs_repo_merged_at", "repo_id", "merged_at"),
    )

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repos.id"), nullable=False)
    github_pr_number = Column(Integer, nullable=False)

    title = Column(String(512), nullable=False)
    body = Column(Text, nullable=True)
    author_login = Column(String(255), nullable=False)
    merged_at = Column(DateTime, nullable=False, index=True)
    merge_commit_sha = Column(String(40), nullable=True)

    labels = Column(JSON, default=list)  # ["feat", "fix", "chore"]
    additions = Column(Integer, default=0)
    deletions = Column(Integer, default=0)
    files_changed = Column(Integer, default=0)

    # Processing state
    processed = Column(Boolean, default=False)
    included_in_release_id = Column(Integer, ForeignKey("releases.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    repo = relationship("Repo", back_populates="merged_prs")
    release = relationship("Release", back_populates="prs")


class Release(Base):
    __tablename__ = "releases"
    __table_args__ = (
        UniqueConstraint("repo_id", "tag_name", name="uq_repo_tag"),
    )

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repos.id"), nullable=False)

    tag_name = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)  # Generated changelog
    body_draft = Column(Text, nullable=True)  # Before publish

    github_release_id = Column(Integer, nullable=True)
    github_html_url = Column(String(512), nullable=True)

    published_at = Column(DateTime, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    published = Column(Boolean, default=False)

    # AI metadata
    ai_model = Column(String(100), default="gemini-1.5-pro")
    ai_prompt_version = Column(String(20), default="1.0")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    repo = relationship("Repo", back_populates="releases")
    prs = relationship("MergedPR", back_populates="release")


class Subscriber(Base):
    __tablename__ = "subscribers"
    __table_args__ = (
        UniqueConstraint("repo_id", "email", name="uq_repo_email"),
    )

    id = Column(Integer, primary_key=True)
    repo_id = Column(Integer, ForeignKey("repos.id"), nullable=False)
    email = Column(String(255), nullable=False)
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    confirmed = Column(Boolean, default=False)

    repo = relationship("Repo", back_populates="subscribers")
