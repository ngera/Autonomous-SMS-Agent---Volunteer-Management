# Re-export all models so Alembic can discover them via Base.metadata
from app.models.admin_user import AdminUser
from app.models.announcement import Announcement
from app.models.appointment_type import AppointmentType
from app.models.availability import AvailabilityRule
from app.models.blocked_date import BlockedDate
from app.models.booking import Booking
from app.models.booking_history import BookingHistory
from app.models.contact import Contact
from app.models.contact_consent import ContactConsent, ContactConsentHistory
from app.models.contact_preferred_type import ContactPreferredType
from app.models.conversation import Conversation
from app.models.notification import AdminNotification
from app.models.pattern import CustomerAppointmentPattern
from app.models.recruitment_campaign import (
    RecruitmentCampaign,
    RecruitmentReport,
    RecruitmentSignup,
    RecruitmentWave,
)
from app.models.related_service import RelatedService
from app.models.reminder import Reminder
from app.models.strike import ContactStrike
from app.models.suspension import ContactSuspension
from app.models.system_setting import SystemSetting
from app.models.tenant import Tenant
from app.models.token_usage import TokenUsage

__all__ = [
    "AdminUser",
    "Announcement",
    "AppointmentType",
    "AvailabilityRule",
    "BlockedDate",
    "Booking",
    "BookingHistory",
    "Contact",
    "ContactConsent",
    "ContactConsentHistory",
    "ContactPreferredType",
    "Conversation",
    "AdminNotification",
    "CustomerAppointmentPattern",
    "RecruitmentCampaign",
    "RecruitmentReport",
    "RecruitmentSignup",
    "RecruitmentWave",
    "RelatedService",
    "Reminder",
    "ContactStrike",
    "ContactSuspension",
    "SystemSetting",
    "Tenant",
    "TokenUsage",
]
