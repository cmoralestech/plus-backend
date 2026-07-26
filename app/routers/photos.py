import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.models.profile import Photo
from app.services.storage import storage, LocalStorage

router = APIRouter(prefix="/api/photos", tags=["photos"])

MAX_PHOTOS = 6
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/", status_code=201)
async def upload_photo(
    file: UploadFile = File(...),
    is_primary: bool = Form(False),
    is_private: bool = Form(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, and WebP images are allowed")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    count_result = await db.execute(
        select(func.count(Photo.id)).where(Photo.profile_id == user.profile.id)
    )
    count = count_result.scalar()
    if count >= MAX_PHOTOS:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_PHOTOS} photos allowed")

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"

    url = await storage.save(contents, filename)

    if is_primary or count == 0:
        await db.execute(
            Photo.__table__.update()
            .where(Photo.profile_id == user.profile.id)
            .values(is_primary=False)
        )
        is_primary = True

    photo = Photo(
        profile_id=user.profile.id,
        url=url,
        is_primary=is_primary,
        is_private=is_private,
        order=count,
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)

    return {
        "id": photo.id,
        "url": photo.url,
        "is_primary": photo.is_primary,
        "is_private": photo.is_private,
        "order": photo.order,
    }


@router.get("/file/{filename}")
async def serve_photo(filename: str):
    """Serve locally-stored photos. Only active when using LocalStorage."""
    if not isinstance(storage, LocalStorage):
        raise HTTPException(status_code=404, detail="Use S3 URLs directly")

    filepath = storage.upload_dir / filename
    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")
    if filepath.resolve().parent != storage.upload_dir.resolve():
        raise HTTPException(status_code=400, detail="Invalid path")
    return FileResponse(filepath)


@router.patch("/{photo_id}/primary")
async def set_primary(
    photo_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.profile_id == user.profile.id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    await db.execute(
        Photo.__table__.update()
        .where(Photo.profile_id == user.profile.id)
        .values(is_primary=False)
    )
    photo.is_primary = True
    await db.commit()
    return {"id": photo.id, "is_primary": True}


@router.delete("/{photo_id}")
async def delete_photo(
    photo_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.profile_id == user.profile.id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    # Delete from storage
    filename = photo.url.split("/")[-1]
    await storage.delete(filename)

    was_primary = photo.is_primary
    await db.delete(photo)
    await db.commit()

    if was_primary:
        next_result = await db.execute(
            select(Photo)
            .where(Photo.profile_id == user.profile.id)
            .order_by(Photo.order)
            .limit(1)
        )
        next_photo = next_result.scalar_one_or_none()
        if next_photo:
            next_photo.is_primary = True
            await db.commit()

    return {"deleted": True}


@router.patch("/{photo_id}/order")
async def reorder_photo(
    photo_id: int,
    new_order: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    result = await db.execute(
        select(Photo).where(Photo.id == photo_id, Photo.profile_id == user.profile.id)
    )
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    photo.order = new_order
    await db.commit()
    return {"id": photo.id, "order": new_order}
