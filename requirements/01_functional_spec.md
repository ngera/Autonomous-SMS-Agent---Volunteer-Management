# AI-Powered Appointment Booking System

### Functional Specification

*What the system does and how it behaves*

Document 1 of 3

Version 1.0 | March 2026

*Status: Draft*

## Table of Contents

- [1. Purpose and Scope](#purpose-and-scope)
- [2. System Overview](#system-overview)
- [3. User Roles](#user-roles)
- [4. Admin Authentication](#admin-authentication)
  - [4.1 Login](#login)
  - [4.2 Session Management](#session-management)
  - [4.3 Password Reset](#password-reset)
  - [4.4 Role Permissions](#role-permissions)
- [5. End User Consent Management](#end-user-consent-management)
  - [5.1 Consent States](#consent-states)
  - [5.2 Opt-In Flow](#opt-in-flow)
  - [5.3 Opt-Out — At Any Time](#opt-out-----at-any-time)
  - [5.4 Re-Opt-In](#re-opt-in)
  - [5.5 Consent Audit Trail](#consent-audit-trail)
- [6. SMS Conversational Chatbot](#sms-conversational-chatbot)
  - [6.1 Message Processing Pipeline](#message-processing-pipeline)
  - [6.2 Dynamic Context](#dynamic-context)
  - [6.3 Natural Language Handling](#natural-language-handling)
  - [6.4 Booking Conversation Stages](#booking-conversation-stages)
  - [6.5 Fallback Behaviour](#fallback-behaviour)
  - [6.6 Conversation Expiry](#conversation-expiry)
- [7. Appointment Types and Related Services](#appointment-types-and-related-services)
  - [7.1 Appointment Type Properties](#appointment-type-properties)
  - [7.2 Related Services](#related-services)
  - [7.3 Price Snapshot](#price-snapshot)
- [8. Calendar Integration](#calendar-integration)
  - [8.1 Operations](#operations)
  - [8.2 Availability Logic](#availability-logic)
  - [8.3 Calendar Event Contents](#calendar-event-contents)
- [9. Appointment Booking Flow](#appointment-booking-flow)
  - [9.1 Booking Status Lifecycle](#booking-status-lifecycle)
  - [9.2 Reschedule Flow](#reschedule-flow)
  - [9.3 Cancellation Flow](#cancellation-flow)
- [10. ICS Calendar Invite Feature](#ics-calendar-invite-feature)
  - [10.1 Three ICS Operations](#three-ics-operations)
  - [10.2 How SEQUENCE Works](#how-sequence-works)
  - [10.3 SMS Messages with ICS Links](#sms-messages-with-ics-links)
  - [10.4 Resending an ICS Link](#resending-an-ics-link)
- [11. Recurring Appointment Intelligence](#recurring-appointment-intelligence)
  - [11.1 Interval Calculation](#interval-calculation)
  - [11.2 Confidence Levels](#confidence-levels)
  - [11.3 Manual Override](#manual-override)
  - [11.4 Pattern Recalculation](#pattern-recalculation)
  - [11.5 What is Stored](#what-is-stored)
- [12. Automated Reminder System](#automated-reminder-system)
  - [12.1 Reminder Trigger Conditions](#reminder-trigger-conditions)
  - [12.2 Message Personalisation](#message-personalisation)
  - [12.3 Reminder Conversation Flow](#reminder-conversation-flow)
  - [12.4 Follow-Up](#follow-up)
  - [12.5 Reminder Outcomes](#reminder-outcomes)
- [13. Abuse Detection and Account Suspension](#abuse-detection-and-account-suspension)
  - [13.1 Pre-Screener](#pre-screener)
  - [13.2 Classifications](#classifications)
  - [13.3 Strike Escalation](#strike-escalation)
  - [13.4 Strike Decay](#strike-decay)
  - [13.5 Post-Suspension Behaviour](#post-suspension-behaviour)
  - [13.6 Admin Review](#admin-review)
- [14. Web Admin Panel](#web-admin-panel)
  - [14.1 Dashboard](#dashboard)
  - [14.2 Bookings Module](#bookings-module)
  - [14.3 Customers Module](#customers-module)
  - [14.4 Appointment Types Module](#appointment-types-module)
  - [14.5 Availability Module](#availability-module)
  - [14.6 Reminders Module](#reminders-module)
  - [14.7 Conversations Module](#conversations-module)
  - [14.8 Suspensions Module](#suspensions-module)
  - [14.9 Analytics Module](#analytics-module)
  - [14.10 Settings Module](#settings-module)
- [15. Notifications](#notifications)
- [16. Analytics and Reporting](#analytics-and-reporting)

---

## 1. Purpose and Scope

This document defines the complete functional specification for the AI-Powered Appointment Booking System. It describes what the system does, how it behaves, the rules it enforces, and the experience it delivers to both end users and administrators. It does not describe implementation details, programming languages, or infrastructure — those are covered in the Technical Specification (Document 2).

This document is the primary reference for understanding system behaviour, designing test cases, and validating that the built system meets its requirements.

## 2. System Overview

The system is an AI-powered appointment booking platform that enables service businesses to automate the full lifecycle of appointment management via SMS. End users interact exclusively via SMS on their own phones — no app download or registration required. Administrators manage all aspects of the service through a browser-based admin panel accessible from any device.

The system handles six core lifecycle stages automatically:

-   Initial consent collection from new customers

-   AI-guided booking conversations with appointment selection, upsell suggestions, and price confirmation

-   Calendar event creation with ICS invite links for users

-   Proactive reminder outreach based on personalised recurrence patterns

-   Appointment modification and cancellation with calendar synchronisation

-   Abuse detection, cost control, and account suspension management

| Capability | Description |
| — | — |
| Messaging channel | Twilio SMS API — all end user interaction |
| AI conversations | Natural language booking dialogue powered by claude-haiku-4-5 |
| Calendar | Google Calendar — read availability, write/update/delete events |
| Admin interface | Browser-based web app, works on phone, tablet, and desktop |
| Supported users | Up to 250 active customers per month (scalable beyond) |
| Languages | English (extensible to other languages via AI model capability) |

## 3. User Roles

The system has two distinct user types with separate interfaces and capabilities.

| Role | Interface | Description |
| — | — | — |
| End User | SMS | Customers who book appointments. No account or app required. |
| Admin — Owner | Web Admin Panel | Full system access including admin user management and all settings. |
| Admin — Manager | Web Admin Panel | Full booking and customer management. Cannot manage admin users or billing. |
| Admin — Staff | Web Admin Panel | Read-only access to bookings and customer profiles. No configuration access. |

## 4. Admin Authentication

The Admin Panel is protected by email and password authentication. All admin sessions are managed via secure JWT tokens. No part of the Admin Panel is accessible without a valid authenticated session.

### 4.1 Login

-   Admin navigates to the Admin Panel URL in any browser

-   If a valid session exists, admin is taken directly to the dashboard

-   If no valid session, the login screen is displayed

-   Admin enters email and password and clicks Sign In

-   On success, admin is redirected to the dashboard

-   On failure, an error message is shown — the specific reason (wrong email vs wrong password) is NOT revealed to prevent enumeration attacks

-   After 5 consecutive failed login attempts, the account is locked for 15 minutes

### 4.2 Session Management

-   Sessions expire after 30 minutes of inactivity

-   On expiry, the admin is shown the login screen and returned to their previous page after re-authentication

-   A "Remember me" option extends the session to 7 days

-   Admins can log out explicitly at any time via the user menu

-   Multiple concurrent sessions are permitted (e.g. phone and laptop simultaneously)

### 4.3 Password Reset

-   Admins can request a password reset via the login screen

-   A reset link is sent to the registered email address

-   Reset links expire after 1 hour

-   After a successful password reset, all existing sessions are invalidated

### 4.4 Role Permissions

| Feature | Owner | Manager | Staff |
| — | — | — | — |
| View dashboard | Yes | Yes | Yes |
| View bookings | Yes | Yes | Yes |
| Create/edit/cancel bookings | Yes | Yes | No |
| View customers | Yes | Yes | Yes |
| Edit customer details | Yes | Yes | No |
| Manage consent (opt-in/opt-out) | Yes | Yes | No |
| Configure appointment types | Yes | Yes | No |
| Configure availability | Yes | Yes | No |
| View conversations | Yes | Yes | Yes |
| Review suspensions | Yes | Yes | No |
| View analytics | Yes | Yes | No |
| Manage admin users | Yes | No | No |
| System settings | Yes | No | No |

## 5. End User Consent Management

All communication with end users is governed by explicit opt-in consent. No message of any kind is sent to a user until they have actively confirmed they wish to receive messages. This is required by TCPA and carrier SMS regulations and applicable data protection regulations.

### 5.1 Consent States

| State | Description | Can Receive Messages? |
| — | — | — |
| UNCONTACTED | In the system but never sent any message | No |
| PENDING | Opt-in invitation sent, awaiting reply | Opt-in message only |
| OPTED_IN | Confirmed consent — active customer | Yes — all messages |
| OPTED_OUT | Declined or withdrew consent | No |
| BLOCKED | Account suspended pending admin review | No |

### 5.2 Opt-In Flow

When an admin triggers an opt-in outreach to a customer, the system sends a pre-approved SMS opt-in message. This message must clearly state: the business name, what types of messages the customer will receive, and how to opt out. The customer replies YES to consent or NO to decline. Any response matching YES intent (yes, y, sure, ok, absolutely) sets the status to OPTED_IN. Any response matching NO intent (no, n, nope, don\'t, not interested) sets the status to OPTED_OUT.

> *Carriers require the opt-in SMS to be pre-approved before sending. SMS opt-in messages must comply with TCPA regulations. Carriers may filter non-compliant messages.*

### 5.3 Opt-Out — At Any Time

A customer can opt out at any point during any conversation by sending any of the following keywords or phrases: STOP, UNSUBSCRIBE, OPT OUT, OPTOUT, REMOVE ME, DO NOT CONTACT, LEAVE ME ALONE, NO MORE MESSAGES, CANCEL MESSAGES.

The opt-out check runs as the very first step when any message is received — before any AI call, before any business logic. On detection:

1.  Status is immediately set to OPTED_OUT

2.  A confirmation message is sent: "You have been unsubscribed and will receive no further messages. Contact us directly if you change your mind."

3.  All conversation processing stops immediately

4.  No further messages are ever sent to this number without a new explicit admin-initiated opt-in

### 5.4 Re-Opt-In

An opted-out customer can only be re-contacted if an admin deliberately initiates a new opt-in outreach and provides a documented reason. This is a manual action requiring at least Manager role. The system does not automatically re-contact opted-out customers under any circumstances.

### 5.5 Consent Audit Trail

Every consent status change is permanently recorded with: the previous and new status, the timestamp, the identity of who made the change (phone number for user-initiated, admin user ID for admin-initiated), and a mandatory reason for admin-initiated changes. This audit trail is visible in the admin panel and cannot be deleted.

## 6. SMS Conversational Chatbot

The chatbot is an AI-powered conversational agent that conducts natural-language appointment booking conversations entirely via SMS. It is dynamically informed by live configuration data so any change the admin makes is immediately reflected in subsequent conversations.

### 6.1 Message Processing Pipeline

Every inbound message from a user passes through the following pipeline in strict order. Each step can terminate processing early if the appropriate condition is met.

| Step | Check | Action on Failure |
| — | — | — |
| 1 | Validate Twilio webhook signature | Reject — return 403 |
| 2 | Check account suspension status | Log silently — no response sent |
| 3 | Check opt-out keywords | Process opt-out — send confirmation — stop |
| 4 | Check consent status (opted_in) | Route to consent flow — stop main flow |
| 5 | Pre-screener Stage 1 (rule-based) | If IRRELEVANT/ABUSIVE — handle strike — stop |
| 6 | Pre-screener Stage 2 (AI micro-prompt) | If IRRELEVANT/ABUSIVE — handle strike — stop |
| 7 | Load conversation history | Create new conversation record |
| 8 | Fetch dynamic context | Log error — send fallback message |
| 9 | Call full conversation AI | Log error — send fallback message |
| 10 | Parse AI intent (booking/confirmation) | Continue conversation |
| 11 | Execute booking if confirmed | Log error — send fallback message |
| 12 | Send SMS response | Retry up to 3 times |
| 13 | Save conversation history | Log error — do not retry |

### 6.2 Dynamic Context

At each conversation turn, the following live data is fetched from the database and injected into the AI system prompt. This means the AI always has current, accurate information without any code deployment when the admin updates configuration.

-   All active appointment types with name, duration, price, and description

-   Related service pairings with suggestion messages

-   Available calendar slots for the next 14 days (from Google Calendar API)

-   Customer\'s booking history summary (for returning customers)

-   Business name and any custom instructions set by the admin in Settings

### 6.3 Natural Language Handling

Because claude-haiku-4-5 processes the conversation, customers can respond naturally. The system handles varied phrasings such as:

-   "The longer one please" — maps to longest-duration appointment type

-   "Tuesday afternoon" — maps to available Tuesday PM slots

-   "Can I change to Wednesday?" — mid-flow slot change handled gracefully

-   "How much is that?" — price confirmation mid-conversation

-   "Actually, add the follow-up too" — late-stage related service addition

### 6.4 Booking Conversation Stages

| Stage | Bot Behaviour | User Expected Response |
| — | — | — |
| Greeting | Welcomes user, confirms booking service | Intent to book |
| Type selection | Lists available appointment types with durations and prices | Selects a type by name or number |
| Related service | If configured, naturally suggests a complementary service | Accept or decline |
| Slot selection | Presents 3 available time slots from live calendar | Selects a slot |
| Price confirmation | States total price including any add-ons, asks to confirm | Confirms price |
| Final confirmation | Summarises full booking details, asks for explicit confirmation | Confirms or changes mind |
| Booking complete | Confirms booking, sends ICS link, closes conversation | No response needed |

### 6.5 Fallback Behaviour

If the user provides a response the AI cannot map to a clear intent after two attempts, the bot sends a fallback message offering a simplified menu of options and, if still unclear, directs the user to contact the business directly. This prevents infinite loops and keeps conversations productive.

### 6.6 Conversation Expiry

Conversations with no activity for 7 days are automatically marked as expired. If the user sends a message after expiry, a new conversation begins from the greeting stage. Booking history is preserved — only the conversation state resets.

## 7. Appointment Types and Related Services

All appointment configuration is managed by the administrator and stored in the database. Changes take effect immediately for all subsequent conversations.

### 7.1 Appointment Type Properties

| Property | Description | Required? |
| — | — | — |
| Name | Display name shown to customers in conversation | Yes |
| Duration (minutes) | Used to compute end time when creating calendar events | Yes |
| Price | Displayed to customer for confirmation; stored at booking time | Yes |
| Description | Optional context injected into AI prompt for richer conversation | No |
| Default recurrence (weeks) | Used when customer has insufficient booking history for personalisation | No |
| Active | Inactive types are hidden from chatbot and not offered to customers | Yes |

### 7.2 Related Services

Any appointment type can be linked to one or more other appointment types as a related service. When a customer selects a type that has related services, the AI naturally suggests the related service during the conversation. Each relationship has a custom suggestion message written by the admin, allowing contextual and natural-sounding recommendations.

Example: "Consultation" is linked to "Follow-up Session" with the suggestion message: "Many clients find it helpful to also book a follow-up session within a week. Would you like to add one today at a discounted rate?" The AI weaves this into the conversation at the appropriate moment — after the customer has selected their main appointment but before slot selection.

### 7.3 Price Snapshot

When a booking is confirmed, the price at that moment is stored in the booking record. This means subsequent price changes by the admin do not retroactively affect existing confirmed bookings. The price shown in booking history always reflects what the customer was quoted and confirmed.

## 8. Calendar Integration

The system integrates with the administrator\'s Google Calendar account. Google Calendar is the single source of truth for availability. The system never maintains a separate internal calendar — it always queries Google Calendar in real time.

### 8.1 Operations

| Operation | When Triggered | Outcome |
| — | — | — |
| Read availability | Customer requests slot options during booking conversation | Free slots computed from working hours minus existing events |
| Create event | Booking confirmed by customer | Calendar event created with customer details; event ID stored in database |
| Update event | Admin or customer reschedules existing booking | Existing calendar event updated to new time |
| Delete event | Booking cancelled by admin or customer | Calendar event removed |

### 8.2 Availability Logic

Available slots are computed as follows: working hours configured by the admin are taken as the base availability. Existing Google Calendar events (any event, not just system-created ones) are treated as busy periods. Buffer time configured per appointment type is added around each busy period. The remaining gaps that fit the requested appointment duration are the available slots. A maximum of 3 slot options are presented to the user per conversation turn.

### 8.3 Calendar Event Contents

Each calendar event created by the system contains: the appointment type name and customer name in the title, the customer phone number and confirmed price in the description, and the correct start and end times based on the appointment duration.

## 9. Appointment Booking Flow

A booking progresses through defined status states from creation through completion. The status lifecycle governs what actions are available at each stage.

### 9.1 Booking Status Lifecycle

| Status | Meaning | Possible Next States |
| — | — | — |
| SCHEDULED | Confirmed by customer, calendar event created | COMPLETED, CANCELLED, RESCHEDULED |
| RESCHEDULED | Moved to a new time, calendar event updated | COMPLETED, CANCELLED, RESCHEDULED |
| COMPLETED | Appointment date has passed and was attended | Terminal — triggers pattern recalculation |
| CANCELLED | Cancelled before the appointment date | Terminal — calendar event deleted |
| NO_SHOW | Customer did not attend | Terminal — tracked for pattern analysis |

### 9.2 Reschedule Flow

A booking can be rescheduled by the admin through the Admin Panel or by the customer via SMS conversation. In both cases:

5.  New slot availability is checked against Google Calendar in real time

6.  Customer receives a SMS message confirming the new time

7.  Google Calendar event is updated to the new time

8.  ICS update link is sent to the customer for their personal calendar

9.  Reschedule is recorded in the booking history audit trail

### 9.3 Cancellation Flow

A booking can be cancelled by the admin through the Admin Panel. Customer-initiated cancellation via SMS is also supported — the AI recognises cancellation intent and confirms before processing. On cancellation:

10. Google Calendar event is deleted

11. Customer receives a cancellation confirmation via SMS

12. ICS cancellation link is sent so the event is removed from the customer\'s personal calendar

13. Booking status set to CANCELLED

14. Cancellation recorded in booking history

## 10. ICS Calendar Invite Feature

When a booking is created, rescheduled, or cancelled, the system generates a calendar invite link that the customer can tap via SMS to update their personal device calendar. The ICS format is universally supported by Apple Calendar (iPhone), Google Calendar, Android Calendar, Outlook, and all major calendar applications.

### 10.1 Three ICS Operations

| Operation | ICS Method | Trigger | Customer Experience |
| — | — | — | — |
| New booking | METHOD:REQUEST (SEQUENCE:0) | Booking confirmed | Tap link → "Add to Calendar?" prompt → tap Add |
| Reschedule | METHOD:REQUEST (SEQUENCE:N+1) | Booking rescheduled | Tap link → "Update existing event?" → tap Update |
| Cancellation | METHOD:CANCEL (SEQUENCE:N+1) | Booking cancelled | Tap link → "Remove from Calendar?" → tap Remove |

### 10.2 How SEQUENCE Works

Each booking is assigned a unique UID (based on the booking ID) that persists across all modifications. The SEQUENCE number starts at 0 for a new booking and increments by 1 on every reschedule or cancellation. The customer\'s calendar app uses the UID to identify which event to update or remove, and the SEQUENCE to ensure it is receiving a newer version and not a duplicate. This means rescheduling and cancelling work correctly even if the customer tapped the original add link.

### 10.3 SMS Messages with ICS Links

***New Booking Confirmation***

> *"Your Full Session is confirmed for Tuesday 10 March at 10:00am. Price: £150. Add to your calendar: https://api.yourbusiness.com/calendar/abc123/new.ics"*

***Reschedule Confirmation***

> *"Your appointment has been rescheduled to Thursday 12 March at 2:00pm. Update your calendar: https://api.yourbusiness.com/calendar/abc123/update.ics"*

***Cancellation Confirmation***

> *"Your Full Session on Tuesday 10 March has been cancelled. Remove from your calendar: https://api.yourbusiness.com/calendar/abc123/cancel.ics"*

### 10.4 Resending an ICS Link

If a customer asks for the calendar link again during a conversation, the AI recognises this intent and resends the appropriate ICS link for their current booking. The admin can also resend ICS links manually from the booking detail screen in the Admin Panel.

## 11. Recurring Appointment Intelligence

The system analyses each customer\'s personal booking history per appointment type to calculate a personalised recurrence interval. This drives the automated reminder system and improves in accuracy over time as more booking data accumulates.

### 11.1 Interval Calculation

For each customer and appointment type combination, the algorithm:

15. Retrieves all COMPLETED bookings sorted by date

16. Calculates the gap in days between each consecutive pair

17. Calculates the median gap

18. Removes outlier gaps greater than 2× the median (missed cycles, holidays, etc.)

19. If fewer than 2 gaps remain, reverts to the original list

20. Calculates the mean of remaining gaps — this is the Personal Interval

### 11.2 Confidence Levels

The system blends the personal interval with the admin-configured default based on how much history is available, transitioning gradually rather than switching abruptly.

| Confidence | Completed Bookings | Personal Weight | Default Weight | Effective Interval |
| — | — | — | — | — |
| Default | 0—2 | 0% | 100% | Admin default only |
| Emerging | 3 | 33% | 67% | Mostly default |
| Emerging | 4 | 55% | 45% | Equal blend |
| Emerging | 5 | 77% | 23% | Mostly personal |
| Personal | 6+ | 100% | 0% | Personal interval only |

### 11.3 Manual Override

The admin can set a manual interval override for any individual customer. When a manual override is set, the algorithm is bypassed entirely for that customer and the override value is used. Manual overrides are visible on the customer profile and can be cleared to return to algorithmic calculation.

### 11.4 Pattern Recalculation

The pattern is automatically recalculated each time a booking is marked as COMPLETED. This ensures the interval stays current and improves as more bookings accumulate. The admin can also manually trigger a recalculation from the customer profile.

### 11.5 What is Stored

For each customer and appointment type combination, the system stores: the number of completed bookings counted, the raw calculated personal interval (if enough history), the blended interval actually used, the admin default at the time of calculation, the confidence level, the number of outliers removed, and the next calculated due date. This is displayed in the customer profile to give the admin full transparency into how the system derived the reminder schedule.

## 12. Automated Reminder System

The reminder system proactively contacts customers when they are approaching their next calculated appointment due date. This reduces gaps in the booking schedule and improves customer retention.

### 12.1 Reminder Trigger Conditions

A reminder is dispatched when ALL of the following conditions are true:

-   Today equals the customer\'s reminder date (next due date minus their lead time preference, default 7 days)

-   The customer does not already have a SCHEDULED booking for this appointment type

-   No reminder has been sent for this customer and appointment type in the past 14 days

-   The customer\'s consent status is OPTED_IN

-   The customer\'s account is active (not suspended or banned)

### 12.2 Message Personalisation

| Confidence Level | Message Tone | Example Opening |
| — | — | — |
| Personal | References their specific pattern | "Hi Sarah, we\'ve noticed you usually come in every 5 weeks — you\'re due for your next Full Session soon." |
| Default | General prompt | "Hi James, it\'s been a while since your last Full Session. Time to book your next one?" |
| Lapsed (2+ intervals overdue) | Re-engagement tone | "Hi Alex, we haven\'t seen you in a while. We\'d love to welcome you back — ready to book?" |

### 12.3 Reminder Conversation Flow

The reminder message initiates a new booking conversation. When the customer replies, the full AI booking conversation flow (Section 6.4) is triggered. The customer is guided through slot selection, price confirmation, and booking confirmation exactly as in a standard booking conversation.

If the customer indicates they want to skip this cycle ("Not this time", "Maybe next month"), the AI acknowledges gracefully and the system advances their next due date by one interval. The reminder record is closed as SKIPPED.

### 12.4 Follow-Up

If a customer does not respond to the initial reminder within 48 hours, a single follow-up message is sent. No further automated messages are sent regardless of whether the customer responds to the follow-up. The reminder record is updated to NO_RESPONSE and the system waits for the next calculated reminder cycle.

### 12.5 Reminder Outcomes

| Outcome | Status Set | Next Action |
| — | — | — |
| Customer books | BOOKED | Recurrence timer resets from new booking date |
| Customer skips this cycle | SKIPPED | Next due date advanced by one interval |
| No response after follow-up | NO_RESPONSE | Wait for next calculated reminder cycle |
| Customer opts out | N/A | Opt-out processed — no further reminders ever |
| Admin cancels reminder | CANCELLED | No message sent — reason logged |

## 13. Abuse Detection and Account Suspension

The system includes a cost-control and service-integrity mechanism that detects users sending irrelevant or abusive messages and prevents them from consuming AI processing resources. The detection engine uses claude-haiku-4-5 micro-prompts for accuracy while keeping per-check cost minimal.

### 13.1 Pre-Screener

Every inbound message passes through a two-stage screener before reaching the full conversation AI:

### Stage 1 — Rule-Based (Zero Cost)

-   Message under 2 characters after trimming → IRRELEVANT

-   Message over 85% non-alphabetic characters → IRRELEVANT

-   Message matches known prompt injection patterns → ABUSIVE

-   Message matches opt-out keywords → routed to opt-out handler (not a strike)

-   If none match → pass to Stage 2

### Stage 2 — AI Micro-Prompt (\~60--100 tokens)

A minimal claude-haiku-4-5 call classifies the message as exactly one of RELEVANT, IRRELEVANT, or ABUSIVE. The screener is given the business context and asked to respond with one word only.

### 13.2 Classifications

| Classification | Definition |
| — | — |
| RELEVANT | Message relates to booking, appointments, services, prices, availability, rescheduling, or confirmation |
| IRRELEVANT | Off-topic, random characters, nonsense, or unrelated questions (jokes, weather, football scores, etc.) |
| ABUSIVE | Threatening, offensive, prompt injection attempts, or messages trying to override AI behaviour |

### 13.3 Strike Escalation

| Strike | Trigger | System Action | Message Sent to User |
| — | — | — | — |
| 1 | First IRRELEVANT | Strike logged internally | "I can only help with booking appointments. Would you like to schedule one?" |
| 2 | Second IRRELEVANT | Strike logged, warning sent | "Please keep messages relevant to booking. Further off-topic messages may suspend your access." |
| 3 | Third IRRELEVANT | Strike logged, final warning | "This is your final warning. Further off-topic messages will suspend your access." |
| 4 | Fourth IRRELEVANT | Account suspended immediately | "Your access has been temporarily suspended. Contact us directly if you believe this is an error." |
| Any ABUSIVE | Any abusive message | Immediate suspension, no warnings | Same suspension message |

### 13.4 Strike Decay

Strikes older than 30 days do not count toward the suspension threshold. This prevents a genuine customer who sent a confused message weeks ago from being unfairly suspended. Decay is evaluated at the time of each new message, not as a background process.

### 13.5 Post-Suspension Behaviour

Once suspended, every inbound message from that number is silently dropped at the very first step of the pipeline — before any AI call, any business logic, and without sending any response. This is the cost-control mechanism: a suspended user cannot consume any further processing resources. Silence (no response) is deliberate — responding would encourage continued engagement.

### 13.6 Admin Review

On suspension, the admin receives an immediate notification with the full strike history and conversation context. The suspension remains in place until an admin with Manager or Owner role reviews the conversation and makes one of three decisions:

-   Lift suspension — restores account to OPTED_IN status, resets strike counter, optionally notifies customer that access has been restored

-   Confirm suspension — keeps account suspended indefinitely

-   Permanent ban — sets account to BANNED status; cannot be reversed without Owner intervention

All review decisions are recorded with the reviewing admin\'s identity, timestamp, and mandatory notes.

## 14. Web Admin Panel

The Admin Panel is a browser-based application accessible from any device. It provides full visibility and control over every aspect of the system. The layout uses a collapsible sidebar for navigation and a responsive design that adapts between desktop, tablet, and mobile phone.

### 14.1 Dashboard

The landing page after login. Provides a real-time overview of the current state of the business.

-   Today\'s appointments — list of all bookings scheduled for today with customer name, time, and type

-   Pending conversations — customers currently mid-booking conversation

-   Reminders going out today — customers the scheduler will contact today

-   Unreviewed suspensions — red badge count if any accounts await review

-   Monthly KPIs — total bookings, opt-in rate, reminder conversion rate, total revenue

-   Notification centre — recent alerts requiring admin attention

### 14.2 Bookings Module

-   Calendar view — visual monthly and weekly calendar of all appointments

-   List view — paginated, filterable, sortable table of all bookings

-   Filters: date range, status, appointment type, customer

-   Booking detail — full booking information, conversation reference, booking history audit trail

-   Reschedule — slot picker showing live availability, triggers full reschedule flow

-   Cancel — confirmation required, triggers cancellation flow including customer SMS message

-   Mark complete / no-show — manual status update

-   Manual booking creation — admin creates a booking directly without chatbot flow

### 14.3 Customers Module

-   Searchable, paginated customer list with consent status indicator

-   Customer profile — full view of one customer containing:

    -   Contact details (name, phone, email)

    -   Consent status and full audit trail timeline

    -   Complete booking history with status indicators

    -   Booking pattern data: confidence level, personal interval, default interval, next due date, outliers removed

    -   Full SMS conversation history

    -   Strike history and any suspension records

-   CSV import for bulk customer addition

-   Opt-in outreach — trigger the opt-in SMS to selected customers

-   Manual opt-out — requires reason, updates consent status immediately

-   Pattern override — set manual recurrence interval for a specific customer

### 14.4 Appointment Types Module

-   List of all appointment types with price, duration, recurrence default, and active status

-   Add new appointment type — name, duration, price, description, recurrence weeks, active

-   Edit existing — all fields editable; price changes do not affect confirmed bookings

-   Archive appointment type — removes from chatbot, preserves historical booking records

-   Related services manager — link types together with custom suggestion messages

### 14.5 Availability Module

-   Weekly schedule builder — set working hours per day of week with visual time picker

-   Blocked dates — add single dates or date ranges (holidays, time off)

-   Buffer time — configurable gap between appointments

-   Slot preview — shows how the availability configuration would look to customers

### 14.6 Reminders Module

-   Upcoming reminders — all reminders scheduled to fire in next 30 days with customer, type, confidence, and calculated interval

-   Sent history — past reminders with sent date, conversion outcome, and personal vs default label

-   Manual trigger — send a reminder to a specific customer outside the normal schedule

-   Cancel reminder — cancel a scheduled reminder before it fires with reason

-   Analytics — conversion rate by appointment type, by confidence level, by day of week

### 14.7 Conversations Module

-   Active conversations — all ongoing SMS conversations with current stage indicator

-   Conversation detail — complete message history for any customer in chronological order

-   Pre-screener classifications visible — shows how each message was classified

-   Admin notes — admin can add internal notes to a conversation visible only in the admin panel

### 14.8 Suspensions Module

-   All suspended accounts listed with suspension date, reason, and reviewed status

-   Unreviewed suspensions highlighted in red with prominent action required indicator

-   Suspension detail — full strike history with message content and classification, complete conversation, customer booking history

-   Actions: Lift Suspension, Confirm Suspension, Permanent Ban — all require notes

-   Manual suspend — admin can suspend any customer account with mandatory reason

### 14.9 Analytics Module

-   Booking trends — volume by week and month over time

-   Revenue — by appointment type, by month, cumulative

-   Retention — percentage of customers on recurring pattern, average interval accuracy

-   Reminder performance — sent vs converted, personal vs default conversion rate comparison

-   Consent funnel — uncontacted → pending → opted-in → opted-out rates

### 14.10 Settings Module

-   Business profile — name, address, SMS contact number for messages

-   Custom AI instructions — additional guidance injected into AI system prompt

-   Admin users — add, edit, deactivate admin accounts; change roles

-   SMS messages — view submitted SMSs and approval status

-   Google Calendar connection — connect, view status, disconnect

-   Notification preferences — which events trigger email notifications and to whom

## 15. Notifications

The admin notification system ensures timely awareness of events requiring attention.

| Event | In-App | Email | Priority |
| — | — | — | — |
| Account suspended (auto) | Yes — red badge | Yes — all Owners and Managers | High |
| Account suspended (manual) | Yes | No | Medium |
| Strike 3 issued (final warning) | Yes — amber | No | Medium |
| New booking confirmed | Yes | No | Low |
| Booking cancelled | Yes | No | Low |
| Customer opted out | Yes | No | Low |
| Reminder failed to send | Yes | Yes | High |
| Google Calendar API error | Yes | Yes | High |
| Unreviewed suspension older than 24hrs | Yes — escalated red | Yes | High |

## 16. Analytics and Reporting

The system captures data throughout the booking lifecycle to provide the admin with meaningful insights into business performance.

| Metric | Description | Use Case |
| — | — | — |
| Booking volume | Total bookings per week and month by type and status | Capacity planning |
| Revenue | Total and per-type revenue over time | Financial reporting |
| Reminder conversion rate | Percentage of reminders that result in a booking | Optimise reminder strategy |
| Personal vs default conversion | Compare conversion rates by interval confidence level | Validate personalisation value |
| Consent funnel | Opt-in rate, opt-out rate over time | Customer acquisition and retention |
| Average gap accuracy | How close actual rebooking gaps are to predicted intervals | Algorithm performance |
| Suspension rate | Accounts suspended per month, lift vs confirm rates | Abuse trend monitoring |
| Response time | Average time from reminder to booking confirmation | Message timing optimisation |
