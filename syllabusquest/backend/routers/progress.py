from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from deps import get_current_user

router = APIRouter(prefix="/api/progress", tags=["progress"])

DEFAULT_MAX_LEVEL = 5  # shown for a subject with zero questions uploaded yet, so the map still renders
DEFAULT_DEMO_CAP = 5   # fallback if a subject has no config row yet


def _max_level_for_subject(db: Session, subject: str) -> int:
    """Highest level with at least one question — this is what makes levels
    open-ended: upload through level 12 in the Excel sheet, and students can
    progress all the way to 12 with no code change needed."""
    highest = db.query(func.max(models.Question.level)).filter(models.Question.subject == subject).scalar()
    return highest or DEFAULT_MAX_LEVEL


def _demo_cap_for_subject(db: Session, subject: str) -> int:
    row = db.query(models.Subject).filter(models.Subject.key == subject).first()
    return row.demo_level_cap if row else DEFAULT_DEMO_CAP


def _is_level_accessible(prog: models.Progress, level: int, is_guest: bool) -> bool:
    """Levels 1-5 stay strictly sequential (this is also the guest demo
    range). Once a non-guest student clears level 5, every level beyond it
    opens at once — a "concept tier" the student can tackle in any order,
    rather than one long forced sequence. Guests always stay sequential,
    even if their demo cap happens to extend past 5."""
    if is_guest or level <= 5:
        return level <= prog.unlocked_level
    return prog.unlocked_level >= 6


def _level_labels_for_subject(db: Session, subject: str, max_level: int) -> dict:
    """Concept-tier levels (6+) are labeled by their questions' Topic tag
    instead of a plain number — e.g. {"6": "Newton's Laws"}. Levels 1-5 always
    use their built-in Foundation/Building/... labels regardless of this."""
    if max_level <= 5:
        return {}
    rows = db.query(models.Question.level, models.Question.topic).filter(
        models.Question.subject == subject, models.Question.level > 5, models.Question.topic.isnot(None)
    ).all()
    labels = {}
    for level, topic in rows:
        key = str(level)
        if key not in labels and topic:
            labels[key] = topic
    return labels


def _to_schema(db: Session, p: models.Progress) -> schemas.SubjectProgress:
    max_level = _max_level_for_subject(db, p.subject)
    return schemas.SubjectProgress(
        subject=p.subject, unlocked_level=p.unlocked_level,
        max_level=max_level,
        demo_level_cap=_demo_cap_for_subject(db, p.subject),
        xp=p.xp, stars={str(k): v for k, v in (p.stars or {}).items()},
        enrolled=p.enrolled,
        level_labels=_level_labels_for_subject(db, p.subject, max_level),
    )


@router.get("", response_model=List[schemas.SubjectProgress])
def get_my_progress(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    # Returns every subject the student has a Progress row for (i.e. every
    # subject mapped to their grade) — including ones they aren't enrolled
    # in. The frontend shows those as locked cards with an upgrade/register
    # prompt rather than hiding them, so a student can see what they're
    # missing. Actual access is still enforced separately below and in
    # questions.py regardless of what this endpoint returns.
    rows = db.query(models.Progress).filter(models.Progress.user_id == user.id).all()
    return [_to_schema(db, p) for p in rows]


@router.get("/performance")
def get_performance_dashboard(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Build the student dashboard directly from the Progress table.

    Progress is the source of truth for the student's actual learning state:
    subject, XP, unlocked level and stars per level. Question-bank metadata is
    used only to enrich the hierarchy when it is available.
    """
    from collections import defaultdict

    # IMPORTANT: use the student's Progress rows as the primary dataset.
    # Do not depend on GradeSubject mappings; older/student accounts can have
    # valid progress rows even when a grade mapping was never configured.
    progress_rows = db.query(models.Progress).filter(
        models.Progress.user_id == user.id
    ).order_by(models.Progress.subject).all()

    subject_meta = {
        s.key: s
        for s in db.query(models.Subject).all()
    }

    subjects = []
    overall_points = 0.0
    overall_weight = 0

    for p in progress_rows:
        subj = subject_meta.get(p.subject)
        subject_name = subj.name if subj else p.subject.replace("_", " ").title()
        subject_icon = (subj.icon if subj else None) or "📘"
        stars = {str(k): int(v or 0) for k, v in (p.stars or {}).items()}
        max_level = _max_level_for_subject(db, p.subject)

        # Level rows are the actual performance table represented by Progress.
        # Keep every completed level visible and also include the current
        # unlocked level when it has not been completed yet.
        level_rows = []
        for level in range(1, max_level + 1):
            star_count = max(0, min(3, stars.get(str(level), 0)))
            score = round((star_count / 3.0) * 100) if star_count else 0
            level_rows.append({
                "level": level,
                "stars": star_count,
                "score": score,
                "completed": str(level) in stars and star_count > 0,
            })

        # Only completed levels contribute to the subject score. A newly
        # created subject therefore starts at 0 rather than looking complete.
        completed = [x for x in level_rows if x["completed"]]
        subject_score = round(sum(x["score"] for x in completed) / len(completed)) if completed else 0

        # Enrich with chapter -> topic -> stage if question metadata exists.
        qrows = db.query(models.Question).filter(
            models.Question.subject == p.subject,
            models.Question.status != "draft",
            (models.Question.grade.is_(None) | (models.Question.grade == user.grade)),
        ).all()

        buckets = defaultdict(lambda: {"count": 0, "points": 0.0})
        for q in qrows:
            chapter = q.chapter or "Level performance"
            topic = q.topic or f"Level {q.level}"
            stage = q.stage or "Overall"
            star_count = stars.get(str(q.level), 0)
            key = (chapter, topic, stage)
            buckets[key]["count"] += 1
            buckets[key]["points"] += (star_count / 3.0) * 100.0

        chapter_map = defaultdict(
		lambda: {
            		"count": 0, 
			"points": 0.0,
            		"children": defaultdict(
				lambda: {
                			"count": 0, "points": 0.0,
                			"children": defaultdict(
						lambda: {
							"count": 0, 
							"points": 0.0
							}
								)
            				}
						)
        		}
				)
        for (chapter, topic, stage), b in buckets.items():
            cm = chapter_map[chapter]
            cm["count"] += b["count"]
            cm["points"] += b["points"]
            tm = cm["children"][topic]
            tm["count"] += b["count"]
            tm["points"] += b["points"]
            sm = tm["children"][stage]
            sm["count"] += b["count"]
            sm["points"] += b["points"]

        chapters = []
        for chapter, cm in chapter_map.items():
            topics = []
            for topic, tm in cm["children"].items():
                stages = []
                for stage, sm in tm["children"].items():
                    stages.append({
                        "name": stage,
                        "score": round(sm["points"] / sm["count"]) if sm["count"] else 0,
                        "question_count": sm["count"],
                    })
                topics.append({
                    "name": topic,
                    "score": round(tm["points"] / tm["count"]) if tm["count"] else 0,
                    "question_count": tm["count"],
                    "stages": stages,
                })
            chapters.append({
                "name": chapter,
                "score": round(cm["points"] / cm["count"]) if cm["count"] else 0,
                "question_count": cm["count"],
                "topics": topics,
            })

        # Use the Progress table for dashboard insights.
        strongest_levels = [x for x in sorted(completed, key=lambda r: r["score"], reverse=True) if x["score"] >= 80][:3]
        practice_levels = [x for x in sorted(completed, key=lambda r: r["score"]) if x["score"] < 70][:3]

        subjects.append({
            "key": p.subject,
            "name": subject_name,
            "icon": subject_icon,
            "enrolled": bool(p.enrolled),
            "score": subject_score if p.enrolled else None,
            "xp": p.xp or 0,
            "unlocked_level": p.unlocked_level or 0,
            "max_level": max_level,
            "levels": level_rows,
            "chapters": chapters,
            "what_went_well": [f"Level {x['level']} ({x['score']}%)" for x in strongest_levels],
            "improvement": [f"Level {x['level']} ({x['score']}%)" for x in practice_levels],
            "reflection": (
                f"You have completed {len(completed)} level(s) in {subject_name}."
                if p.enrolled else f"{subject_name} is not enrolled."
            ),
        })

        if p.enrolled and completed:
            overall_points += sum(x["score"] for x in completed)
            overall_weight += len(completed)

    overall = round(overall_points / overall_weight) if overall_weight else 0
    enrolled_subjects = [s for s in subjects if s["enrolled"]]
    mastered = sum(1 for s in enrolled_subjects if (s["score"] or 0) >= 90)
    needs_practice = sum(1 for s in enrolled_subjects if (s["score"] or 0) < 70)

    # A flat performance table is returned as well. The frontend uses this
    # to render the detailed dashboard without needing another API call.
    performance_table = []
    for s in subjects:
        for level in s["levels"]:
            performance_table.append({
                "subject": s["name"],
                "subject_key": s["key"],
                "level": level["level"],
                "stars": level["stars"],
                "score": level["score"],
                "completed": level["completed"],
                "xp": s["xp"],
            })

    return {
        "student": {
            "name": user.name,
            "grade": user.grade,
            "board": user.board,
            "avatar": user.avatar,
        },
        "overall_score": overall,
        "enrolled_subjects": len(enrolled_subjects),
        "mastered_subjects": mastered,
        "needs_practice": needs_practice,
        "subjects": subjects,
        "performance_table": performance_table,
    }

