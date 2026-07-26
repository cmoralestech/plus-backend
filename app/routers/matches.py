import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserType
from app.models.profile import Profile
from app.models.match import Like, Match
from app.models.message import Conversation, Message
from app.schemas.match import LikeCreate, MatchResponse
from app.routers.profiles import profile_to_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matches", tags=["matches"])


@router.post("/like", status_code=status.HTTP_201_CREATED)
async def like_profile(
    data: LikeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    if data.profile_id == user.profile.id:
        raise HTTPException(status_code=400, detail="Cannot like yourself")

    # Check if target profile exists
    target_r = await db.execute(select(Profile).where(Profile.id == data.profile_id))
    target_profile = target_r.scalar_one_or_none()
    if not target_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Cross-type only: sugar can only like attractive and vice versa
    target_user_r = await db.execute(select(User).where(User.id == target_profile.user_id))
    target_user = target_user_r.scalar_one_or_none()
    if target_user and target_user.user_type == user.user_type:
        raise HTTPException(status_code=403, detail="You can only like members of the other type")

    # Likes are unlimited for all users — they serve as saves/bookmarks
    # and enable mutual matching. No rate limiting.

    # Check if already liked
    existing = await db.execute(
        select(Like).where(
            Like.from_profile_id == user.profile.id,
            Like.to_profile_id == data.profile_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already liked")

    like = Like(from_profile_id=user.profile.id, to_profile_id=data.profile_id)
    db.add(like)

    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Already liked")

    # Send "someone liked you" email to the target
    try:
        from app.services.email import send_someone_liked_you
        target_profile_r = await db.execute(select(Profile).where(Profile.id == data.profile_id))
        target_profile = target_profile_r.scalar_one_or_none()
        if target_profile:
            target_user_r = await db.execute(select(User).where(User.id == target_profile.user_id))
            target_user = target_user_r.scalar_one_or_none()
            if target_user:
                send_someone_liked_you(
                    to=target_user.email,
                    liker_name=user.profile.display_name,
                    liker_city=user.profile.city or "",
                )
    except Exception:
        pass

    # Check for mutual like -> create match
    mutual = await db.execute(
        select(Like).where(
            Like.from_profile_id == data.profile_id,
            Like.to_profile_id == user.profile.id,
        )
    )
    is_match = False
    if mutual.scalar_one_or_none():
        p1 = min(user.profile.id, data.profile_id)
        p2 = max(user.profile.id, data.profile_id)

        # Check if match already exists (race condition guard)
        existing_match = await db.execute(
            select(Match).where(Match.profile1_id == p1, Match.profile2_id == p2)
        )
        if not existing_match.scalar_one_or_none():
            try:
                match = Match(profile1_id=p1, profile2_id=p2)
                db.add(match)
                await db.flush()
                conversation = Conversation(match_id=match.id, profile1_id=p1, profile2_id=p2)
                db.add(conversation)
                is_match = True

                # Send match notification emails
                try:
                    from app.services.email import send_new_match
                    other_pid = data.profile_id
                    other_profile_r = await db.execute(select(Profile).where(Profile.id == other_pid))
                    other_profile = other_profile_r.scalar_one_or_none()
                    other_user_r = await db.execute(select(User).where(User.id == other_profile.user_id))
                    other_user = other_user_r.scalar_one_or_none()
                    if other_user:
                        send_new_match(other_user.email, user.profile.display_name)
                except Exception:
                    pass  # Don't fail the match on email error
            except IntegrityError:
                # Another request already created the match — that's fine
                await db.rollback()
                is_match = True
        else:
            is_match = True

    await db.commit()
    return {"liked": True, "is_match": is_match}


@router.delete("/like/{profile_id}", status_code=status.HTTP_200_OK)
async def unlike_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    result = await db.execute(
        select(Like).where(
            Like.from_profile_id == user.profile.id,
            Like.to_profile_id == profile_id,
        )
    )
    like = result.scalar_one_or_none()
    if not like:
        raise HTTPException(status_code=404, detail="Like not found")

    await db.delete(like)
    await db.commit()
    return {"unliked": True}


@router.get("/", response_model=list[MatchResponse])
async def get_matches(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        return []

    pid = user.profile.id

    # Single query: get all matches with profiles and users eagerly loaded
    result = await db.execute(
        select(Match)
        .where(
            Match.is_active == True,
            or_(Match.profile1_id == pid, Match.profile2_id == pid),
        )
        .order_by(Match.created_at.desc())
    )
    matches = result.scalars().all()

    if not matches:
        return []

    # Batch load all other profile IDs
    other_pids = [
        m.profile2_id if m.profile1_id == pid else m.profile1_id
        for m in matches
    ]

    # Single query for all profiles
    profiles_result = await db.execute(
        select(Profile).where(Profile.id.in_(other_pids))
    )
    profiles_map = {p.id: p for p in profiles_result.scalars().all()}

    # Single query for all users
    user_ids = [p.user_id for p in profiles_map.values()]
    users_result = await db.execute(
        select(User).where(User.id.in_(user_ids))
    )
    users_map = {u.id: u for u in users_result.scalars().all()}

    # Single query for last messages per conversation
    conv_ids = [m.conversation.id for m in matches if m.conversation]
    last_msgs: dict[int, str] = {}
    unreads: dict[int, int] = {}

    if conv_ids:
        # Last message per conversation using lateral join equivalent
        from sqlalchemy import literal_column
        for conv_id in conv_ids:
            msg_result = await db.execute(
                select(Message.content)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.created_at.desc())
                .limit(1)
            )
            row = msg_result.scalar_one_or_none()
            if row:
                last_msgs[conv_id] = row

        # Unread counts in single query
        from sqlalchemy import case
        unread_result = await db.execute(
            select(
                Message.conversation_id,
                func.count(Message.id),
            )
            .where(
                Message.conversation_id.in_(conv_ids),
                Message.sender_profile_id != pid,
                Message.is_read == False,
            )
            .group_by(Message.conversation_id)
        )
        unreads = dict(unread_result.all())

    responses = []
    for match in matches:
        other_pid = match.profile2_id if match.profile1_id == pid else match.profile1_id
        other_profile = profiles_map.get(other_pid)
        if not other_profile:
            continue
        other_user = users_map.get(other_profile.user_id)

        conv_id = match.conversation.id if match.conversation else None

        responses.append(MatchResponse(
            id=match.id,
            profile=profile_to_response(other_profile, other_user),
            created_at=match.created_at,
            has_conversation=match.conversation is not None,
            last_message=last_msgs.get(conv_id) if conv_id else None,
            unread_count=unreads.get(conv_id, 0) if conv_id else 0,
        ))

    return responses
