import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from deps import require_admin

router = APIRouter(prefix="/api", tags=["themes"])

MAX_IMAGE_BYTES = 3 * 1024 * 1024  # 3MB per image — generous for a background/icon, keeps the DB sane
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$")


async def _read_and_validate_image(file: UploadFile, label: str) -> tuple[bytes, str]:
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=f"{label} must be an image file")
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail=f"{label} is too large (max 3MB)")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail=f"{label} is empty")
    return data, file.content_type


# ---------- public: list themes + serve images (no auth — these are just decorative assets, and
# CSS background-image / <img> requests can't attach our JWT Authorization header anyway) ----------
@router.get("/themes", response_model=List[schemas.ThemeOut])
def list_themes(db: Session = Depends(get_db)):
    themes = db.query(models.Theme).order_by(models.Theme.name).all()
    return [
        schemas.ThemeOut(key=t.key, name=t.name, icon_count=len(t.icons))
        for t in themes
    ]


@router.get("/themes/{key}/background")
def get_theme_background(key: str, db: Session = Depends(get_db)):
    theme = db.query(models.Theme).filter(models.Theme.key == key).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    return Response(content=theme.background_image, media_type=theme.background_mime)


@router.get("/themes/{key}/icons/{index}")
def get_theme_icon(key: str, index: int, db: Session = Depends(get_db)):
    theme = db.query(models.Theme).filter(models.Theme.key == key).first()
    if not theme or index < 0 or index >= len(theme.icons):
        raise HTTPException(status_code=404, detail="Icon not found")
    icon = theme.icons[index]
    return Response(content=icon.image, media_type=icon.mime)


# ---------- admin: upload / manage themes ----------
@router.get("/admin/themes", response_model=List[schemas.ThemeOut])
def admin_list_themes(db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    return list_themes(db)


@router.post("/admin/themes", response_model=schemas.ThemeOut, status_code=status.HTTP_201_CREATED)
async def admin_create_theme(
    key: str = Form(...),
    name: str = Form(...),
    background: UploadFile = File(...),
    icons: Optional[List[UploadFile]] = File(default=None),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    key = key.strip().lower()
    if not KEY_PATTERN.match(key):
        raise HTTPException(
            status_code=400,
            detail="Theme key must be 3-32 lowercase letters/numbers/hyphens (e.g. 'race-track')",
        )
    if key == "classic":
        raise HTTPException(status_code=400, detail="'classic' is a built-in theme and can't be overwritten")
    if db.query(models.Theme).filter(models.Theme.key == key).first():
        raise HTTPException(status_code=400, detail=f"A theme with key '{key}' already exists")

    bg_bytes, bg_mime = await _read_and_validate_image(background, "Background image")

    theme = models.Theme(key=key, name=name.strip(), background_image=bg_bytes, background_mime=bg_mime)
    db.add(theme)
    db.flush()  # get theme.id for the icons' FK

    if icons:
        for i, icon_file in enumerate(icons):
            icon_bytes, icon_mime = await _read_and_validate_image(icon_file, f"Icon {i + 1}")
            db.add(models.ThemeIcon(theme_id=theme.id, image=icon_bytes, mime=icon_mime, sort_order=i))

    db.commit()
    db.refresh(theme)
    return schemas.ThemeOut(key=theme.key, name=theme.name, icon_count=len(theme.icons))


@router.post("/admin/themes/{key}/icons", response_model=schemas.ThemeOut)
async def admin_add_icons(
    key: str,
    icons: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Add more icons to an existing theme (appended after whatever's already there)."""
    theme = db.query(models.Theme).filter(models.Theme.key == key).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    next_order = len(theme.icons)
    for i, icon_file in enumerate(icons):
        icon_bytes, icon_mime = await _read_and_validate_image(icon_file, f"Icon {i + 1}")
        db.add(models.ThemeIcon(theme_id=theme.id, image=icon_bytes, mime=icon_mime, sort_order=next_order + i))

    db.commit()
    db.refresh(theme)
    return schemas.ThemeOut(key=theme.key, name=theme.name, icon_count=len(theme.icons))


@router.put("/admin/themes/{key}", response_model=schemas.ThemeOut)
async def admin_update_theme(
    key: str,
    name: Optional[str] = Form(default=None),
    background: Optional[UploadFile] = File(default=None),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(require_admin),
):
    """Rename a theme and/or replace its background image. Icons are managed
    separately (add via POST .../icons, remove via DELETE .../icons/{index})
    so a background swap never disturbs the existing icon set."""
    theme = db.query(models.Theme).filter(models.Theme.key == key).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")

    if name and name.strip():
        theme.name = name.strip()
    if background is not None:
        bg_bytes, bg_mime = await _read_and_validate_image(background, "Background image")
        theme.background_image = bg_bytes
        theme.background_mime = bg_mime

    db.commit()
    db.refresh(theme)
    return schemas.ThemeOut(key=theme.key, name=theme.name, icon_count=len(theme.icons))


@router.delete("/admin/themes/{key}/icons/{index}", response_model=schemas.ThemeOut)
def admin_delete_icon(key: str, index: int, db: Session = Depends(get_db),
                       _admin: models.User = Depends(require_admin)):
    """Remove a single icon by its position. Remaining icons keep their
    relative order and simply shift down — level nodes cycle through
    whatever icons remain, so this never breaks the level map."""
    theme = db.query(models.Theme).filter(models.Theme.key == key).first()
    if not theme or index < 0 or index >= len(theme.icons):
        raise HTTPException(status_code=404, detail="Icon not found")

    db.delete(theme.icons[index])
    db.commit()
    db.refresh(theme)
    return schemas.ThemeOut(key=theme.key, name=theme.name, icon_count=len(theme.icons))


@router.delete("/admin/themes/{key}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_theme(key: str, db: Session = Depends(get_db), _admin: models.User = Depends(require_admin)):
    if key == "classic":
        raise HTTPException(status_code=400, detail="'classic' is a built-in theme and can't be deleted")
    theme = db.query(models.Theme).filter(models.Theme.key == key).first()
    if not theme:
        raise HTTPException(status_code=404, detail="Theme not found")
    db.delete(theme)  # cascades to icons

    # Any student currently using this theme falls back to classic rather than
    # being left pointing at a theme that no longer exists.
    db.query(models.User).filter(models.User.theme == key).update({models.User.theme: "classic"})

    db.commit()
    return None
