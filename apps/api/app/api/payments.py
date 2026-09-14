import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.deps import CurrentSession
from app.models import Member, Payment

router = APIRouter(tags=["payments"])


class PaymentOut(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    member_name: str
    member_name_en: str
    amount_usd: float
    at: datetime
    method: str


@router.get("/payments", response_model=list[PaymentOut])
async def list_payments(session: CurrentSession) -> list[PaymentOut]:
    result = await session.execute(
        select(Payment, Member)
        .join(Member, Member.id == Payment.member_id)
        .order_by(Payment.at.desc())
    )
    return [
        PaymentOut(
            id=payment.id, member_id=member.id, member_name=member.name,
            member_name_en=member.name_en, amount_usd=payment.amount_usd,
            at=payment.at, method=payment.method,
        )
        for payment, member in result.all()
    ]
