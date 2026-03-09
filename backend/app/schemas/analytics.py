from pydantic import BaseModel


class BookingVolumePoint(BaseModel):
    period: str
    count: int
    appointment_type: str | None = None
    status: str | None = None


class RevenuePoint(BaseModel):
    period: str
    revenue: float
    appointment_type: str | None = None


class RetentionMetrics(BaseModel):
    recurring_customer_rate: float
    average_interval_accuracy: float
    total_recurring_customers: int


class ReminderAnalytics(BaseModel):
    total_sent: int
    total_converted: int
    conversion_rate: float
    personal_conversion_rate: float
    default_conversion_rate: float


class ConsentFunnel(BaseModel):
    total_contacts: int
    uncontacted: int
    pending: int
    opted_in: int
    opted_out: int
    opt_in_rate: float
