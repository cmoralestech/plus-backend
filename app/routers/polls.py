"""Anonymous polls — no auth required for max participation."""
import hashlib
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.poll import PollVote

router = APIRouter(prefix="/api/polls", tags=["polls"])


class VoteRequest(BaseModel):
    slug: str
    option: int


def _voter_hash(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    ua = request.headers.get("user-agent", "")
    return hashlib.sha256(f"{ip}:{ua}".encode()).hexdigest()[:32]


@router.post("/vote")
async def vote(data: VoteRequest, request: Request, db: AsyncSession = Depends(get_db)):
    vh = _voter_hash(request)

    # Check if already voted on this poll
    existing = await db.execute(
        select(PollVote).where(PollVote.poll_slug == data.slug, PollVote.voter_hash == vh)
    )
    if existing.scalar_one_or_none():
        return {"already_voted": True}

    vote = PollVote(poll_slug=data.slug, option_index=data.option, voter_hash=vh)
    db.add(vote)
    await db.commit()
    return {"voted": True}


@router.get("/results")
async def get_results(slugs: str, db: AsyncSession = Depends(get_db)):
    """Get vote counts. slugs is comma-separated."""
    slug_list = [s.strip() for s in slugs.split(",") if s.strip()]
    if not slug_list:
        return {}

    result = await db.execute(
        select(PollVote.poll_slug, PollVote.option_index, func.count(PollVote.id))
        .where(PollVote.poll_slug.in_(slug_list))
        .group_by(PollVote.poll_slug, PollVote.option_index)
    )
    rows = result.all()

    results: dict[str, dict[int, int]] = {}
    for slug, opt, count in rows:
        if slug not in results:
            results[slug] = {}
        results[slug][opt] = count

    return results


@router.get("/my-votes")
async def my_votes(slugs: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Check which polls the current visitor already voted on."""
    slug_list = [s.strip() for s in slugs.split(",") if s.strip()]
    if not slug_list:
        return {}

    vh = _voter_hash(request)
    result = await db.execute(
        select(PollVote.poll_slug, PollVote.option_index)
        .where(PollVote.poll_slug.in_(slug_list), PollVote.voter_hash == vh)
    )
    return {slug: opt for slug, opt in result.all()}
