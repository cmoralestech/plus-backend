"""Generate styled placeholder portrait images for demo profiles."""
import asyncio
import uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from sqlalchemy import select

from app.database import async_session
from app.models.profile import Profile, Photo

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Color palettes per profile (gradient top, gradient bottom)
PALETTES = {
    "James":     [("#1a1a2e", "#16213e"), ("#0f3460", "#16213e")],
    "Michael":   [("#2d3436", "#636e72"), ("#0c2461", "#1e3799")],
    "David":     [("#2c3e50", "#3498db"), ("#1a5276", "#2e86c1")],
    "Alexander": [("#1b2631", "#17202a"), ("#212f3d", "#2c3e50")],
    "Robert":    [("#0d0d0d", "#434343"), ("#1c1c1c", "#383838")],
    "William":   [("#2c3e50", "#4a6fa5"), ("#34495e", "#5d6d7e")],
    "Richard":   [("#2d132c", "#801336"), ("#4a0e4e", "#b12a8c")],
    "Sophia":    [("#a855f7", "#ec4899"), ("#7c3aed", "#db2777")],
    "Emma":      [("#f472b6", "#fb923c"), ("#ec4899", "#f59e0b")],
    "Olivia":    [("#8b5cf6", "#06b6d4"), ("#7c3aed", "#0891b2")],
    "Isabella":  [("#10b981", "#3b82f6"), ("#059669", "#2563eb")],
    "Ava":       [("#f43f5e", "#8b5cf6"), ("#e11d48", "#7c3aed")],
    "Mia":       [("#f59e0b", "#ef4444"), ("#d97706", "#dc2626")],
    "Luna":      [("#8b5cf6", "#ec4899"), ("#6d28d9", "#be185d")],
    "Charlotte": [("#6366f1", "#8b5cf6"), ("#4f46e5", "#7c3aed")],
    "Natalie":   [("#14b8a6", "#3b82f6"), ("#0d9488", "#2563eb")],
}


def create_gradient_portrait(name: str, colors: tuple[str, str], size: int = 600) -> str:
    """Create a gradient portrait with a large initial."""
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)

    # Draw gradient
    top = tuple(int(colors[0].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
    bot = tuple(int(colors[1].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))

    for y in range(size):
        ratio = y / size
        r = int(top[0] + (bot[0] - top[0]) * ratio)
        g = int(top[1] + (bot[1] - top[1]) * ratio)
        b = int(top[2] + (bot[2] - top[2]) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b))

    # Draw initial
    initial = name[0]
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size // 3)
    except (OSError, IOError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initial, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), initial, fill=(255, 255, 255, 180), font=font)

    filename = f"{uuid.uuid4().hex}.jpg"
    filepath = UPLOAD_DIR / filename
    img.save(filepath, "JPEG", quality=85)
    return f"/api/photos/file/{filename}"


async def seed_photos():
    async with async_session() as db:
        for name, palette in PALETTES.items():
            result = await db.execute(
                select(Profile).where(Profile.display_name == name)
            )
            profile = result.scalar_one_or_none()
            if not profile:
                print(f"  Profile '{name}' not found, skipping")
                continue

            # Clear existing photos
            existing = await db.execute(select(Photo).where(Photo.profile_id == profile.id))
            for p in existing.scalars().all():
                await db.delete(p)

            # Create 2 gradient photos per profile
            for i, colors in enumerate(palette):
                url = create_gradient_portrait(name, colors)
                photo = Photo(
                    profile_id=profile.id,
                    url=url,
                    is_primary=(i == 0),
                    order=i,
                )
                db.add(photo)

            print(f"  Created 2 photos for {name}")

        await db.commit()

    print(f"\nDone! Generated photos for {len(PALETTES)} profiles.")


if __name__ == "__main__":
    asyncio.run(seed_photos())
