from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, or_, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User, UserType
from app.models.profile import Profile
from app.models.match import Match
from app.models.message import Conversation, Message
from app.models.subscription import Subscription, SubscriptionTier
from app.models.safety import Block
from app.schemas.message import MessageCreate, MessageResponse, ConversationResponse
from app.routers.profiles import profile_to_response
from app.services.content_filter import scan_text
from app.services.audit import log_action

router = APIRouter(prefix="/api/messages", tags=["messages"])

LOCKED_CONTENT = "Upgrade to Premium to read this message"


async def _can_read_messages(user: User, db: AsyncSession) -> bool:
    if user.user_type == UserType.ATTRACTIVE:
        return True
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    if not sub:
        return False
    return sub.tier in (SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND) and sub.is_active


async def _can_send_message(user: User, conversation_id: int, db: AsyncSession) -> tuple[bool, str]:
    if user.user_type == UserType.ATTRACTIVE:
        return True, ""
    result = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    sub = result.scalar_one_or_none()
    is_paid = sub and sub.tier in (SubscriptionTier.PREMIUM, SubscriptionTier.DIAMOND) and sub.is_active
    if is_paid:
        return True, ""
    sent_count_result = await db.execute(
        select(func.count(Message.id)).where(
            Message.conversation_id == conversation_id,
            Message.sender_profile_id == user.profile.id,
        )
    )
    sent_count = sent_count_result.scalar()
    if sent_count >= 1:
        return False, "Free members can send one opening message per conversation. Upgrade to Premium for unlimited messaging."
    return True, ""


def _get_other_pid(conv: Conversation, my_pid: int) -> int | None:
    """Get the other participant's profile ID from a conversation."""
    if conv.match:
        m = conv.match
        return m.profile2_id if m.profile1_id == my_pid else m.profile1_id
    # Direct conversation
    if conv.profile1_id == my_pid:
        return conv.profile2_id
    return conv.profile1_id


def _is_participant(conv: Conversation, pid: int) -> bool:
    """Check if a profile is part of this conversation."""
    if conv.match:
        return pid in (conv.match.profile1_id, conv.match.profile2_id)
    return pid in (conv.profile1_id, conv.profile2_id)


@router.post("/start/{profile_id}", status_code=201)
async def start_conversation(
    profile_id: int,
    data: MessageCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new conversation with any profile (no match required)."""
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")
    if profile_id == user.profile.id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    pid = user.profile.id

    # Check if blocked
    blocked = await db.execute(
        select(Block).where(
            or_(
                and_(Block.blocker_profile_id == pid, Block.blocked_profile_id == profile_id),
                and_(Block.blocker_profile_id == profile_id, Block.blocked_profile_id == pid),
            )
        )
    )
    if blocked.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Cannot message this user")

    # Check if target exists
    target_r = await db.execute(select(Profile).where(Profile.id == profile_id, Profile.is_active == True))
    target_profile = target_r.scalar_one_or_none()
    if not target_profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    # Cross-type only: sugar can only message attractive and vice versa
    target_user_r = await db.execute(select(User).where(User.id == target_profile.user_id))
    target_user = target_user_r.scalar_one_or_none()
    if target_user and target_user.user_type == user.user_type:
        raise HTTPException(status_code=403, detail="You can only message members of the other type")

    # Check if conversation already exists (match-based or direct)
    p1, p2 = min(pid, profile_id), max(pid, profile_id)

    # Check match-based conversation
    match_conv = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.match))
        .join(Match, Conversation.match_id == Match.id)
        .where(Match.profile1_id == p1, Match.profile2_id == p2)
    )
    existing_match_conv = match_conv.scalar_one_or_none()
    if existing_match_conv:
        conv = existing_match_conv
    else:
        # Check direct conversation
        direct_conv = await db.execute(
            select(Conversation).where(
                Conversation.profile1_id == p1, Conversation.profile2_id == p2
            )
        )
        existing_direct = direct_conv.scalar_one_or_none()
        if existing_direct:
            conv = existing_direct
        else:
            # Create new direct conversation
            conv = Conversation(profile1_id=p1, profile2_id=p2)
            db.add(conv)
            await db.flush()

    # Check send permission
    can_send, reason = await _can_send_message(user, conv.id, db)
    if not can_send:
        raise HTTPException(status_code=403, detail=reason)

    # Send the message
    flagged, matched = scan_text(data.content)
    message = Message(
        conversation_id=conv.id,
        sender_profile_id=pid,
        content=data.content,
        is_flagged=flagged,
        flag_reason=matched,
    )
    db.add(message)
    if flagged:
        await log_action(db, actor_type="system", action="flag_message", resource_type="message", details={"matched_term": matched, "sender_profile_id": pid}, request=request)
    conv.updated_at = func.now()
    await db.commit()
    await db.refresh(message)

    # Email notification to recipient
    try:
        from app.services.email import send_new_message
        target_r = await db.execute(select(Profile).where(Profile.id == profile_id))
        target_p = target_r.scalar_one_or_none()
        if target_p:
            target_u_r = await db.execute(select(User).where(User.id == target_p.user_id))
            target_u = target_u_r.scalar_one_or_none()
            if target_u:
                send_new_message(target_u.email, user.profile.display_name)
    except Exception:
        pass

    return {
        "conversation_id": conv.id,
        "message": MessageResponse(
            id=message.id,
            conversation_id=message.conversation_id,
            sender_profile_id=message.sender_profile_id,
            sender_name=user.profile.display_name,
            content=message.content,
            is_read=message.is_read,
            created_at=message.created_at,
        ),
    }


@router.get("/conversations")
async def get_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        return []

    pid = user.profile.id
    can_read = await _can_read_messages(user, db)

    # Get match-based conversations
    match_convos = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.match))
        .join(Match, Conversation.match_id == Match.id)
        .where(or_(Match.profile1_id == pid, Match.profile2_id == pid))
    )

    # Get direct conversations
    direct_convos = await db.execute(
        select(Conversation)
        .where(
            Conversation.match_id == None,
            or_(Conversation.profile1_id == pid, Conversation.profile2_id == pid),
        )
    )

    all_convos = list(match_convos.scalars().all()) + list(direct_convos.scalars().all())
    all_convos.sort(key=lambda c: c.updated_at, reverse=True)

    if not all_convos:
        return []

    # Collect other profile IDs
    other_pids = [_get_other_pid(c, pid) for c in all_convos]

    # Batch load profiles and users
    valid_pids = [p for p in other_pids if p]
    profiles_result = await db.execute(select(Profile).where(Profile.id.in_(valid_pids)))
    profiles_map = {p.id: p for p in profiles_result.scalars().all()}

    user_ids = [p.user_id for p in profiles_map.values()]
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in users_result.scalars().all()}

    # Batch load last messages and unread counts
    conv_ids = [c.id for c in all_convos]

    last_msgs: dict[int, Message] = {}
    for conv_id in conv_ids:
        msg_result = await db.execute(
            select(Message).where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.desc()).limit(1)
        )
        msg = msg_result.scalar_one_or_none()
        if msg:
            last_msgs[conv_id] = msg

    unread_result = await db.execute(
        select(Message.conversation_id, func.count(Message.id))
        .where(Message.conversation_id.in_(conv_ids), Message.sender_profile_id != pid, Message.is_read == False)
        .group_by(Message.conversation_id)
    )
    unreads = dict(unread_result.all())

    responses = []
    for conv, other_pid in zip(all_convos, other_pids):
        if not other_pid:
            continue
        other_profile = profiles_map.get(other_pid)
        if not other_profile:
            continue
        other_user = users_map.get(other_profile.user_id)

        last_msg = last_msgs.get(conv.id)
        last_msg_resp = None
        if last_msg:
            is_from_other = last_msg.sender_profile_id != pid
            show_content = can_read or not is_from_other
            last_msg_resp = MessageResponse(
                id=last_msg.id, conversation_id=last_msg.conversation_id,
                sender_profile_id=last_msg.sender_profile_id,
                content=last_msg.content if show_content else LOCKED_CONTENT,
                is_read=last_msg.is_read, created_at=last_msg.created_at,
                locked=not show_content,
            )

        responses.append(ConversationResponse(
            id=conv.id, match_id=conv.match_id or 0,
            other_profile=profile_to_response(other_profile, other_user),
            last_message=last_msg_resp,
            unread_count=unreads.get(conv.id, 0),
            can_read=can_read,
            created_at=conv.created_at, updated_at=conv.updated_at,
        ))

    return responses


@router.get("/{conversation_id}")
async def get_messages(
    conversation_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    conv = await _get_conversation_for_user(conversation_id, user.profile.id, db)
    can_read = await _can_read_messages(user, db)
    pid = user.profile.id

    if can_read:
        await db.execute(
            update(Message).where(
                Message.conversation_id == conversation_id,
                Message.sender_profile_id != pid, Message.is_read == False,
            ).values(is_read=True)
        )
        await db.commit()

    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )
    messages = result.scalars().all()

    return [
        MessageResponse(
            id=m.id, conversation_id=m.conversation_id,
            sender_profile_id=m.sender_profile_id,
            sender_name=m.sender.display_name if m.sender else None,
            content=m.content if (can_read or m.sender_profile_id == pid) else LOCKED_CONTENT,
            is_read=m.is_read, created_at=m.created_at,
            locked=not (can_read or m.sender_profile_id == pid),
        )
        for m in reversed(messages)
    ]


@router.post("/{conversation_id}", response_model=MessageResponse, status_code=201)
async def send_message(
    conversation_id: int,
    data: MessageCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="Create a profile first")

    conv = await _get_conversation_for_user(conversation_id, user.profile.id, db)
    can_send, reason = await _can_send_message(user, conversation_id, db)
    if not can_send:
        raise HTTPException(status_code=403, detail=reason)

    flagged, matched = scan_text(data.content)
    message = Message(
        conversation_id=conversation_id,
        sender_profile_id=user.profile.id,
        content=data.content,
        is_flagged=flagged,
        flag_reason=matched,
    )
    db.add(message)
    if flagged:
        await log_action(db, actor_type="system", action="flag_message", resource_type="message", details={"matched_term": matched, "sender_profile_id": user.profile.id}, request=request)
    conv.updated_at = func.now()
    await db.commit()
    await db.refresh(message)

    # Send email notification to recipient
    try:
        from app.services.email import send_new_message
        other_pid = _get_other_pid(conv, user.profile.id)
        if other_pid:
            other_profile_r = await db.execute(select(Profile).where(Profile.id == other_pid))
            other_profile = other_profile_r.scalar_one_or_none()
            if other_profile:
                other_user_r = await db.execute(select(User).where(User.id == other_profile.user_id))
                other_user = other_user_r.scalar_one_or_none()
                if other_user:
                    send_new_message(other_user.email, user.profile.display_name)
    except Exception:
        pass

    return MessageResponse(
        id=message.id, conversation_id=message.conversation_id,
        sender_profile_id=message.sender_profile_id,
        sender_name=user.profile.display_name,
        content=message.content, is_read=message.is_read,
        created_at=message.created_at,
    )


async def _get_conversation_for_user(
    conversation_id: int, profile_id: int, db: AsyncSession
) -> Conversation:
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.match))
        .where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if not _is_participant(conv, profile_id):
        raise HTTPException(status_code=403, detail="Not your conversation")

    return conv
