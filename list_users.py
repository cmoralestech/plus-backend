"""List all users in the database."""
import asyncio
import sqlalchemy as sa
from app.database import async_session
from app.models.user import User


async def main():
    async with async_session() as db:
        result = await db.execute(
            sa.select(User.id, User.email, User.user_type, User.created_at)
            .order_by(User.created_at)
        )
        users = result.all()
        print(f"Total users: {len(users)}")
        print()
        for u in users:
            is_demo = "SEED" if "demo" in str(u.email) or "arranged.demo" in str(u.email) else "REAL"
            print(f"{is_demo}  {u.email:<45} {u.user_type:<12} {str(u.created_at)[:19]}")


if __name__ == "__main__":
    asyncio.run(main())
