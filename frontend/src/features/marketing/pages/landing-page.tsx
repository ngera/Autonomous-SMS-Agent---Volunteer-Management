import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Ban,
  Calendar,
  CheckCircle2,
  ClipboardList,
  Cpu,
  Heart,
  Mail,
  MessageSquare,
  Plug,
  Shield,
  Sheet,
  Sparkles,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-white text-zinc-900">
      <TopNav />
      <Hero />
      <LogoStrip />
      <AgentsSection />
      <AdminDashboardSection />
      <DashboardSection />
      <IntegrationsSection />
      <TrustSection />
      <PricingSection />
      <FAQSection />
      <BottomCTA />
      <Footer />
    </div>
  );
}

function Wordmark({
  variant = "blue",
  className,
}: {
  variant?: "blue" | "white";
  className?: string;
}) {
  // Light-mode lockup uses the primary brand blue on transparent — the
  // canonical blue mark. The dark/`white` variant uses the inverted
  // white-transparent for placement on darker backgrounds.
  const src =
    variant === "white"
      ? "/brand/mustr-white-transparent.svg"
      : "/brand/mustr-primary-blue-transparent.svg";
  return (
    <img
      src={src}
      alt="mustr"
      className={cn("h-10 w-auto", className)}
    />
  );
}

function TopNav() {
  return (
    <nav className="sticky top-0 z-50 border-b border-zinc-200/80 bg-white/85 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <div className="hidden items-center gap-7 text-sm text-zinc-600 md:flex">
          <a href="#agents" className="hover:text-zinc-900">
            Product
          </a>
          <a href="#pricing" className="hover:text-zinc-900">
            Pricing
          </a>
          <a href="#faq" className="hover:text-zinc-900">
            FAQ
          </a>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/login"
            className="text-sm font-medium text-zinc-700 hover:text-zinc-900"
          >
            Login
          </Link>
          <a
            href="#cta"
            className="rounded-full bg-[#0F172A] px-4 py-1.5 text-sm font-medium text-white hover:bg-zinc-800"
          >
            Book demo
          </a>
        </div>
      </div>
    </nav>
  );
}

function Hero() {
  return (
    <section className="bg-gradient-to-b from-[#F5F8FC] via-white to-white px-6 py-20">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <div>
          <Wordmark className="h-32 w-auto" />
          <h1 className="mt-8 text-6xl font-extrabold leading-[1.02] tracking-tight">
            Your non-profit&apos;s coordination agents,{" "}
            <em className="text-[#1c2d4a]">on autopilot.</em>
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-relaxed text-zinc-600">
            <span className="font-semibold text-zinc-900">mustr</span> plans
            events with you, reaches out to volunteers, fills shifts, sends
            reminders/announcements, and runs donation campaigns &mdash; all
            via plain SMS or voice calls.
          </p>
          <ul className="mt-4 max-w-xl list-disc pl-6 text-lg leading-relaxed text-zinc-900">
            <li className="font-semibold">No app for your volunteers or donors.</li>
            <li className="font-semibold">No spreadsheet for you.</li>
          </ul>
          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href="#cta"
              className="rounded-full bg-[#007AFF] px-6 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-[#0066d6]"
            >
              Book a 15-min demo
            </a>
            <a
              href="#hero-thread"
              className="rounded-full border border-zinc-300 bg-white px-6 py-3 text-sm font-semibold text-zinc-700 transition-colors hover:bg-zinc-50"
            >
              Watch a real conversation &rarr;
            </a>
          </div>
        </div>
        <div id="hero-thread" className="flex justify-center lg:justify-end">
          <HeroThread />
        </div>
      </div>
    </section>
  );
}

const HERO_MESSAGES: Array<{ kind: "in" | "out"; text: string }> = [
  {
    kind: "in",
    text: "Hi Maya 👋 We're 3 short for Sunday's 8am food drive — can you swing by?",
  },
  { kind: "out", text: "Sunday is a stretch. Got anything Saturday?" },
  {
    kind: "in",
    text: "Yes — Sat 9am pickup at the warehouse. ICS attached. Reply Y to lock it in.",
  },
  { kind: "out", text: "Y" },
  { kind: "in", text: "Locked in. See you Saturday 9am 🙌" },
];

function HeroThread() {
  return (
    <div className="w-full max-w-sm overflow-hidden rounded-3xl border border-[#9CADC2] bg-[#D2DBE8] shadow-2xl">
      <div className="flex items-center justify-between gap-2 border-b border-[#9CADC2] bg-[#BCC9DA]/95 px-3 py-3 backdrop-blur">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[#9CADC2] text-base">
            🤖
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold leading-tight text-black">
              mustr
            </p>
            <p className="truncate text-[11px] leading-tight text-black">
              Recruiter agent
            </p>
          </div>
        </div>
        <span className="text-[11px] text-black/70">today</span>
      </div>

      <div className="space-y-1.5 bg-[#D2DBE8] px-3 py-4">
        {HERO_MESSAGES.map((m, i) => {
          const isOut = m.kind === "out";
          return (
            <div
              key={i}
              className={cn(
                "flex w-full",
                isOut ? "justify-end" : "justify-start"
              )}
            >
              <div
                className={cn(
                  "max-w-[78%] whitespace-pre-wrap border border-[#9CADC2] bg-[#FBF6EE] px-3 py-1.5 text-sm leading-snug text-[#1c1c1e]",
                  isOut
                    ? "rounded-[18px] rounded-br-[4px]"
                    : "rounded-[18px] rounded-bl-[4px]"
                )}
              >
                {m.text}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center gap-2 border-t border-[#9CADC2] bg-[#BCC9DA]/95 px-2 py-2 backdrop-blur">
        <div className="h-8 flex-1 rounded-full border border-[#9CADC2] bg-[#FBF6EE] px-3 py-1.5 text-sm text-[#7e8a9c]">
          iMessage
        </div>
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#9CADC2] text-white">
          <ArrowUp className="h-4 w-4" strokeWidth={3} />
        </div>
      </div>
    </div>
  );
}

const LOGO_ORGS = [
  "Sample Food Bank",
  "City Animal Rescue",
  "Coastline Faith",
  "Rapid Relief Network",
  "Open Hands Coalition",
  "Westside Shelter",
];

function LogoStrip() {
  return (
    <section className="border-y border-zinc-200 bg-zinc-50/60 px-6 py-10">
      <div className="mx-auto max-w-6xl">
        <p className="text-center text-xs uppercase tracking-wider text-zinc-500">
          Trusted by food banks, animal shelters, faith communities, and
          disaster-relief teams across the U.S.
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
          {LOGO_ORGS.map((org) => (
            <span
              key={org}
              className="text-sm font-semibold uppercase tracking-wide text-zinc-400"
            >
              {org}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

const AGENTS = [
  {
    icon: Cpu,
    name: "Planner",
    tag: "Plans and fills empty events while you sleep.",
    body: "Plans outreach in waves, targets the right volunteers, escalates only when it can't close the gap.",
  },
  {
    icon: Calendar,
    name: "Scheduler",
    tag: "Books, swaps, and cascades reschedules.",
    body: "Multi-shift events, ICS calendar sync, no double-bookings ever.",
  },
  {
    icon: MessageSquare,
    name: "Engagement",
    tag: "Reminds, follows up, retains.",
    body: "Reminders, no-show chase, attendance tracking, retention loops.",
  },
  {
    icon: Heart,
    name: "Marketing",
    tag: "Runs donation campaigns end-to-end.",
    body: "Touch sequences, attribution, IRS-ready receipts. Stripe Connect built in.",
  },
];

function AgentsSection() {
  return (
    <section id="agents" className="px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-4xl font-bold tracking-tight">Meet the agents</h2>
          <p className="mt-3 text-lg text-zinc-600">
            Four specialists, one Orchestrator. Each one purpose-built &mdash;
            not a chatbot bolt-on.
          </p>
        </div>
        <div className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {AGENTS.map((a) => {
            const Icon = a.icon;
            return (
              <div
                key={a.name}
                className="rounded-2xl border border-zinc-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#E1E9F4] text-[#1c2d4a]">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="mt-4 text-lg font-semibold">{a.name}</h3>
                <p className="mt-1 text-sm italic text-[#1c2d4a]">{a.tag}</p>
                <p className="mt-3 text-sm leading-relaxed text-zinc-600">
                  {a.body}
                </p>
              </div>
            );
          })}
        </div>
        <p className="mt-10 text-center text-sm text-zinc-500">
          All coordinated by an{" "}
          <span className="font-semibold text-zinc-900">Orchestrator</span>.
          Admin takeover is one tap away.
        </p>
      </div>
    </section>
  );
}

const ADMIN_KPIS = [
  { label: "Volunteers", value: "1,247", trend: "+38 this mo" },
  { label: "This week", value: "7", trend: "5 recurring · 2 one-time" },
  { label: "Open slots", value: "23", trend: "Across 4 events" },
  { label: "Monthly bookings", value: "184", trend: "+12% vs last mo" },
];

const ADMIN_WEEK = [
  { name: "Sat 9am · Food Drive (Warehouse)", booked: 8, max: 12 },
  { name: "Sun 8am · Animal shelter pickup", booked: 12, max: 12 },
  { name: "Mon 10am · Front desk", booked: 4, max: 8 },
  { name: "Tue 6pm · Phone bank", booked: 15, max: 20 },
  { name: "Wed 7am · Kitchen prep", booked: 6, max: 6 },
];

const ADMIN_ALERTS = [
  {
    icon: AlertTriangle,
    title: "Food drive understaffed",
    body: "Sat 9am — 8/12 booked",
    tone: "amber" as const,
  },
  {
    icon: ClipboardList,
    title: "3 strikes pending review",
    body: "No-shows last 7 days",
    tone: "neutral" as const,
  },
  {
    icon: Ban,
    title: "1 volunteer suspended",
    body: "Awaiting action",
    tone: "neutral" as const,
  },
];

const ADMIN_CAMPAIGNS = [
  { name: "Fall Donor Drive", value: "$12.4k raised", color: "text-emerald-600" },
  { name: "Sat Recruit Wave", value: "47 invites sent", color: "text-[#007AFF]" },
];

function AdminDashboardSection() {
  return (
    <section className="bg-[#F8FAFC] px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-4xl font-bold tracking-tight">
            Run your week from one screen
          </h2>
          <p className="mt-3 text-lg text-zinc-600">
            Every event, every volunteer, every alert &mdash; at a glance.
          </p>
        </div>
        <div className="mt-14 space-y-16">
          <DashboardRow
            src="/screenshots/Dashboard1.png"
            alt="mustr admin dashboard — events and campaigns"
            heading="Manage events and campaigns"
            points={[
              "Live Event Roster",
              "Status of upcoming events",
              "Donation Tracker",
              "Alerts for events falling behind, decisions needed now, upcoming events, and more",
            ]}
          />
          <DashboardRow
            src="/screenshots/Dashboard2.png"
            alt="mustr admin dashboard — organization health"
            heading="Monitor your org's health"
            points={[
              "Volunteer recruiting trends, walk-ups, and no-shows",
              "Donor base growth and engagement",
              "Complaints, feedback, and issues — surfaced and addressable",
            ]}
          />
        </div>
      </div>
    </section>
  );
}

function DashboardRow({
  src,
  alt,
  heading,
  points,
  reverse = false,
}: {
  src: string;
  alt: string;
  heading: string;
  points: string[];
  reverse?: boolean;
}) {
  return (
    <div
      className={cn(
        "grid items-center gap-10 lg:grid-cols-[1.6fr_1fr]",
        reverse && "lg:[&>*:first-child]:order-2"
      )}
    >
      <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-2xl">
        <img
          src={src}
          alt={alt}
          className="block h-auto w-full"
          loading="lazy"
        />
      </div>
      <div>
        <h3 className="text-2xl font-bold tracking-tight text-zinc-900">
          {heading}
        </h3>
        <ul className="mt-5 space-y-3 text-zinc-700">
          {points.map((p) => (
            <li key={p} className="flex gap-2.5">
              <CheckCircle2 className="mt-0.5 h-5 w-5 flex-shrink-0 text-[#007AFF]" />
              <span>{p}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function DashboardSection() {
  return (
    <section className="bg-[#0F172A] px-6 py-24 text-white">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <div>
          <h2 className="text-4xl font-bold tracking-tight">
            One platform for volunteers <em className="text-[#7BA9F0]">and</em>{" "}
            donors
          </h2>
          <p className="mt-3 text-lg text-zinc-300">
            Drop the volunteer-signup tool, the email blaster, the donation
            page, and the spreadsheet that holds them together.
          </p>
          <ul className="mt-8 space-y-5 text-zinc-300">
            {[
              {
                title: "One contact record, not three.",
                body: "When Maria signs up for Saturday's food drive, mustr already knows she gave at year-end. Same person, same context — without anyone retyping anything.",
              },
              {
                title: "One outreach engine for events and campaigns.",
                body: "Fundraising Campaigns reuse the same wave-based engine that fills events — calibrated waves, not mass-blast spam that burns goodwill.",
              },
              {
                title: "One phone number. One inbox. One bill.",
                body: "Replace four tools and the spreadsheet with one $99/mo subscription. Your supporters reply right in their texts. No app, no link, no install.",
              },
              {
                title: "Save up to 90% of your time.",
                body: "Coordinators get hours back every week. That time goes back to the work you actually started the non-profit to do.",
              },
            ].map((feat) => (
              <li key={feat.title} className="flex gap-3">
                <CheckCircle2 className="mt-1 h-5 w-5 flex-shrink-0 text-[#7BA9F0]" />
                <div>
                  <div className="font-semibold text-white">{feat.title}</div>
                  <div className="mt-0.5 text-sm leading-relaxed text-zinc-400">
                    {feat.body}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </div>
        <PlatformConsolidationVisual />
      </div>
    </section>
  );
}

function PlatformConsolidationVisual() {
  const replaced = [
    { icon: Users, label: "Volunteer signups" },
    { icon: Heart, label: "Donation page" },
    { icon: Mail, label: "Email blasts" },
    { icon: Sheet, label: "Spreadsheet" },
  ];
  return (
    <div className="rounded-2xl border border-zinc-700/60 bg-gradient-to-br from-zinc-900 via-[#13213b] to-zinc-900 p-7 shadow-2xl">
      <div className="text-center text-[10px] uppercase tracking-[0.2em] text-zinc-500">
        Replaces
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        {replaced.map((tool) => (
          <div
            key={tool.label}
            className="flex items-center gap-2 rounded-lg border border-zinc-700/70 bg-zinc-900/70 px-3 py-3 text-zinc-400"
          >
            <tool.icon className="h-4 w-4 flex-shrink-0 opacity-70" />
            <span className="text-sm line-through decoration-zinc-500 decoration-2">
              {tool.label}
            </span>
          </div>
        ))}
      </div>

      <div className="my-4 flex justify-center">
        <ArrowDown className="h-7 w-7 text-[#7BA9F0]" strokeWidth={2.5} />
      </div>

      <div className="rounded-xl border border-[#7BA9F0]/40 bg-gradient-to-br from-[#1c2d4a] to-[#0F172A] p-5 shadow-lg">
        <div className="flex items-center justify-center gap-2">
          <Sparkles className="h-5 w-5 text-[#7BA9F0]" />
          <span className="text-xl font-bold tracking-tight text-white">
            mustr
          </span>
        </div>
        <div className="mt-1 text-center text-xs text-zinc-400">
          One inbox · one phone number · one bill
        </div>
        <div className="mt-4 flex flex-wrap justify-center gap-1.5">
          {["Volunteers", "Donors", "Outreach", "Reporting"].map((cap) => (
            <span
              key={cap}
              className="rounded-full border border-[#7BA9F0]/30 bg-[#1c2d4a]/60 px-2.5 py-0.5 text-[10px] font-medium text-zinc-200"
            >
              {cap}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

const INTEGRATIONS = [
  "Twilio",
  "Anthropic Claude",
  "Stripe",
  "Google Calendar",
  "Salesforce",
  "HubSpot",
  "BambooHR",
  "Airtable",
  "Bloomerang",
  "Zapier",
];

function IntegrationsSection() {
  return (
    <section className="px-6 py-24">
      <div className="mx-auto max-w-6xl text-center">
        <h2 className="text-4xl font-bold tracking-tight">Connect everything</h2>
        <p className="mt-3 text-lg text-zinc-600">
          Plug into the tools you already use.
        </p>
        <div className="mt-10 flex flex-wrap justify-center gap-3">
          {INTEGRATIONS.map((name) => (
            <span
              key={name}
              className="rounded-full border border-zinc-200 bg-white px-4 py-2 text-sm font-medium text-zinc-700 shadow-sm"
            >
              {name}
            </span>
          ))}
        </div>
        <div className="mx-auto mt-12 max-w-3xl rounded-2xl border border-[#E1E9F4] bg-[#F5F8FC] p-6 text-sm leading-relaxed text-zinc-700">
          <Plug className="mx-auto h-6 w-6 text-[#1c2d4a]" />
          <p className="mt-3">
            Or drive <span className="font-semibold text-zinc-900">mustr</span>{" "}
            from Claude Desktop, Cursor, or any AI assistant &mdash; our MCP
            server makes the whole platform programmable.
          </p>
        </div>
      </div>
    </section>
  );
}

const TRUST = [
  {
    word: "Isolated",
    body: "Row-level tenant isolation on every table.",
  },
  {
    word: "Yours",
    body: "Per-tenant Twilio + Stripe Connect — your data, your funds, never commingled.",
  },
  {
    word: "Auditable",
    body: "Every AI decision logged, traceable, and replayable.",
  },
  {
    word: "Guarded",
    body: "Quiet hours, rate limits, crisis detection, A2P 10DLC, SOC 2 path.",
  },
];

function TrustSection() {
  return (
    <section className="bg-zinc-50 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <Shield className="mx-auto h-10 w-10 text-[#1c2d4a]" />
          <h2 className="mt-4 text-4xl font-bold tracking-tight">
            Trust, by design
          </h2>
          <p className="mt-3 text-lg text-zinc-600">
            Nonprofit boards demand it. We built for it.
          </p>
        </div>
        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {TRUST.map((t) => (
            <div
              key={t.word}
              className="rounded-2xl border border-zinc-200 bg-white p-6"
            >
              <p className="text-xl font-bold">{t.word}.</p>
              <p className="mt-2 text-sm leading-relaxed text-zinc-600">
                {t.body}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

const TIERS = [
  {
    name: "Starter",
    price: "$99",
    cadence: "/mo",
    description: "Get your first event filled.",
    features: [
      "Up to 250 volunteers",
      "1,500 SMS / mo",
      "1 user seat",
      "Core agents (Recruiter, Scheduler, Engagement)",
    ],
    cta: "Start free trial",
    accent: false,
  },
  {
    name: "Growth",
    price: "$299",
    cadence: "/mo",
    description: "Most nonprofits start here.",
    features: [
      "Up to 2,000 volunteers",
      "10,000 SMS / mo",
      "5 seats",
      "Donation campaigns",
      "MCP server",
    ],
    cta: "Start free trial",
    accent: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    cadence: "",
    description: "Built for chapters & networks.",
    features: [
      "Unlimited volunteers + SMS",
      "SSO",
      "Dedicated success",
      "Custom integrations",
      "SLA",
    ],
    cta: "Talk to us",
    accent: false,
  },
];

function PricingSection() {
  return (
    <section id="pricing" className="px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-4xl font-bold tracking-tight">
            Simple pricing, no per-volunteer fees
          </h2>
          <p className="mt-3 text-lg text-zinc-600">
            One price. Every agent. Every integration.
          </p>
        </div>
        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {TIERS.map((t) => (
            <div
              key={t.name}
              className={cn(
                "flex flex-col rounded-2xl border p-8",
                t.accent
                  ? "border-[#0F172A] bg-[#0F172A] text-white shadow-xl"
                  : "border-zinc-200 bg-white"
              )}
            >
              <p
                className={cn(
                  "text-sm font-semibold uppercase tracking-wider",
                  t.accent ? "text-[#7BA9F0]" : "text-[#1c2d4a]"
                )}
              >
                {t.name}
              </p>
              <div className="mt-3 flex items-baseline gap-1">
                <span
                  className={cn(
                    "text-4xl font-bold",
                    t.accent ? "text-white" : "text-zinc-900"
                  )}
                >
                  {t.price}
                </span>
                {t.cadence && (
                  <span
                    className={cn(
                      "text-sm",
                      t.accent ? "text-zinc-300" : "text-zinc-500"
                    )}
                  >
                    {t.cadence}
                  </span>
                )}
              </div>
              <p
                className={cn(
                  "mt-2 text-sm",
                  t.accent ? "text-zinc-300" : "text-zinc-500"
                )}
              >
                {t.description}
              </p>
              <ul className="mt-6 flex-1 space-y-2 text-sm">
                {t.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <CheckCircle2
                      className={cn(
                        "mt-0.5 h-4 w-4 flex-shrink-0",
                        t.accent ? "text-[#7BA9F0]" : "text-[#1c2d4a]"
                      )}
                    />
                    <span className={t.accent ? "text-zinc-200" : "text-zinc-700"}>
                      {f}
                    </span>
                  </li>
                ))}
              </ul>
              <a
                href="#cta"
                className={cn(
                  "mt-8 rounded-full px-5 py-2.5 text-center text-sm font-semibold",
                  t.accent
                    ? "bg-white text-[#0F172A] hover:bg-zinc-100"
                    : "bg-[#0F172A] text-white hover:bg-zinc-800"
                )}
              >
                {t.cta}
              </a>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

const FAQS = [
  {
    q: "Do volunteers need an app?",
    a: "No. Everything happens over SMS — they reply like they would to a friend.",
  },
  {
    q: "How do you stay compliant with A2P 10DLC?",
    a: "mustr provisions a per-tenant Twilio subaccount, registers your campaign, and handles consent and opt-outs out of the box.",
  },
  {
    q: "Can we keep our CRM?",
    a: "Yes. Salesforce, HubSpot, BambooHR, Airtable, and others can stay your source of truth — mustr syncs and stays in lane.",
  },
  {
    q: "What if the AI gets it wrong?",
    a: "Every reply has a thumbs-down. Hallucinations get flagged and routed for review. Admins can take over any thread, any time.",
  },
  {
    q: "How fast can we launch?",
    a: "Most orgs run their first event through mustr in under a week.",
  },
  {
    q: "What happens if we cancel?",
    a: "Export everything — conversations, contacts, bookings — in standard formats. We don't hold your data hostage.",
  },
];

function FAQSection() {
  return (
    <section id="faq" className="bg-zinc-50 px-6 py-24">
      <div className="mx-auto max-w-3xl">
        <h2 className="text-4xl font-bold tracking-tight">Frequently asked</h2>
        <div className="mt-10 space-y-4">
          {FAQS.map((f) => (
            <div
              key={f.q}
              className="rounded-2xl border border-zinc-200 bg-white p-6"
            >
              <p className="font-semibold text-zinc-900">{f.q}</p>
              <p className="mt-2 text-sm leading-relaxed text-zinc-600">{f.a}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function BottomCTA() {
  return (
    <section id="cta" className="px-6 py-24">
      <div className="mx-auto max-w-3xl rounded-3xl bg-gradient-to-br from-[#0F172A] to-[#1f2c50] p-12 text-center text-white shadow-2xl">
        <h2 className="text-4xl font-bold tracking-tight">
          See it run a real event.
        </h2>
        <p className="mt-3 text-lg text-zinc-300">
          15-minute demo. We&apos;ll walk through your next campaign live.
        </p>
        <a
          href="mailto:hello@mustr.app?subject=mustr%20demo"
          className="mt-8 inline-block rounded-full bg-white px-8 py-3 text-sm font-semibold text-[#0F172A] hover:bg-zinc-100"
        >
          Book your demo
        </a>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-zinc-200 bg-white px-6 py-12">
      <div className="mx-auto grid max-w-6xl gap-8 md:grid-cols-4">
        <div>
          <Wordmark className="h-14 w-auto" />
          <p className="mt-4 max-w-xs text-sm text-zinc-500">
            Made for the people who run nonprofits.
          </p>
        </div>
        <FooterCol
          title="Product"
          links={["Features", "Pricing", "MCP server", "Changelog"]}
        />
        <FooterCol
          title="Company"
          links={["About", "Customers", "Blog", "Contact"]}
        />
        <FooterCol
          title="Legal"
          links={["Privacy", "Terms", "DPA", "Security"]}
        />
      </div>
      <p className="mx-auto mt-12 max-w-6xl text-center text-xs text-zinc-400">
        © 2026 mustr
      </p>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <p className="text-sm font-semibold text-zinc-900">{title}</p>
      <ul className="mt-3 space-y-2 text-sm text-zinc-500">
        {links.map((l) => (
          <li key={l}>
            <a href="#" className="hover:text-zinc-900">
              {l}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
