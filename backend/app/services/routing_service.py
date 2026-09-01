from typing import Dict

from sqlalchemy.orm import Session

from app.models.routing_rule import RoutingRule


PRIORITY_WEIGHT = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def route_ticket(ticket: Dict, db: Session) -> Dict:
    """
    Determine the best routing rule for an incoming MSP ticket.

    The engine:
    - Checks all active rules
    - Gives more weight to title matches
    - Gives less weight to description matches
    - Rewards specific keywords
    - Uses priority as a tie-breaker
    - Returns an explanation and confidence score
    """

    title = ticket.get("title", "").lower().strip()
    description = ticket.get("description", "").lower().strip()

    rules = (
        db.query(RoutingRule)
        .filter(RoutingRule.is_active == True)
        .order_by(RoutingRule.id.asc())
        .all()
    )

    candidates = []

    for rule in rules:

        keywords = rule.keywords or []

        title_matches = []
        description_matches = []

        for keyword in keywords:

            keyword = keyword.lower().strip()

            if not keyword:
                continue

            if keyword in title:
                title_matches.append(keyword)

            if keyword in description:
                description_matches.append(keyword)

        if not title_matches and not description_matches:
            continue

        # -----------------------------------------
        # SCORE
        # -----------------------------------------

        title_score = len(title_matches) * 30

        description_score = len(description_matches) * 10

        specificity_score = 0

        all_matches = set(
            title_matches + description_matches
        )

        for keyword in all_matches:
            specificity_score += len(keyword.split()) * 5

        priority_score = PRIORITY_WEIGHT.get(
            rule.priority.lower(),
            0
        )

        total_score = (
            title_score
            + description_score
            + specificity_score
            + priority_score
        )

        candidates.append(
            {
                "rule": rule,
                "title_matches": title_matches,
                "description_matches": description_matches,
                "score": total_score,
            }
        )

    # -----------------------------------------
    # NO MATCH
    # -----------------------------------------

    if not candidates:
        fallback_team = "Service Desk"
        if db is not None:
            try:
                from app.models.team import Team
                sd_team = db.query(Team).filter(Team.name == "Service Desk", Team.is_active == True).first()
                if not sd_team:
                    alt_team = db.query(Team).filter(Team.is_active == True).order_by(Team.id.asc()).first()
                    if alt_team:
                        fallback_team = alt_team.name
            except Exception:
                fallback_team = "Service Desk"

        return {
            "team": fallback_team,
            "priority": "low",
            "category": "General",
            "routing_method": "rule_engine",
            "matched_keywords": [],
            "match_location": "none",
            "confidence": 0,
            "score": 0,
            "rule": "General",
            "reason": "No active routing rule matched the ticket.",
        }

    # -----------------------------------------
    # BEST MATCH
    # -----------------------------------------

    best_match = max(
        candidates,
        key=lambda candidate: candidate["score"]
    )

    rule = best_match["rule"]

    title_matches = best_match["title_matches"]
    description_matches = best_match["description_matches"]

    matched_keywords = list(
        set(title_matches + description_matches)
    )

    # -----------------------------------------
    # MATCH LOCATION
    # -----------------------------------------

    if title_matches and description_matches:
        match_location = "title_and_description"

    elif title_matches:
        match_location = "title"

    else:
        match_location = "description"

    # -----------------------------------------
    # CONFIDENCE
    # -----------------------------------------

    best_score = best_match["score"]

    second_best_score = 0

    for candidate in candidates:

        if candidate is not best_match:
            second_best_score = max(
                second_best_score,
                candidate["score"]
            )

    if second_best_score == 0:
        confidence = 95

    else:
        difference = best_score - second_best_score

        confidence = min(
            95,
            max(
                50,
                50 + difference
            )
        )

    # -----------------------------------------
    # EXPLANATION
    # -----------------------------------------

    if title_matches:
        reason = (
            f"{rule.category} rule matched "
            f"keyword(s) in the ticket title: "
            f"{', '.join(title_matches)}."
        )

    else:
        reason = (
            f"{rule.category} rule matched "
            f"keyword(s) in the ticket description: "
            f"{', '.join(description_matches)}."
        )

    return {
    "team": rule.team,
    "priority": rule.priority,
    "category": rule.category,
    "routing_method": "rule_engine",
    "matched_keywords": matched_keywords,
    "match_location": match_location,
    "confidence": confidence,
    "score": best_score,
    "rule": rule.category,
    "reason": reason,
}