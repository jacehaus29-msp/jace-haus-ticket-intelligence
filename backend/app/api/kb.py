import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_

from app.database import get_db
from app.core.auth import (
    get_current_user,
    get_optional_current_user,
    require_admin,
    require_manager_or_admin,
    require_internal
)
from app.models.user import User
from app.models.customer import Customer
from app.models.team import Team
from app.models.kb import (
    KBCategory,
    KBArticle,
    KBArticleVersion,
    KBArticleFeedback
)

router = APIRouter(
    tags=["Knowledge Base & Self-Service Portal"]
)


def slugify(text: str) -> str:
    """Generate a clean URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text or "article"


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = "book"
    display_order: Optional[int] = 0
    is_active: Optional[bool] = True


class CategoryUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class ArticleCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    summary: Optional[str] = None
    content: str = Field(..., min_length=5)
    category_id: Optional[int] = None
    visibility: Optional[str] = Field("public", description="'public' (clients & staff) or 'internal' (staff only)")
    status: Optional[str] = Field("published", description="'published', 'draft', or 'archived'")
    team_id: Optional[int] = None
    tags: Optional[str] = Field(None, description="Comma-separated keywords")
    change_summary: Optional[str] = "Initial publication"


class ArticleUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    summary: Optional[str] = None
    content: Optional[str] = Field(None, min_length=5)
    category_id: Optional[int] = None
    visibility: Optional[str] = None
    status: Optional[str] = None
    team_id: Optional[int] = None
    tags: Optional[str] = None
    change_summary: Optional[str] = "Updated content"


class ArticleFeedbackRequest(BaseModel):
    is_helpful: bool
    comment: Optional[str] = None
    session_id: Optional[str] = None


# =============================================================================
# 1. CUSTOMER PORTAL / PUBLIC KB ENDPOINTS (Strict Public Scoping)
# =============================================================================

@router.get("/portal/kb/categories")
def get_portal_categories(
    db: Session = Depends(get_db)
):
    """
    List all active categories with count of published, public articles.
    """
    categories = db.query(KBCategory).filter(
        KBCategory.is_active == True
    ).order_by(KBCategory.display_order.asc(), KBCategory.name.asc()).all()

    result = []
    for cat in categories:
        count = db.query(KBArticle).filter(
            KBArticle.category_id == cat.id,
            KBArticle.visibility == "public",
            KBArticle.status == "published"
        ).count()
        # Include category even if 0 articles
        result.append(cat.to_dict(article_count=count))

    return {
        "count": len(result),
        "categories": result
    }


@router.get("/portal/kb/articles")
def list_portal_articles(
    query: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    category_slug: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    sort: str = Query("relevance"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Search and filter public, published articles for customer self-service.
    Strictly excludes internal and draft articles.
    """
    db_query = db.query(KBArticle).filter(
        KBArticle.visibility == "public",
        KBArticle.status == "published"
    )

    if category_id:
        db_query = db_query.filter(KBArticle.category_id == category_id)
    elif category_slug:
        cat = db.query(KBCategory).filter(KBCategory.slug == category_slug).first()
        if cat:
            db_query = db_query.filter(KBArticle.category_id == cat.id)
        else:
            return {"count": 0, "articles": []}

    if tag:
        tag_clean = tag.strip().lower()
        db_query = db_query.filter(func.lower(KBArticle.tags).contains(tag_clean))

    articles = db_query.all()

    if query and query.strip():
        q_terms = [t.strip().lower() for t in query.strip().split() if len(t.strip()) > 1]
        scored_articles = []
        for art in articles:
            score = 0
            title_lower = art.title.lower()
            summary_lower = (art.summary or "").lower()
            content_lower = art.content.lower()
            tags_lower = (art.tags or "").lower()

            for term in q_terms:
                if term in title_lower:
                    score += 15
                if term in tags_lower:
                    score += 10
                if term in summary_lower:
                    score += 5
                if term in content_lower:
                    score += 2

            if score > 0:
                scored_articles.append((score, art))

        scored_articles.sort(key=lambda x: (x[0], x[1].helpful_count, x[1].view_count), reverse=True)
        articles = [a[1] for a in scored_articles[:limit]]
    else:
        if sort == "views":
            articles.sort(key=lambda x: x.view_count, reverse=True)
        elif sort == "helpful":
            articles.sort(key=lambda x: x.helpful_count, reverse=True)
        else:
            articles.sort(key=lambda x: (x.updated_at.timestamp() if x.updated_at else (x.created_at.timestamp() if x.created_at else 0.0)), reverse=True)
        articles = articles[:limit]

    return {
        "count": len(articles),
        "articles": [a.to_dict(include_content=False) for a in articles]
    }


@router.get("/portal/kb/articles/{id_or_slug}")
def get_portal_article_detail(
    id_or_slug: str,
    db: Session = Depends(get_db)
):
    """
    Get full public article content for customer portal reading.
    Increments view_count. Strictly blocks internal/draft articles.
    """
    article = None
    if id_or_slug.isdigit():
        article = db.query(KBArticle).filter(KBArticle.id == int(id_or_slug)).first()
    if not article:
        article = db.query(KBArticle).filter(KBArticle.slug == id_or_slug).first()

    if not article:
        raise HTTPException(status_code=404, detail="Knowledge base article not found.")

    # Strict Tenant/Visibility Security Boundary
    if article.visibility != "public" or article.status != "published":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: This article is restricted to internal MSP engineering staff."
        )

    # Increment view count
    article.view_count += 1
    db.commit()
    db.refresh(article)

    return {
        "article": article.to_dict(include_content=True)
    }


@router.post("/portal/kb/articles/{article_id}/feedback")
def submit_article_feedback(
    article_id: int,
    payload: ArticleFeedbackRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit customer/user feedback (thumbs up / thumbs down) for an article.
    """
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")

    # Update article counts
    if payload.is_helpful:
        article.helpful_count += 1
    else:
        article.not_helpful_count += 1

    feedback = KBArticleFeedback(
        article_id=article.id,
        user_id=current_user.id if current_user else None,
        customer_id=current_user.customer_id if (current_user and current_user.customer_id) else None,
        is_helpful=payload.is_helpful,
        comment=payload.comment.strip() if payload.comment and payload.comment.strip() else None,
        session_id=payload.session_id
    )
    db.add(feedback)
    db.commit()
    db.refresh(article)

    return {
        "message": "Thank you for your feedback!",
        "helpful_count": article.helpful_count,
        "not_helpful_count": article.not_helpful_count
    }


@router.get("/portal/kb/suggest")
def suggest_portal_articles(
    q: str = Query(..., min_length=2),
    category: Optional[str] = Query(None),
    limit: int = Query(4, ge=1, le=10),
    db: Session = Depends(get_db)
):
    """
    Live ticket deflection endpoint: Suggest relevant public articles
    as customer types their ticket subject/description.
    """
    q_terms = [t.strip().lower() for t in q.strip().split() if len(t.strip()) > 1]
    if not q_terms:
        return {"suggestions": []}

    articles = db.query(KBArticle).filter(
        KBArticle.visibility == "public",
        KBArticle.status == "published"
    ).all()

    scored = []
    for art in articles:
        score = 0
        t_low = art.title.lower()
        tag_low = (art.tags or "").lower()
        sum_low = (art.summary or "").lower()

        for term in q_terms:
            if term in t_low:
                score += 15
            if term in tag_low:
                score += 10
            if term in sum_low:
                score += 5

        # Boost matching category if specified
        if category and art.category_name and category.lower() in art.category_name.lower():
            score += 8

        if score > 0:
            scored.append((score, art))

    scored.sort(key=lambda x: (x[0], x[1].helpful_count), reverse=True)
    top_matches = [s[1] for s in scored[:limit]]

    return {
        "query": q,
        "count": len(top_matches),
        "suggestions": [
            {
                "id": a.id,
                "title": a.title,
                "slug": a.slug,
                "summary": a.summary or "",
                "category_name": a.category_name or "General",
                "category_icon": a.category_rel.icon if a.category_rel else "book",
                "helpfulness_score": a.to_dict(include_content=False)["helpfulness_score"]
            }
            for a in top_matches
        ]
    }


# =============================================================================
# 2. INTERNAL MSP KNOWLEDGE BASE ENDPOINTS (Staff / Manager / Admin)
# =============================================================================

@router.get("/kb/categories")
def list_internal_categories(
    current_user: User = Depends(require_internal),
    db: Session = Depends(get_db)
):
    """
    List all knowledge base categories for internal staff.
    """
    categories = db.query(KBCategory).order_by(
        KBCategory.display_order.asc(),
        KBCategory.name.asc()
    ).all()

    result = []
    for cat in categories:
        count = db.query(KBArticle).filter(KBArticle.category_id == cat.id).count()
        result.append(cat.to_dict(article_count=count))

    return {
        "count": len(result),
        "categories": result
    }


@router.post("/kb/categories")
def create_category(
    payload: CategoryCreateRequest,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new knowledge base category (Manager / Admin).
    """
    clean_name = payload.name.strip()
    clean_slug = slugify(clean_name)

    existing = db.query(KBCategory).filter(
        or_(
            func.lower(KBCategory.name) == clean_name.lower(),
            KBCategory.slug == clean_slug
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{clean_name}' already exists."
        )

    cat = KBCategory(
        name=clean_name,
        slug=clean_slug,
        description=payload.description.strip() if payload.description else None,
        icon=payload.icon or "book",
        display_order=payload.display_order or 0,
        is_active=payload.is_active if payload.is_active is not None else True
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)

    return {
        "message": "Category created successfully",
        "category": cat.to_dict(article_count=0)
    }


@router.put("/kb/categories/{category_id}")
def update_category(
    category_id: int,
    payload: CategoryUpdateRequest,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """
    Update a knowledge base category (Manager / Admin).
    """
    cat = db.query(KBCategory).filter(KBCategory.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")

    if payload.name:
        clean_name = payload.name.strip()
        clean_slug = slugify(clean_name)
        existing = db.query(KBCategory).filter(
            KBCategory.id != category_id,
            or_(
                func.lower(KBCategory.name) == clean_name.lower(),
                KBCategory.slug == clean_slug
            )
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Category name '{clean_name}' is already in use.")
        cat.name = clean_name
        cat.slug = clean_slug

    if payload.description is not None:
        cat.description = payload.description.strip()
    if payload.icon is not None:
        cat.icon = payload.icon
    if payload.display_order is not None:
        cat.display_order = payload.display_order
    if payload.is_active is not None:
        cat.is_active = payload.is_active

    db.commit()
    db.refresh(cat)

    return {
        "message": "Category updated successfully",
        "category": cat.to_dict()
    }


@router.delete("/kb/categories/{category_id}")
def delete_category(
    category_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete a knowledge base category (Admin only).
    """
    cat = db.query(KBCategory).filter(KBCategory.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found.")

    db.delete(cat)
    db.commit()

    return {
        "message": f"Category '{cat.name}' deleted successfully."
    }


@router.get("/kb/articles")
def list_internal_articles(
    query: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    visibility: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    team_id: Optional[int] = Query(None),
    sort: str = Query("recent"),
    limit: int = Query(100, ge=1, le=200),
    current_user: User = Depends(require_internal),
    db: Session = Depends(get_db)
):
    """
    List all internal & public knowledge base articles for staff.
    """
    db_query = db.query(KBArticle)

    if category_id:
        db_query = db_query.filter(KBArticle.category_id == category_id)
    if visibility:
        db_query = db_query.filter(KBArticle.visibility == visibility)
    if status_filter:
        db_query = db_query.filter(KBArticle.status == status_filter)
    if team_id:
        db_query = db_query.filter(KBArticle.team_id == team_id)

    articles = db_query.all()

    if query and query.strip():
        q_terms = [t.strip().lower() for t in query.strip().split() if len(t.strip()) > 1]
        scored_articles = []
        for art in articles:
            score = 0
            t_low = art.title.lower()
            tag_low = (art.tags or "").lower()
            sum_low = (art.summary or "").lower()
            cnt_low = art.content.lower()

            for term in q_terms:
                if term in t_low:
                    score += 15
                if term in tag_low:
                    score += 10
                if term in sum_low:
                    score += 5
                if term in cnt_low:
                    score += 2

            if score > 0:
                scored_articles.append((score, art))

        scored_articles.sort(key=lambda x: (x[0], x[1].view_count), reverse=True)
        articles = [a[1] for a in scored_articles[:limit]]
    else:
        if sort == "views":
            articles.sort(key=lambda x: x.view_count, reverse=True)
        elif sort == "helpful":
            articles.sort(key=lambda x: x.helpful_count, reverse=True)
        else:
            articles.sort(key=lambda x: (x.updated_at.timestamp() if x.updated_at else (x.created_at.timestamp() if x.created_at else 0.0)), reverse=True)
        articles = articles[:limit]

    return {
        "count": len(articles),
        "articles": [a.to_dict(include_content=False) for a in articles]
    }


@router.get("/kb/articles/{article_id}")
def get_internal_article_detail(
    article_id: int,
    current_user: User = Depends(require_internal),
    db: Session = Depends(get_db)
):
    """
    Get full internal article details, metadata, and tags.
    """
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")

    return {
        "article": article.to_dict(include_content=True)
    }


@router.post("/kb/articles")
def create_article(
    payload: ArticleCreateRequest,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new KB article and record Version 1 (Manager / Admin).
    """
    clean_title = payload.title.strip()
    base_slug = slugify(clean_title)
    
    # Ensure unique slug
    slug = base_slug
    idx = 1
    while db.query(KBArticle).filter(KBArticle.slug == slug).first():
        slug = f"{base_slug}-{idx}"
        idx += 1

    cat_name = None
    if payload.category_id:
        cat = db.query(KBCategory).filter(KBCategory.id == payload.category_id).first()
        if cat:
            cat_name = cat.name

    team_name = None
    if payload.team_id:
        team = db.query(Team).filter(Team.id == payload.team_id).first()
        if team:
            team_name = team.name

    article = KBArticle(
        title=clean_title,
        slug=slug,
        summary=payload.summary.strip() if payload.summary else None,
        content=payload.content.strip(),
        category_id=payload.category_id,
        category_name=cat_name,
        visibility=payload.visibility if payload.visibility in ["public", "internal"] else "public",
        status=payload.status if payload.status in ["published", "draft", "archived"] else "published",
        author_id=current_user.id,
        author_name=current_user.name,
        team_id=payload.team_id,
        team_name=team_name,
        tags=payload.tags.strip() if payload.tags else None,
        current_version=1
    )
    db.add(article)
    db.commit()
    db.refresh(article)

    # Record Version 1 in Audit Trail
    version1 = KBArticleVersion(
        article_id=article.id,
        version_number=1,
        title=article.title,
        content=article.content,
        summary=article.summary,
        change_summary=payload.change_summary or "Initial publication",
        edited_by_id=current_user.id,
        edited_by_name=current_user.name
    )
    db.add(version1)
    db.commit()

    return {
        "message": "Article created successfully",
        "article": article.to_dict(include_content=True)
    }


@router.put("/kb/articles/{article_id}")
def update_article(
    article_id: int,
    payload: ArticleUpdateRequest,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """
    Update KB article and record new audit version (Manager / Admin).
    """
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")

    has_content_changed = False

    if payload.title and payload.title.strip() != article.title:
        article.title = payload.title.strip()
        has_content_changed = True

    if payload.summary is not None and payload.summary.strip() != (article.summary or ""):
        article.summary = payload.summary.strip()
        has_content_changed = True

    if payload.content and payload.content.strip() != article.content:
        article.content = payload.content.strip()
        has_content_changed = True

    if payload.category_id is not None and payload.category_id != article.category_id:
        article.category_id = payload.category_id
        cat = db.query(KBCategory).filter(KBCategory.id == payload.category_id).first()
        article.category_name = cat.name if cat else None

    if payload.visibility and payload.visibility in ["public", "internal"]:
        article.visibility = payload.visibility

    if payload.status and payload.status in ["published", "draft", "archived"]:
        article.status = payload.status

    if payload.team_id is not None:
        article.team_id = payload.team_id
        team = db.query(Team).filter(Team.id == payload.team_id).first()
        article.team_name = team.name if team else None

    if payload.tags is not None:
        article.tags = payload.tags.strip() if payload.tags else None

    article.updated_at = datetime.now(timezone.utc)

    if has_content_changed:
        article.current_version += 1
        new_ver = KBArticleVersion(
            article_id=article.id,
            version_number=article.current_version,
            title=article.title,
            content=article.content,
            summary=article.summary,
            change_summary=payload.change_summary or f"Updated to version {article.current_version}",
            edited_by_id=current_user.id,
            edited_by_name=current_user.name
        )
        db.add(new_ver)

    db.commit()
    db.refresh(article)

    return {
        "message": "Article updated successfully",
        "article": article.to_dict(include_content=True)
    }


@router.delete("/kb/articles/{article_id}")
def delete_article(
    article_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Permanently delete KB article (Admin only).
    """
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")

    db.delete(article)
    db.commit()

    return {
        "message": f"Article '{article.title}' deleted successfully."
    }


@router.get("/kb/articles/{article_id}/versions")
def get_article_versions(
    article_id: int,
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """
    Get complete audit revision history for an article.
    """
    article = db.query(KBArticle).filter(KBArticle.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found.")

    versions = db.query(KBArticleVersion).filter(
        KBArticleVersion.article_id == article_id
    ).order_by(KBArticleVersion.version_number.desc()).all()

    return {
        "article_id": article.id,
        "article_title": article.title,
        "current_version": article.current_version,
        "count": len(versions),
        "versions": [v.to_dict() for v in versions]
    }


# =============================================================================
# 3. KNOWLEDGE BASE ANALYTICS & REPORTING
# =============================================================================

@router.get("/kb/analytics")
def get_kb_analytics(
    category_id: Optional[int] = Query(None),
    current_user: User = Depends(require_manager_or_admin),
    db: Session = Depends(get_db)
):
    """
    Comprehensive Knowledge Base operational analytics, view counts,
    satisfaction %, top articles, and flagged low-performing guides.
    """
    query = db.query(KBArticle)
    if category_id:
        query = query.filter(KBArticle.category_id == category_id)

    articles = query.all()

    total_articles = len(articles)
    public_count = sum(1 for a in articles if a.visibility == "public" and a.status == "published")
    internal_count = sum(1 for a in articles if a.visibility == "internal" and a.status == "published")
    draft_count = sum(1 for a in articles if a.status == "draft")
    archived_count = sum(1 for a in articles if a.status == "archived")

    total_views = sum(a.view_count for a in articles)
    total_helpful = sum(a.helpful_count for a in articles)
    total_not_helpful = sum(a.not_helpful_count for a in articles)
    total_feedback = total_helpful + total_not_helpful

    overall_helpfulness = (
        round((total_helpful / total_feedback) * 100, 1)
        if total_feedback > 0
        else 100.0
    )

    # Top Viewed Articles
    top_viewed = sorted(articles, key=lambda a: a.view_count, reverse=True)[:5]
    top_helpful = sorted(articles, key=lambda a: a.helpful_count, reverse=True)[:5]

    # Flagged Articles (low helpfulness or > 2 unhelpful votes)
    flagged = []
    for a in articles:
        tot = a.helpful_count + a.not_helpful_count
        if tot >= 3:
            score = round((a.helpful_count / tot) * 100, 1)
            if score < 75.0 or a.not_helpful_count >= 3:
                flagged.append({
                    "id": a.id,
                    "title": a.title,
                    "category_name": a.category_name,
                    "visibility": a.visibility,
                    "helpful_count": a.helpful_count,
                    "not_helpful_count": a.not_helpful_count,
                    "helpfulness_score": score
                })

    return {
        "total_articles": total_articles,
        "public_articles": public_count,
        "internal_articles": internal_count,
        "draft_articles": draft_count,
        "archived_articles": archived_count,
        "total_views": total_views,
        "total_helpful": total_helpful,
        "total_not_helpful": total_not_helpful,
        "total_feedback": total_feedback,
        "overall_helpfulness_percentage": overall_helpfulness,
        "estimated_deflections": int(total_helpful * 0.85),
        "top_viewed_articles": [
            {"id": a.id, "title": a.title, "views": a.view_count, "category": a.category_name, "visibility": a.visibility}
            for a in top_viewed
        ],
        "top_helpful_articles": [
            {"id": a.id, "title": a.title, "helpful": a.helpful_count, "category": a.category_name, "visibility": a.visibility}
            for a in top_helpful
        ],
        "articles_needing_review": flagged
    }
