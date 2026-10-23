"""
Unified handling for marking a work as failed and refunding credits.
All generation-failure paths should go through mark_work_failed so refund is never missed.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..models.work import Work, WorkStatus
from ..models.credit_record import CreditRecord, CreditType
from ..models.notification import NotificationType
from ..services.credit_service import add_credits as credit_service_add_credits
from ..utils.notification import create_notification
from ..utils.logger import logger


def mark_work_failed(
    db: Session,
    work: Work,
    error_message: str,
    *,
    refund_description: Optional[str] = None,
) -> None:
    """
    Mark work as failed, set completed_at, and perform idempotent refund.

    Caller is responsible for db.commit() and sending WebSocket if needed.
    Refund is skipped if this work_id already has a REFUND record (idempotent).
    """
    # Serialize failure/refund handling across workers and concurrent callbacks.
    # A database row lock is held until the caller commits the transaction.
    locked_work = db.query(Work).filter(Work.id == work.id).with_for_update().first()
    if locked_work is None:
        logger.error(f"Cannot fail missing work {work.id}")
        return
    if locked_work.status == WorkStatus.SUCCESS:
        logger.info(f"Work {work.id} already succeeded; ignoring late failure")
        return
    work = locked_work
    work.status = WorkStatus.FAILED
    work.error_message = error_message
    work.completed_at = datetime.now(timezone.utc)

    # Idempotent refund: skip if already refunded for this work
    existing = (
        db.query(CreditRecord)
        .filter(
            CreditRecord.work_id == work.id,
            CreditRecord.type == CreditType.REFUND,
        )
        .first()
    )
    if existing:
        logger.info(f"Work {work.id} already has refund record, skipping duplicate refund")
        return

    # Refund the exact amount actually charged (ledger), not today's
    # model price. Pricing may change while a generation is running.
    charges = (
        db.query(CreditRecord)
        .filter(
            CreditRecord.work_id == work.id,
            CreditRecord.type == CreditType.CONSUME,
        )
        .all()
    )
    charged_credits = -sum(int(record.amount) for record in charges if record.amount < 0)
    if charged_credits <= 0:
        logger.info(f"No charged credits to refund for work {work.id}")
        return

    # User-facing description: short and generic (shown in credit history)
    description = refund_description or "Refund: Generation failed"
    credit_service_add_credits(
        db,
        work.user_id,
        charged_credits,
        CreditType.REFUND,
        description,
        work_id=work.id,
    )
    logger.info(f"Refunded {charged_credits} credits for failed work {work.id}: {description}; reason: {error_message}")


def notify_generation_failed(db: Session, user_id: int) -> None:
    """
    Create a TASK_FAILED notification so it appears in the user's Notifications dropdown.
    Call after mark_work_failed + db.commit() so the user sees the failure and can check /billing for the refund.
    """
    create_notification(
        db,
        user_id,
        NotificationType.TASK_FAILED,
        title="Generation failed",
        content="Your generation did not complete. Credits have been refunded to your account. Check Billing for details.",
        link_url="/billing",
    )
