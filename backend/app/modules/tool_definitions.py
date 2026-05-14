"""Anthropic tool_use definitions for customer and admin SMS conversations."""

# ── Customer tools ──

LIST_SERVICES = {
    "name": "list_services",
    "description": "List all available appointment types with name, duration, and price.",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

CHECK_AVAILABILITY = {
    "name": "check_availability",
    "description": (
        "Check available appointment slots for a specific date. Optionally filter by service name. "
        "Each slot shows max capacity, current signups, and (when the event allows roster sharing) "
        "the names of volunteers already signed up. A slot only appears if it has capacity for the requested service."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format.",
            },
            "service_name": {
                "type": "string",
                "description": "Optional service name to filter slots (must match a name from list_services). If omitted, shows slots for all services.",
            },
        },
        "required": ["date"],
    },
}

GET_MY_APPOINTMENTS = {
    "name": "get_my_appointments",
    "description": "Get the customer's upcoming appointments (scheduled or rescheduled).",
    "input_schema": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

BOOK_APPOINTMENT = {
    "name": "book_appointment",
    "description": (
        "Create a new appointment booking for the customer. The customer must have confirmed the service, "
        "date, time, and price before calling this tool. Before calling, ASK the volunteer how they want "
        "their name shown to other volunteers on the event roster (first name only by default; full name if "
        "they prefer; hidden if they want privacy)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "service_name": {
                "type": "string",
                "description": "Name of the service (must match a name from list_services).",
            },
            "date": {
                "type": "string",
                "description": "Date in YYYY-MM-DD format.",
            },
            "time": {
                "type": "string",
                "description": "Time in HH:MM format (24-hour).",
            },
            "share_on_roster": {
                "type": "string",
                "enum": ["hidden", "first_name", "full_name"],
                "description": "How to show this volunteer to other volunteers on the event roster. Default 'first_name'.",
            },
        },
        "required": ["service_name", "date", "time"],
    },
}

CANCEL_APPOINTMENT = {
    "name": "cancel_appointment",
    "description": "Cancel an existing appointment by its reference code.",
    "input_schema": {
        "type": "object",
        "properties": {
            "booking_ref": {
                "type": "string",
                "description": "The booking reference code (last 8 characters of the booking ID).",
            },
        },
        "required": ["booking_ref"],
    },
}

RESCHEDULE_APPOINTMENT = {
    "name": "reschedule_appointment",
    "description": "Reschedule an existing appointment to a new date and time.",
    "input_schema": {
        "type": "object",
        "properties": {
            "booking_ref": {
                "type": "string",
                "description": "The booking reference code.",
            },
            "new_date": {
                "type": "string",
                "description": "New date in YYYY-MM-DD format.",
            },
            "new_time": {
                "type": "string",
                "description": "New time in HH:MM format (24-hour).",
            },
        },
        "required": ["booking_ref", "new_date", "new_time"],
    },
}

# ── Admin-only tools ──

SEARCH_BOOKINGS = {
    "name": "search_bookings",
    "description": "Search bookings with optional filters. Returns a list of matching bookings.",
    "input_schema": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Filter by specific date (YYYY-MM-DD).",
            },
            "status": {
                "type": "string",
                "description": "Filter by status: scheduled, rescheduled, completed, cancelled, no_show.",
            },
            "customer_phone": {
                "type": "string",
                "description": "Filter by customer phone number.",
            },
        },
        "required": [],
    },
}

LOOKUP_CUSTOMER = {
    "name": "lookup_customer",
    "description": "Look up customer information by phone number or name.",
    "input_schema": {
        "type": "object",
        "properties": {
            "phone": {
                "type": "string",
                "description": "Customer phone number to search.",
            },
            "name": {
                "type": "string",
                "description": "Customer name to search (partial match).",
            },
        },
        "required": [],
    },
}

BLOCK_DATE = {
    "name": "block_date",
    "description": (
        "Block a date range so no appointments can be booked during that period. "
        "If there are existing bookings in the range and cancel_existing is not set, "
        "the tool will return the list of affected bookings and ask the admin to confirm. "
        "Call again with cancel_existing=true to cancel them, or cancel_existing=false to block without cancelling."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "date_from": {
                "type": "string",
                "description": "Start date in YYYY-MM-DD format.",
            },
            "date_to": {
                "type": "string",
                "description": "End date in YYYY-MM-DD format.",
            },
            "reason": {
                "type": "string",
                "description": "Reason for blocking (e.g., 'Holiday', 'Maintenance').",
            },
            "cancel_existing": {
                "type": "boolean",
                "description": "If true, cancel all existing bookings in the date range. If false, block without cancelling. Omit to check for conflicts first.",
            },
        },
        "required": ["date_from", "date_to"],
    },
}

UNBLOCK_DATE = {
    "name": "unblock_date",
    "description": "Remove a date block to allow appointments again.",
    "input_schema": {
        "type": "object",
        "properties": {
            "date_from": {
                "type": "string",
                "description": "Start date of the block to remove (YYYY-MM-DD).",
            },
        },
        "required": ["date_from"],
    },
}

CANCEL_EVENT_BOOKINGS = {
    "name": "cancel_event_bookings",
    "description": (
        "Cancel every active booking on a given event date (optionally limited to one service), "
        "and notify each affected volunteer by SMS with the reason and an invitation to sign up again. "
        "The event itself stays open for new sign-ups — this only cancels the existing bookings, "
        "it does NOT block the date or delete the event. "
        "If `confirm` is not set, the tool returns the list of bookings that would be cancelled "
        "and asks the admin to confirm. Call again with `confirm=true` to actually cancel them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "event_date": {
                "type": "string",
                "description": "Event date in YYYY-MM-DD format.",
            },
            "service_name": {
                "type": "string",
                "description": (
                    "Optional. Only cancel bookings for this specific service "
                    "(e.g. 'Hall Setup'). Omit to cancel every booking on the date."
                ),
            },
            "reason": {
                "type": "string",
                "description": (
                    "Short reason shown to volunteers in the cancellation SMS "
                    "(e.g. 'venue change', 'rescheduling'). Optional."
                ),
            },
            "rebook_message": {
                "type": "string",
                "description": (
                    "Optional custom invitation appended to the SMS. Defaults to "
                    "'You can sign up again whenever you're ready — just text us back.'"
                ),
            },
            "confirm": {
                "type": "boolean",
                "description": "Set true to actually cancel and notify. Omit to preview the affected bookings first.",
            },
        },
        "required": ["event_date"],
    },
}

GET_SCHEDULE = {
    "name": "get_schedule",
    "description": "Get the schedule for a specific date: all bookings and available slots.",
    "input_schema": {
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Date to view (YYYY-MM-DD). Defaults to today if omitted.",
            },
        },
        "required": [],
    },
}

MANAGE_SERVICE = {
    "name": "manage_service",
    "description": (
        "Create, update, or deactivate a service/appointment type. "
        "Each service defines its minimum duration and price. "
        "Min/max participants are configured per availability window via manage_availability."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "update", "deactivate"],
                "description": "Action to perform.",
            },
            "name": {
                "type": "string",
                "description": "Service name (required for all actions).",
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Minimum slot duration in minutes (required for create).",
            },
            "price": {
                "type": "number",
                "description": "Price (required for create).",
            },
            "description": {
                "type": "string",
                "description": "Service description (optional).",
            },
        },
        "required": ["action", "name"],
    },
}

SEND_ANNOUNCEMENT = {
    "name": "send_announcement",
    "description": (
        "Send an SMS announcement to volunteers. Two common modes:\n"
        "1) Broadcast to ALL opted-in volunteers — call with just `message` (no booking_date, no status_filter).\n"
        "2) Event-specific — call with `booking_date` AND `service_name` (and optionally `status_filter='upcoming'`). "
        "This sends only to volunteers who are signed up for that event/service on that date. The system auto-prepends "
        "an event header (date, time, location) to the message in this mode.\n"
        "IMPORTANT: Always ASK the admin before sending which audience they want — sign-ups for the event, or all opted-in "
        "volunteers — and confirm both the message and audience before invoking this tool."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "The SMS message to send to volunteers. Do not include event details — the system prepends a header automatically when booking_date + service_name are provided.",
            },
            "service_name": {
                "type": "string",
                "description": "Only send to volunteers who have booked or prefer this service (must match a name from list_services). Combine with booking_date for event-specific announcements.",
            },
            "booking_date": {
                "type": "string",
                "description": "Only send to volunteers who have bookings on this date (YYYY-MM-DD). When set together with service_name, the announcement is treated as event-specific.",
            },
            "status_filter": {
                "type": "string",
                "enum": ["upcoming", "past", "cancelled"],
                "description": "Filter by booking status: 'upcoming' (scheduled/rescheduled), 'past' (completed), 'cancelled'.",
            },
        },
        "required": ["message"],
    },
}

MANAGE_AVAILABILITY = {
    "name": "manage_availability",
    "description": (
        "View or manage weekly schedule windows. Each window can specify which services are needed "
        "with minimum and maximum participants per service. "
        "Use 'list' to see current schedule (returns ids). Use 'set' to add a new window. "
        "Use 'update' to modify an existing window by id (only the fields you provide are changed). "
        "Use 'delete' to remove a window by id."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "set", "update", "delete"],
                "description": "Action: 'list' to view, 'set' to add, 'update' to modify, 'delete' to remove.",
            },
            "id": {
                "type": "string",
                "description": "Rule id (required for 'update' and 'delete'). Get it from 'list'.",
            },
            "day_of_week": {
                "type": "integer",
                "description": "Day of week (0=Monday, 6=Sunday). Required for 'set'.",
            },
            "label": {
                "type": "string",
                "description": "Label (optional).",
            },
            "start_time": {
                "type": "string",
                "description": "Start time HH:MM. Required for 'set'.",
            },
            "end_time": {
                "type": "string",
                "description": "End time HH:MM. Required for 'set'.",
            },
            "buffer_minutes": {
                "type": "integer",
                "description": "Buffer between appointments (default 0).",
            },
            "allow_roster_sharing": {
                "type": "boolean",
                "description": "If true (default), volunteers signed up for this window can see each other's names on the roster (subject to each volunteer's own per-booking visibility setting).",
            },
            "services": {
                "type": "array",
                "description": "Services needed during this window with min/max participants. If omitted, all services allowed (min 1, max 1). On 'update', omit to leave services unchanged; pass an empty array to clear.",
                "items": {
                    "type": "object",
                    "properties": {
                        "service_name": {"type": "string", "description": "Service name (must match list_services)."},
                        "min_required": {"type": "integer", "description": "Minimum participants needed (default 1)."},
                        "max_allowed": {"type": "integer", "description": "Maximum participants allowed (default = min_required)."},
                    },
                    "required": ["service_name"],
                },
            },
        },
        "required": ["action"],
    },
}

MANAGE_SPECIFIC_DATE_SLOT = {
    "name": "manage_specific_date_slot",
    "description": (
        "View or manage one-off events on specific dates. "
        "Use 'list' to see upcoming events (returns ids). "
        "Use 'add' to create a new event. "
        "Use 'update' to modify an existing event by id (only fields you provide are changed). "
        "Use 'delete' to remove an event by id."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "add", "update", "delete"],
                "description": "Action: 'list' to view, 'add' to create, 'update' to modify, 'delete' to remove.",
            },
            "id": {
                "type": "string",
                "description": "Event id (required for 'update' and 'delete'). Get it from 'list'.",
            },
            "date": {"type": "string", "description": "Date YYYY-MM-DD. Required for 'add'."},
            "start_time": {"type": "string", "description": "Start time HH:MM. Required for 'add'."},
            "end_time": {"type": "string", "description": "End time HH:MM. Required for 'add'."},
            "label": {"type": "string", "description": "Event name/label (optional)."},
            "location": {"type": "string", "description": "Event location (optional)."},
            "buffer_minutes": {"type": "integer", "description": "Buffer between appointments (default 0)."},
            "allow_roster_sharing": {
                "type": "boolean",
                "description": "If true (default), volunteers signed up for this event can see each other's names on the roster (subject to each volunteer's own per-booking visibility setting).",
            },
            "services": {
                "type": "array",
                "description": "Services needed for this event with min/max participants. On 'update', omit to leave unchanged; pass empty array to clear.",
                "items": {
                    "type": "object",
                    "properties": {
                        "service_name": {"type": "string", "description": "Service name."},
                        "min_required": {"type": "integer", "description": "Minimum participants."},
                        "max_allowed": {"type": "integer", "description": "Maximum participants."},
                    },
                    "required": ["service_name"],
                },
            },
        },
        "required": ["action"],
    },
}

MANAGE_VOLUNTEER = {
    "name": "manage_volunteer",
    "description": (
        "View or manage volunteer (customer) records. Mirrors the admin web UI. "
        "Use 'list' to search across volunteers (returns phones + basic info). "
        "Use 'get' for one volunteer's full record (services, availability, weekly hours, blocked dates). "
        "Use 'add' to register a new volunteer. "
        "Use 'update' to modify any subset of fields by phone. "
        "Use 'delete' to remove a volunteer (only allowed when they have no upcoming bookings). "
        "For status changes (suspend/unsuspend), use the dedicated suspend/unsuspend tools."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "get", "add", "update", "delete"],
                "description": "What to do.",
            },
            "phone": {
                "type": "string",
                "description": "Volunteer phone number. Required for 'get', 'add', 'update', 'delete'. Used as a substring match for 'list'.",
            },
            "name": {
                "type": "string",
                "description": "Volunteer name. Required for 'add'. Substring match for 'list' (when phone not given).",
            },
            "email": {"type": "string", "description": "Email (optional)."},
            "sex": {
                "type": "string",
                "enum": ["male", "female", "non_binary", "prefer_not_to_say"],
                "description": "Sex (optional).",
            },
            "reminder_preference_days": {
                "type": "integer",
                "description": "Days before appointment to send reminder (default 7).",
            },
            "background_check_required": {
                "type": "boolean",
                "description": "If true, the volunteer is blocked from booking until cleared.",
            },
            "all_services_enabled": {
                "type": "boolean",
                "description": "If true, the volunteer can book any active service (preferred_services is ignored).",
            },
            "preferred_services": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Array of service names this volunteer participates in. On 'update', omit to leave unchanged; pass empty array to clear.",
            },
            "availability": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "weekday_am",
                        "weekday_pm",
                        "weekday_eve",
                        "weekend_am",
                        "weekend_pm",
                        "weekend_eve",
                    ],
                },
                "description": "General availability buckets. On 'update', omit to leave unchanged; pass empty array to clear.",
            },
            "weekly_hours": {
                "type": "array",
                "description": "Specific weekly windows (day_of_week 0=Mon..6=Sun, start_time HH:MM, end_time HH:MM). On 'update', omit to leave unchanged; pass empty array to clear.",
                "items": {
                    "type": "object",
                    "properties": {
                        "day_of_week": {"type": "integer"},
                        "start_time": {"type": "string"},
                        "end_time": {"type": "string"},
                    },
                    "required": ["day_of_week", "start_time", "end_time"],
                },
            },
            "unavailable_dates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Dates the volunteer cannot attend (YYYY-MM-DD). On 'update', omit to leave unchanged; pass empty array to clear.",
            },
        },
        "required": ["action"],
    },
}

SUSPEND_CUSTOMER = {
    "name": "suspend_customer",
    "description": (
        "Suspend a customer by phone number. The customer will be blocked from booking "
        "and will receive a suspension notice if they message. "
        "Always confirm the phone number and reason with the admin before suspending."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "phone": {
                "type": "string",
                "description": "Customer phone number.",
            },
            "reason": {
                "type": "string",
                "description": "Reason for suspension.",
            },
        },
        "required": ["phone", "reason"],
    },
}

UNSUSPEND_CUSTOMER = {
    "name": "unsuspend_customer",
    "description": "Lift a suspension for a customer, restoring their ability to book appointments.",
    "input_schema": {
        "type": "object",
        "properties": {
            "phone": {
                "type": "string",
                "description": "Customer phone number.",
            },
        },
        "required": ["phone"],
    },
}

# ── Tool sets ──

CUSTOMER_TOOLS = [
    LIST_SERVICES,
    CHECK_AVAILABILITY,
    GET_MY_APPOINTMENTS,
    BOOK_APPOINTMENT,
    CANCEL_APPOINTMENT,
    RESCHEDULE_APPOINTMENT,
]

ADMIN_TOOLS = [
    LIST_SERVICES,
    CHECK_AVAILABILITY,
    GET_MY_APPOINTMENTS,
    BOOK_APPOINTMENT,
    CANCEL_APPOINTMENT,
    RESCHEDULE_APPOINTMENT,
    SEARCH_BOOKINGS,
    MANAGE_VOLUNTEER,
    BLOCK_DATE,
    UNBLOCK_DATE,
    CANCEL_EVENT_BOOKINGS,
    GET_SCHEDULE,
    MANAGE_SERVICE,
    MANAGE_AVAILABILITY,
    MANAGE_SPECIFIC_DATE_SLOT,
    SEND_ANNOUNCEMENT,
    SUSPEND_CUSTOMER,
    UNSUSPEND_CUSTOMER,
]
