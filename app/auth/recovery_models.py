from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    digest: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordRecoveryBudget(Base):
    __tablename__ = "password_recovery_budget"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    requests: Mapped[int] = mapped_column(Integer)
