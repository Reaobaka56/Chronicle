"""Stripe payments and subscription management."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import stripe as stripe_lib

from app.config import get_settings
from app.database import get_db
from app.models import User, PlanTier

router = APIRouter(prefix="/api/billing", tags=["billing"])

settings = get_settings()
stripe_lib.api_key = settings.stripe_secret_key


@router.post("/checkout")
async def create_checkout_session(
    tier: str,  # "pro" or "team"
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout session."""
    # In production, get current user from JWT
    # For MVP, assume user ID 1
    result = await db.execute(select(User).where(User.id == 1))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    price_id = settings.stripe_price_pro if tier == "pro" else settings.stripe_price_team
    if not price_id:
        raise HTTPException(status_code=400, detail="Price not configured")

    # Create Stripe customer if needed
    if not user.stripe_customer_id:
        customer = stripe_lib.Customer.create(
            email=user.email,
            metadata={"github_login": user.github_login, "user_id": user.id},
        )
        user.stripe_customer_id = customer.id
        await db.commit()

    session = stripe_lib.checkout.Session.create(
        customer=user.stripe_customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode="subscription",
        success_url=f"{settings.app_url}/dashboard?success=true",
        cancel_url=f"{settings.app_url}/dashboard?canceled=true",
        metadata={"user_id": user.id, "tier": tier},
    )

    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe_lib.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe_lib.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session["metadata"]["user_id"])
        tier = session["metadata"]["tier"]

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.plan_tier = PlanTier.PRO if tier == "pro" else PlanTier.TEAM
            await db.commit()

    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]

        result = await db.execute(
            select(User).where(User.stripe_customer_id == customer_id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.plan_tier = PlanTier.FREE
            await db.commit()

    return {"status": "ok"}


@router.get("/portal")
async def customer_portal(db: AsyncSession = Depends(get_db)):
    """Redirect to Stripe Customer Portal."""
    result = await db.execute(select(User).where(User.id == 1))
    user = result.scalar_one_or_none()
    if not user or not user.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No subscription found")

    session = stripe_lib.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.app_url}/dashboard",
    )

    return RedirectResponse(session.url)
