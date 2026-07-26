"""Reseed photos only — replace Unsplash with AI-generated faces from thispersondoesnotexist.com."""
import asyncio
import uuid
import time
import urllib.request
from pathlib import Path
from sqlalchemy import select
from app.database import async_session
from app.models.profile import Profile, Photo
import sqlalchemy

UPLOAD_DIR = Path("/app/uploads") if Path("/app/uploads").exists() else Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def download_ai_face() -> str | None:
    """Download a unique AI-generated face."""
    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = UPLOAD_DIR / filename
    try:
        req = urllib.request.Request(
            "https://thispersondoesnotexist.com",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        )
        data = urllib.request.urlopen(req, timeout=15).read()
        if len(data) < 10000:
            return None
        with open(filepath, "wb") as f:
            f.write(data)
        return f"/api/photos/file/{filename}"
    except Exception as e:
        print(f"  Download failed: {e}")
        return None


async def reseed_photos():
    async with async_session() as db:
        # Delete all existing photos
        await db.execute(sqlalchemy.text("DELETE FROM photos"))
        await db.commit()

        # Get all profiles
        result = await db.execute(select(Profile).order_by(Profile.id))
        profiles = result.scalars().all()
        print(f"Found {len(profiles)} profiles to add photos to")

        success = 0
        for i, profile in enumerate(profiles):
            # Small delay to avoid rate limiting
            if i > 0 and i % 5 == 0:
                time.sleep(1)

            url = download_ai_face()
            if url:
                db.add(Photo(profile_id=profile.id, url=url, is_primary=True, order=0))
                success += 1
                print(f"  [{i+1}/{len(profiles)}] {profile.display_name} ✓")
            else:
                print(f"  [{i+1}/{len(profiles)}] {profile.display_name} ✗")

            # Commit every 10 to avoid losing everything on error
            if (i + 1) % 10 == 0:
                await db.commit()

        await db.commit()
        print(f"\nDone! {success}/{len(profiles)} profiles now have AI-generated photos")


if __name__ == "__main__":
    asyncio.run(reseed_photos())
