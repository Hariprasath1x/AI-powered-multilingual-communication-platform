"""Comprehensive and idempotent demo dataset seed script for MassCommAI.

Populates:
- Core system roles (Admin, Campaign Manager, Communication Team).
- Standard demo credentials for all three personas.
- Administrative channel configurations (Email, SMS, WhatsApp, Push, Web).
- Default message templates.
- Diverse citizen demographic audience members (multilingual, multi-state).
- Realistic audience segments.
- Sample campaigns across draft, approved, scheduled, and completed states.
- Multilingual content assets, translations, and demographic variants.
- Dispatched communication messages, delivery logs, tracked links, and click events.
- Recipient feedback records with sentiment analysis scores.

Usage:
    python -m app.db.seed_demo
"""

import logging
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User, Role
from app.models.audience import AudienceMember
from app.models.segment import Segment
from app.models.campaign import Campaign
from app.models.template import Template
from app.models.content_asset import ContentAsset
from app.models.content_variant import ContentVariant
from app.models.channel_config import ChannelConfiguration
from app.models.communication import Message, DeliveryLog, Feedback
from app.models.engagement import TrackedLink, EngagementEvent
from app.core.security import get_password_hash
from app.db.seed import seed_default_roles, seed_default_templates

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("masscommai.seed_demo")

DEMO_USERS = [
    {
        "email": "admin@masscomm.gov.in",
        "password": "Admin@12345",
        "full_name": "Chief Administrator",
        "organization": "Ministry of Communications & Civic Welfare",
        "role_name": "Admin",
    },
    {
        "email": "manager@masscomm.gov.in",
        "password": "Manager@12345",
        "full_name": "Aarav Sharma",
        "organization": "National Disaster Management Authority",
        "role_name": "Campaign Manager",
    },
    {
        "email": "team@masscomm.gov.in",
        "password": "Team@12345",
        "full_name": "Priya Patel",
        "organization": "Public Health Information Bureau",
        "role_name": "Communication Team",
    },
]

DEMO_CHANNELS = [
    {
        "channel": "Email",
        "is_enabled": True,
        "provider_type": "mock",
        "sender_address": "noreply@masscomm.gov.in",
        "sender_name": "Civora Civic Alerts",
        "credentials": {"smtp_host": "smtp.masscomm.gov.in", "smtp_port": 587},
    },
    {
        "channel": "SMS",
        "is_enabled": True,
        "provider_type": "mock",
        "sender_address": "GOVALERT",
        "sender_name": "Government Civic Messaging",
        "credentials": {"dlt_entity_id": "DLT-1100223344", "sender_header": "GOVALT"},
    },
    {
        "channel": "WhatsApp",
        "is_enabled": True,
        "provider_type": "mock",
        "sender_address": "+919876543210",
        "sender_name": "Civora Official Bot",
        "credentials": {"phone_number_id": "wa_demo_pn_1001", "waba_id": "wa_demo_biz_2002"},
    },
    {
        "channel": "Push",
        "is_enabled": True,
        "provider_type": "mock",
        "sender_address": "masscomm-fcm-project",
        "sender_name": "Civic Web Notification Center",
        "credentials": {"fcm_project_id": "civic-fcm-demo"},
    },
    {
        "channel": "Web",
        "is_enabled": True,
        "provider_type": "mock",
        "sender_address": "https://civic.masscomm.gov.in/notices",
        "sender_name": "National Public Notice Portal",
        "credentials": {},
    },
]

DEMO_CITIZENS = [
    {
        "name": "Rajesh Kumar",
        "email": "rajesh.kumar@example.com",
        "phone": "+919811122233",
        "age": 42,
        "gender": "Male",
        "city": "Lucknow",
        "state": "Uttar Pradesh",
        "preferred_language": "hi",
        "occupation": "Farmer",
        "organization_department": "Krishi Vikas Parishad",
        "preferred_channel": "SMS",
        "consent_status": True,
    },
    {
        "name": "Sunita Deshmukh",
        "email": "sunita.deshmukh@example.com",
        "phone": "+919822233344",
        "age": 36,
        "gender": "Female",
        "city": "Pune",
        "state": "Maharashtra",
        "preferred_language": "mr",
        "occupation": "Teacher",
        "organization_department": "Primary Education Board",
        "preferred_channel": "WhatsApp",
        "consent_status": True,
    },
    {
        "name": "Karthik Ramanathan",
        "email": "karthik.raman@example.com",
        "phone": "+919844455566",
        "age": 29,
        "gender": "Male",
        "city": "Chennai",
        "state": "Tamil Nadu",
        "preferred_language": "ta",
        "occupation": "Software Engineer",
        "organization_department": "IT Development Center",
        "preferred_channel": "Email",
        "consent_status": True,
    },
    {
        "name": "Lakshmi Narayana",
        "email": "lakshmi.narayana@example.com",
        "phone": "+919855566677",
        "age": 64,
        "gender": "Male",
        "city": "Hyderabad",
        "state": "Telangana",
        "preferred_language": "te",
        "occupation": "Retired Officer",
        "organization_department": "Postal Department",
        "preferred_channel": "WhatsApp",
        "consent_status": True,
    },
    {
        "name": "Ananya Hegde",
        "email": "ananya.hegde@example.com",
        "phone": "+919866677788",
        "age": 27,
        "gender": "Female",
        "city": "Bengaluru",
        "state": "Karnataka",
        "preferred_language": "kn",
        "occupation": "Doctor",
        "organization_department": "Victoria Hospital",
        "preferred_channel": "Email",
        "consent_status": True,
    },
    {
        "name": "Deepak Verma",
        "email": "deepak.verma@example.com",
        "phone": "+919877788899",
        "age": 51,
        "gender": "Male",
        "city": "New Delhi",
        "state": "Delhi",
        "preferred_language": "en",
        "occupation": "Government Official",
        "organization_department": "Municipal Corporation of Delhi",
        "preferred_channel": "Email",
        "consent_status": True,
    },
    {
        "name": "Meera Sundaram",
        "email": "meera.sundaram@example.com",
        "phone": "+919888899900",
        "age": 68,
        "gender": "Female",
        "city": "Madurai",
        "state": "Tamil Nadu",
        "preferred_language": "ta",
        "occupation": "Homemaker",
        "organization_department": "Senior Citizens Forum",
        "preferred_channel": "SMS",
        "consent_status": True,
    },
    {
        "name": "Ganesh Patil",
        "email": "ganesh.patil@example.com",
        "phone": "+919899900011",
        "age": 48,
        "gender": "Male",
        "city": "Nagpur",
        "state": "Maharashtra",
        "preferred_language": "mr",
        "occupation": "Farmer",
        "organization_department": "Agricultural Produce Market Committee",
        "preferred_channel": "SMS",
        "consent_status": True,
    },
    {
        "name": "Sneha Rao",
        "email": "sneha.rao@example.com",
        "phone": "+919810011223",
        "age": 31,
        "gender": "Female",
        "city": "Mysuru",
        "state": "Karnataka",
        "preferred_language": "kn",
        "occupation": "Nurse",
        "organization_department": "Apollo Clinic",
        "preferred_channel": "WhatsApp",
        "consent_status": True,
    },
    {
        "name": "Vikram Singh",
        "email": "vikram.singh@example.com",
        "phone": "+919820022334",
        "age": 22,
        "gender": "Male",
        "city": "Varanasi",
        "state": "Uttar Pradesh",
        "preferred_language": "hi",
        "occupation": "Student",
        "organization_department": "Banaras Hindu University",
        "preferred_channel": "Push",
        "consent_status": True,
    },
]


def seed_demo_data(db: Session) -> Dict[str, Any]:
    """Populates repeatable and idempotent demo data."""
    from app.db.session import engine
    engine.echo = False
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    summary: Dict[str, int] = {
        "users": 0,
        "channels": 0,
        "templates": 0,
        "citizens": 0,
        "segments": 0,
        "campaigns": 0,
        "content_assets": 0,
        "messages": 0,
        "feedbacks": 0,
        "tracked_links": 0,
        "engagement_events": 0,
    }

    # 1. Seed Roles & Default Templates
    roles = seed_default_roles(db)
    summary["templates"] = len(seed_default_templates(db))

    # 2. Seed Demo Users
    users_by_email: Dict[str, User] = {}
    for u in DEMO_USERS:
        email = u["email"].strip().lower()
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            users_by_email[email] = existing
        else:
            role = roles.get(u["role_name"])
            user = User(
                email=email,
                hashed_password=get_password_hash(u["password"]),
                full_name=u["full_name"],
                organization=u["organization"],
                role_id=role.id,
                is_active=True,
            )
            db.add(user)
            db.flush()
            users_by_email[email] = user
            summary["users"] += 1
            logger.info("Seeded user: %s (%s)", email, u["role_name"])

    admin_user = users_by_email["admin@masscomm.gov.in"]
    manager_user = users_by_email["manager@masscomm.gov.in"]

    # 3. Seed Channel Configurations
    for c in DEMO_CHANNELS:
        ch_name = c["channel"]
        existing = db.execute(select(ChannelConfiguration).where(ChannelConfiguration.channel == ch_name)).scalar_one_or_none()
        if not existing:
            cfg = ChannelConfiguration(
                channel=ch_name,
                is_enabled=c["is_enabled"],
                provider_type=c["provider_type"],
                sender_address=c["sender_address"],
                sender_name=c["sender_name"],
                credentials=c["credentials"],
            )
            db.add(cfg)
            summary["channels"] += 1
            logger.info("Seeded channel config: %s", ch_name)
    db.flush()

    # 4. Seed Audience Members
    citizens: List[AudienceMember] = []
    for cit in DEMO_CITIZENS:
        phone = cit["phone"]
        existing = db.execute(select(AudienceMember).where(AudienceMember.phone == phone)).scalar_one_or_none()
        if existing:
            citizens.append(existing)
        else:
            member = AudienceMember(
                name=cit["name"],
                email=cit["email"],
                phone=cit["phone"],
                age=cit["age"],
                gender=cit["gender"],
                city=cit["city"],
                state=cit["state"],
                preferred_language=cit["preferred_language"],
                occupation=cit["occupation"],
                organization_department=cit["organization_department"],
                preferred_channel=cit["preferred_channel"],
                consent_status=cit["consent_status"],
            )
            db.add(member)
            db.flush()
            citizens.append(member)
            summary["citizens"] += 1
            logger.info("Seeded audience citizen: %s (%s, %s)", cit["name"], cit["city"], cit["preferred_language"])

    # 5. Seed Audience Segments
    demo_segments = [
        {
            "name": "South India Senior Citizens",
            "description": "Senior citizens aged 60+ residing in southern Indian states.",
            "rules": {"age_min": 60, "states": ["Karnataka", "Tamil Nadu", "Telangana"]},
        },
        {
            "name": "Healthcare Workers & Medical Personnel",
            "description": "Physicians, nurses, and medical support staff.",
            "rules": {"occupations": ["Doctor", "Nurse"]},
        },
        {
            "name": "Monsoon Agricultural Alert Recipients",
            "description": "Agrarian workers and farmers needing weather notices.",
            "rules": {"occupations": ["Farmer"], "states": ["Uttar Pradesh", "Maharashtra"]},
        },
    ]

    segments: List[Segment] = []
    for s in demo_segments:
        existing = db.execute(select(Segment).where(Segment.name == s["name"])).scalar_one_or_none()
        if existing:
            segments.append(existing)
        else:
            seg = Segment(
                name=s["name"],
                description=s["description"],
                filter_rules=s["rules"],
                created_by=manager_user.id,
            )
            db.add(seg)
            db.flush()
            segments.append(seg)
            summary["segments"] += 1
            logger.info("Seeded audience segment: %s", s["name"])

    # 6. Seed Sample Campaigns
    now = datetime.now(timezone.utc)
    demo_campaigns = [
        {
            "name": "Monsoon Dengue Awareness & Clean Water Advisory",
            "campaign_type": "Healthcare",
            "objective": "Educate citizens on preventing vector-borne diseases and maintaining clean water storage.",
            "priority": "High",
            "status": "Approved",
            "channels": ["SMS", "WhatsApp", "Email"],
            "start_date": now - timedelta(days=2),
            "end_date": now + timedelta(days=5),
        },
        {
            "name": "Universal Child Immunization & Pulse Polio Drive",
            "campaign_type": "Healthcare",
            "objective": "Notify parents of children under 5 about weekend public health vaccination camps.",
            "priority": "High",
            "status": "Scheduled",
            "channels": ["SMS", "WhatsApp"],
            "start_date": now + timedelta(days=1),
            "end_date": now + timedelta(days=3),
        },
        {
            "name": "Emergency Cyclone & Urban Flood Warning",
            "campaign_type": "Emergency Alert",
            "objective": "Urgent broadcast advising evacuation and emergency helpline availability.",
            "priority": "High",
            "status": "Completed",
            "channels": ["SMS", "WhatsApp", "Push"],
            "start_date": now - timedelta(days=7),
            "end_date": now - timedelta(days=6),
        },
    ]

    campaigns: List[Campaign] = []
    for cmp_data in demo_campaigns:
        existing = db.execute(select(Campaign).where(Campaign.name == cmp_data["name"])).scalar_one_or_none()
        if existing:
            campaigns.append(existing)
        else:
            camp = Campaign(
                name=cmp_data["name"],
                campaign_type=cmp_data["campaign_type"],
                objective=cmp_data["objective"],
                priority=cmp_data["priority"],
                status=cmp_data["status"],
                channels=cmp_data["channels"],
                start_date=cmp_data["start_date"],
                end_date=cmp_data["end_date"],
                created_by=manager_user.id,
            )
            # Associate segments
            camp.segments.extend(segments[:2])
            db.add(camp)
            db.flush()
            campaigns.append(camp)
            summary["campaigns"] += 1
            logger.info("Seeded campaign: %s (%s)", cmp_data["name"], cmp_data["status"])

    # 7. Seed Content Asset & Variants for the primary campaign
    primary_campaign = campaigns[0]
    existing_asset = db.execute(select(ContentAsset).where(ContentAsset.campaign_id == primary_campaign.id)).first()
    if not existing_asset:
        asset = ContentAsset(
            campaign_id=primary_campaign.id,
            title="Dengue Awareness & Monsoon Safety Advisory",
            source_language="en",
            channel="SMS",
            category="Healthcare",
            tone="urgent",
            body="Dear {name}, take immediate steps to prevent Dengue in {city}. Eliminate stagnant water containers and sleep under mosquito nets. Contact local primary health center for persistent fever. Helpline: 1075.",
            summary="Emergency public health guidance on dengue prevention and mosquito protection.",
            call_to_action="Eliminate stagnant water and call 1075 if symptomatic.",
            review_status="Approved",
            created_by=manager_user.id,
        )
        db.add(asset)
        db.flush()
        summary["content_assets"] += 1

        # Add Hindi translation variant
        var_hi = ContentVariant(
            campaign_id=primary_campaign.id,
            source_content_id=asset.id,
            segment_id=segments[0].id if segments else None,
            language="hi",
            channel="SMS",
            variant_title="डेंगू रोकथाम एवं मानसून स्वास्थ्य परामर्श",
            variant_body="प्रिय {name}, डेंगू से बचाव हेतु तत्काल कदम उठाएं। अपने घर के आसपास ठहरा हुआ पानी हटाएं और मच्छरदानी का उपयोग करें। तेज बुखार पर निकटतम प्राथमिक स्वास्थ्य केंद्र जाएं। हेल्पलाइन: 1075।",
            variant_cta="ठहरा हुआ पानी हटाएं और हेल्पलाइन 1075 पर कॉल करें।",
            review_status="Approved",
            created_by=manager_user.id,
        )
        # Add Tamil translation variant
        var_ta = ContentVariant(
            campaign_id=primary_campaign.id,
            source_content_id=asset.id,
            segment_id=segments[0].id if segments else None,
            language="ta",
            channel="SMS",
            variant_title="டெங்கு விழிப்புணர்வு மற்றும் பருவமழை பாதுகாப்பு",
            variant_body="அன்புள்ள {name}, டெங்கு பரவலைத் தடுக்க உடனே நடவடிக்கை எடுக்கவும். தேங்கியுள்ள தண்ணீரை அகற்றி கொசுவலைகளைப் பயன்படுத்தவும். உதவி எண்: 1075.",
            variant_cta="தேங்கிய தண்ணீரை அகற்றுங்கள், உதவிக்கு 1075 அழைக்கவும்.",
            review_status="Approved",
            created_by=manager_user.id,
        )
        db.add_all([var_hi, var_ta])
        db.flush()

    # 8. Seed Dispatched Messages, Links, and Feedback
    # Check if messages already exist for primary campaign
    msg_count = db.execute(select(func.count(Message.id)).where(Message.campaign_id == primary_campaign.id)).scalar() or 0
    if msg_count == 0:
        for i, cit in enumerate(citizens[:6]):
            tracking_id = f"trk_demo_{uuid.uuid4().hex[:12]}"
            feedback_token = f"fbt_demo_{uuid.uuid4().hex[:12]}"
            msg_channel = cit.preferred_channel if cit.preferred_channel in ["SMS", "WhatsApp", "Email"] else "SMS"

            # Message statuses: Delivered, Delivered, Opened, Delivered, Sent, Delivered
            st = "Opened" if i == 2 else ("Sent" if i == 4 else "Delivered")
            sent_time = now - timedelta(hours=24 - (i * 3))
            delivered_time = sent_time + timedelta(seconds=12) if st in ["Delivered", "Opened"] else None
            opened_time = delivered_time + timedelta(minutes=5) if st == "Opened" else None

            msg = Message(
                tracking_id=tracking_id,
                campaign_id=primary_campaign.id,
                audience_member_id=cit.id,
                channel=msg_channel,
                language=cit.preferred_language,
                rendered_content=f"Dear {cit.name}, take immediate steps to prevent Dengue in {cit.city}. Eliminate stagnant water containers. Emergency Helpline: 1075.",
                status=st,
                sent_at=sent_time,
                delivered_at=delivered_time,
                opened_at=opened_time,
                feedback_token=feedback_token,
                created_at=sent_time,
            )
            db.add(msg)
            db.flush()
            summary["messages"] += 1

            # Seed delivery log
            d_log = DeliveryLog(
                message_id=msg.id,
                channel=msg_channel,
                status=st,
                retry_count=0,
                timestamp=delivered_time or sent_time,
            )
            db.add(d_log)

            # Seed tracked link for message
            link_id = f"lnk_{uuid.uuid4().hex[:8]}"
            t_link = TrackedLink(
                link_id=link_id,
                campaign_id=primary_campaign.id,
                message_id=msg.id,
                original_url="https://nhp.gov.in/disease/dengue-fever",
                click_count=1 if st == "Opened" else 0,
                is_active=True,
                created_at=sent_time,
                last_clicked_at=opened_time,
            )
            db.add(t_link)
            summary["tracked_links"] += 1

            if st == "Opened":
                # Add engagement click event
                eng = EngagementEvent(
                    campaign_id=primary_campaign.id,
                    message_id=msg.id,
                    audience_member_id=cit.id,
                    event_type="click",
                    timestamp=opened_time,
                    link_url=t_link.original_url,
                    device_info="Mobile",
                    metadata_json={"user_agent": "Mozilla/5.0 Demo Mobile"},
                )
                db.add(eng)
                summary["engagement_events"] += 1

            # Seed feedback for first 3 citizens
            if i < 3:
                rating = 5 if i == 0 else (4 if i == 1 else 2)
                comment = (
                    "Timely warning! The municipal team also inspected stagnant water."
                    if i == 0
                    else ("Clear instructions and received in regional language." if i == 1 else "Helpline was busy when called.")
                )
                sentiment_lbl = "Positive" if rating >= 4 else "Negative"
                sentiment_scr = 0.85 if rating == 5 else (0.55 if rating == 4 else -0.45)

                fb = Feedback(
                    campaign_id=primary_campaign.id,
                    audience_member_id=cit.id,
                    message_id=msg.id,
                    rating=rating,
                    comment=comment,
                    channel=msg_channel,
                    sentiment_label=sentiment_lbl,
                    sentiment_score=sentiment_scr,
                    language=cit.preferred_language,
                    feedback_token=feedback_token,
                    created_at=now - timedelta(hours=10 - i),
                )
                db.add(fb)
                summary["feedbacks"] += 1

    db.commit()
    return summary


def main() -> None:
    """CLI execution entrypoint."""
    logger.info("Initializing MassCommAI Demo Seeder...")
    session = SessionLocal()
    try:
        summary = seed_demo_data(session)
        logger.info("Demo seeding completed successfully! Seed Summary:")
        for k, v in summary.items():
            logger.info(" - %s: %d newly created", k, v)
        print("\nDemo Data Seed Successful!")
        print("Demo Accounts:")
        print("  Admin:       admin@masscomm.gov.in   / Admin@12345")
        print("  Manager:     manager@masscomm.gov.in / Manager@12345")
        print("  Comm Team:   team@masscomm.gov.in    / Team@12345")
    except Exception as exc:
        session.rollback()
        logger.exception("Demo seeding encountered an error: %s", exc)
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
