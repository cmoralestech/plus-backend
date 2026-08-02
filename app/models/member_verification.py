"""Verification state for a member.

Deliberately stores results, not evidence. Bank statements, brokerage
statements, tax returns and government IDs are handled by the verification
provider; PLUS keeps the minimum outcome needed to render a badge and to know
when to ask again. The pre-existing VerificationRequest model holds an
evidence_url pointing at uploaded documents — that is the pattern this
replaces.

Qualification accepts income OR assets. A founder or investor can hold
substantial assets against a modest conventional salary, and an income-only
rule would exclude exactly the members the product is for.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VerificationMethod(str, enum.Enum):
    INCOME = "income"
    ASSETS = "assets"
    MANUAL = "manual"


class QualificationResult(str, enum.Enum):
    PENDING = "pending"
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"


class MemberVerification(Base):
    __tablename__ = "member_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    # Step 1 — government ID plus liveness, run by the provider.
    identity_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    identity_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Step 2 — qualifying income and/or assets.
    financially_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    financial_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    financial_verification_method: Mapped[VerificationMethod | None] = mapped_column(
        SQLEnum(VerificationMethod, name="verification_method",
                values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    qualification_result: Mapped[QualificationResult] = mapped_column(
        SQLEnum(QualificationResult, name="qualification_result",
                values_callable=lambda e: [m.value for m in e]),
        default=QualificationResult.PENDING,
    )

    # Opaque provider session identifiers. Never a document, URL or amount —
    # they exist only to reconcile a callback with a member.
    identity_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    financial_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Financial standing changes, so verification is not permanent.
    verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    @property
    def is_expired(self) -> bool:
        if not self.verification_expires_at:
            return False
        return datetime.utcnow() > self.verification_expires_at

    @property
    def financially_verified_now(self) -> bool:
        """Verified and still within its validity window."""
        return self.financially_verified and not self.is_expired
