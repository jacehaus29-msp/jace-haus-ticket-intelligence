from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class KBCategory(Base):
    __tablename__ = "kb_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    icon = Column(String(50), default="book", nullable=False)
    display_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    articles = relationship("KBArticle", back_populates="category_rel", lazy="select", cascade="all, delete-orphan")

    def to_dict(self, article_count: Optional[int] = None) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description or "",
            "icon": self.icon or "book",
            "display_order": self.display_order,
            "is_active": self.is_active,
            "article_count": article_count if article_count is not None else (len(self.articles) if self.articles else 0),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class KBArticle(Base):
    __tablename__ = "kb_articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False, index=True)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=False)
    
    # Category Foreign Key
    category_id = Column(Integer, ForeignKey("kb_categories.id", ondelete="SET NULL"), nullable=True, index=True)
    category_name = Column(String(100), nullable=True)
    
    # Visibility: 'public' (customer portal & staff) vs 'internal' (MSP staff only)
    visibility = Column(String(20), default="public", nullable=False, index=True)
    
    # Status: 'published', 'draft', 'archived'
    status = Column(String(20), default="published", nullable=False, index=True)
    
    # Author / Editor
    author_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    author_name = Column(String(100), nullable=True)
    
    # Team scoping (Optional link to specialized MSP team)
    team_id = Column(Integer, ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True)
    team_name = Column(String(100), nullable=True)
    
    # Tags (comma-separated search keywords)
    tags = Column(Text, nullable=True)
    
    # Metrics
    view_count = Column(Integer, default=0, nullable=False)
    helpful_count = Column(Integer, default=0, nullable=False)
    not_helpful_count = Column(Integer, default=0, nullable=False)
    current_version = Column(Integer, default=1, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    category_rel = relationship("KBCategory", back_populates="articles", lazy="joined")
    versions = relationship("KBArticleVersion", back_populates="article_rel", lazy="select", cascade="all, delete-orphan", order_by="desc(KBArticleVersion.version_number)")
    feedback = relationship("KBArticleFeedback", back_populates="article_rel", lazy="select", cascade="all, delete-orphan")

    def get_tag_list(self) -> List[str]:
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def to_dict(self, include_content: bool = True) -> Dict[str, Any]:
        total_feedback = self.helpful_count + self.not_helpful_count
        helpfulness_score = (
            round((self.helpful_count / total_feedback) * 100, 1)
            if total_feedback > 0
            else 100.0
        )
        
        data = {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "summary": self.summary or "",
            "category_id": self.category_id,
            "category_name": self.category_name or (self.category_rel.name if self.category_rel else "General"),
            "category_icon": self.category_rel.icon if self.category_rel else "book",
            "visibility": self.visibility,
            "status": self.status,
            "author_id": self.author_id,
            "author_name": self.author_name or "MSP Engineering",
            "team_id": self.team_id,
            "team_name": self.team_name,
            "tags": self.get_tag_list(),
            "view_count": self.view_count,
            "helpful_count": self.helpful_count,
            "not_helpful_count": self.not_helpful_count,
            "helpfulness_score": helpfulness_score,
            "current_version": self.current_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_content:
            data["content"] = self.content
        return data


class KBArticleVersion(Base):
    __tablename__ = "kb_article_versions"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    change_summary = Column(String(255), nullable=True)
    edited_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    edited_by_name = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    article_rel = relationship("KBArticle", back_populates="versions")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "version_number": self.version_number,
            "title": self.title,
            "summary": self.summary or "",
            "content": self.content,
            "change_summary": self.change_summary or "Version update",
            "edited_by_id": self.edited_by_id,
            "edited_by_name": self.edited_by_name or "System",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class KBArticleFeedback(Base):
    __tablename__ = "kb_article_feedback"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("kb_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    is_helpful = Column(Boolean, nullable=False)
    comment = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    article_rel = relationship("KBArticle", back_populates="feedback")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "user_id": self.user_id,
            "customer_id": self.customer_id,
            "is_helpful": self.is_helpful,
            "comment": self.comment,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
