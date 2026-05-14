import { useEffect, useMemo, useRef, useState } from "react";
import { Bot, Send, ShieldCheck, User, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { useCustomers } from "@/features/customers/hooks/use-customers";
import { getCustomerRecentMessages } from "@/features/customers/api";
import type { CustomerResponse } from "@/types/api";
import { sendTestMessage, type ToolCallInfo } from "../api";

const STORAGE_KEY = "multi-volunteer-test-selected-phones";
const HISTORY_DAYS = 7;
const POLL_INTERVAL_MS = 10_000; // refresh open panels for incoming announcements
const POLL_DEDUPE_WINDOW_MS = 5_000; // treat near-identical timestamps as the same message

type TranscriptKind = "user" | "assistant";

interface TranscriptItem {
  kind: TranscriptKind;
  content: string;
  ts: number;
}

interface ChatState {
  transcript: TranscriptItem[];
  history: { role: string; content: string }[];
  input: string;
  pending: boolean;
}

interface VolunteerChatState extends ChatState {
  phone: string;
  name: string | null;
  loadingHistory: boolean;
}

const EMPTY_CHAT: ChatState = {
  transcript: [],
  history: [],
  input: "",
  pending: false,
};

export function MultiVolunteerTestPage() {
  const [search, setSearch] = useState("");
  const { data: customersData } = useCustomers({ page: 1, page_size: 100 });
  const customers = customersData?.items ?? [];

  const [admin, setAdmin] = useState<ChatState>({ ...EMPTY_CHAT });
  const [panels, setPanels] = useState<Record<string, VolunteerChatState>>({});
  const [saveConversation, setSaveConversation] = useState(true);

  const selectedPhones = useMemo(() => Object.keys(panels), [panels]);
  const selectedCount = selectedPhones.length;

  // Persist selection: write phone list to localStorage whenever it changes.
  // Skip until we've finished hydrating, so the first render doesn't clobber saved state.
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    if (!hydrated) return;
    if (selectedPhones.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedPhones));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [selectedPhones, hydrated]);

  // Rehydrate selection once customers have loaded — match saved phones against the
  // current tenant's customer list, seed panels with loadingHistory, then fetch each.
  useEffect(() => {
    if (hydrated) return;
    if (customersData === undefined) return; // still loading
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      setHydrated(true);
      return;
    }
    let phones: string[] = [];
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) phones = parsed.filter((p) => typeof p === "string");
    } catch {
      phones = [];
    }
    const matched = phones
      .map((p) => customers.find((c) => c.phone === p))
      .filter((c): c is CustomerResponse => !!c);
    if (matched.length > 0) {
      setPanels((prev) => {
        const next = { ...prev };
        for (const c of matched) {
          if (!next[c.phone]) {
            next[c.phone] = {
              ...EMPTY_CHAT,
              phone: c.phone,
              name: c.name,
              loadingHistory: true,
            };
          }
        }
        return next;
      });
      // Fire history fetch for each rehydrated volunteer (no need to await)
      matched.forEach((c) => void loadHistoryForPhone(c.phone));
    }
    setHydrated(true);
  }, [customersData, customers, hydrated]); // eslint-disable-line react-hooks/exhaustive-deps

  const filteredCustomers = useMemo(() => {
    const q = search.trim().toLowerCase();
    return customers.filter((c) => {
      if (panels[c.phone]) return false;
      if (!q) return true;
      return (
        (c.name && c.name.toLowerCase().includes(q)) || c.phone.includes(q)
      );
    });
  }, [customers, search, panels]);

  async function loadHistoryForPhone(phone: string) {
    try {
      const resp = await getCustomerRecentMessages(phone, HISTORY_DAYS);
      const transcript: TranscriptItem[] = resp.messages.map((m, i) => ({
        kind: m.role,
        content: m.content,
        ts: new Date(m.timestamp).getTime() || Date.now() + i,
      }));
      const history = resp.messages.map((m) => ({ role: m.role, content: m.content }));
      setPanels((prev) => {
        const panel = prev[phone];
        if (!panel) return prev;
        // If the admin has already started typing/sending against this volunteer,
        // don't overwrite — just clear the loading flag.
        if (panel.transcript.length > 0 || panel.history.length > 0) {
          return { ...prev, [phone]: { ...panel, loadingHistory: false } };
        }
        return {
          ...prev,
          [phone]: { ...panel, transcript, history, loadingHistory: false },
        };
      });
    } catch {
      setPanels((prev) =>
        prev[phone]
          ? { ...prev, [phone]: { ...prev[phone], loadingHistory: false } }
          : prev
      );
    }
  }

  // Poll each open panel's server-side history every POLL_INTERVAL_MS so that
  // announcements (or any other backend-driven appends) show up without the
  // admin having to re-open the panel. Dedupes by role + content + a small
  // timestamp window so in-session messages with client-side timestamps don't
  // get re-appended once they're saved server-side with a slightly different
  // server timestamp.
  const phoneListKey = useMemo(
    () => Object.keys(panels).sort().join("|"),
    [panels]
  );

  useEffect(() => {
    if (!phoneListKey) return;
    let cancelled = false;

    async function pollOne(phone: string) {
      try {
        const resp = await getCustomerRecentMessages(phone, HISTORY_DAYS);
        if (cancelled) return;
        setPanels((prev) => {
          const panel = prev[phone];
          if (!panel || panel.loadingHistory) return prev;
          const newItems: TranscriptItem[] = [];
          for (const m of resp.messages) {
            const serverTs = new Date(m.timestamp).getTime();
            const dup = panel.transcript.some(
              (t) =>
                t.kind === m.role &&
                t.content === m.content &&
                Math.abs(t.ts - serverTs) < POLL_DEDUPE_WINDOW_MS
            );
            if (!dup) {
              newItems.push({ kind: m.role, content: m.content, ts: serverTs });
            }
          }
          if (newItems.length === 0) return prev;
          return {
            ...prev,
            [phone]: {
              ...panel,
              transcript: [...panel.transcript, ...newItems].sort(
                (a, b) => a.ts - b.ts
              ),
              history: [
                ...panel.history,
                ...newItems.map((n) => ({
                  role: n.kind,
                  content: n.content,
                })),
              ],
            },
          };
        });
      } catch {
        // Silent — try again on the next tick.
      }
    }

    function tick() {
      // Skip while the tab is in the background to save bandwidth.
      if (document.hidden) return;
      const phones = phoneListKey.split("|").filter(Boolean);
      for (const phone of phones) {
        void pollOne(phone);
      }
    }

    const intervalId = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [phoneListKey]);

  function addVolunteer(c: CustomerResponse) {
    setPanels((prev) => ({
      ...prev,
      [c.phone]: {
        ...EMPTY_CHAT,
        phone: c.phone,
        name: c.name,
        loadingHistory: true,
      },
    }));
    setSearch("");
    void loadHistoryForPhone(c.phone);
  }

  function removeVolunteer(phone: string) {
    setPanels((prev) => {
      const next = { ...prev };
      delete next[phone];
      return next;
    });
  }

  function clearAll() {
    setPanels({});
  }

  function patchVolunteer(phone: string, patch: Partial<VolunteerChatState>) {
    setPanels((prev) =>
      prev[phone] ? { ...prev, [phone]: { ...prev[phone], ...patch } } : prev
    );
  }

  function appendVolunteerItems(phone: string, items: TranscriptItem[]) {
    setPanels((prev) => {
      if (!prev[phone]) return prev;
      return {
        ...prev,
        [phone]: {
          ...prev[phone],
          transcript: [...prev[phone].transcript, ...items],
        },
      };
    });
  }

  /**
   * Mirror outbound SMS that the admin's tool calls would have produced into
   * every open volunteer panel that is in the recipient list. Two shapes are
   * supported because each tool emits its preview differently:
   *
   *   send_announcement → one body, many recipients (preview_message + preview_recipients)
   *   cancel_event_bookings → per-volunteer body (preview_messages: [{phone, body}])
   *
   * Each preview is appended to the panel's transcript (so the admin sees
   * exactly what each selected volunteer would have received) and to the
   * panel's history (so a later volunteer reply is context-aware).
   */
  function applyOutboundSmsPreviews(toolCalls: ToolCallInfo[]) {
    type Preview = { phone: string; body: string; label: string };
    const previews: Preview[] = [];
    for (const call of toolCalls) {
      let parsed: unknown;
      try {
        parsed = JSON.parse(call.output);
      } catch {
        continue;
      }
      if (!parsed || typeof parsed !== "object") continue;
      const result = parsed as {
        test_mode?: boolean;
        preview_message?: string;
        preview_recipients?: string[];
        preview_messages?: Array<{ phone?: string; body?: string }>;
      };
      if (!result.test_mode) continue;

      if (
        call.tool === "send_announcement" &&
        result.preview_message &&
        Array.isArray(result.preview_recipients)
      ) {
        for (const phone of result.preview_recipients) {
          if (typeof phone === "string") {
            previews.push({
              phone,
              body: result.preview_message,
              label: "📣 Announcement",
            });
          }
        }
      }

      if (Array.isArray(result.preview_messages)) {
        for (const m of result.preview_messages) {
          if (m?.phone && m?.body) {
            previews.push({
              phone: m.phone,
              body: m.body,
              label: call.tool === "cancel_event_bookings" ? "✖ Booking cancelled" : "📨 SMS",
            });
          }
        }
      }
    }
    if (previews.length === 0) return;

    const ts = Date.now();
    setPanels((prev) => {
      const next = { ...prev };
      for (const { phone, body, label } of previews) {
        if (!next[phone]) continue;
        const text = `${label}\n${body}`;
        next[phone] = {
          ...next[phone],
          transcript: [
            ...next[phone].transcript,
            { kind: "assistant", content: text, ts },
          ],
          history: [
            ...next[phone].history,
            { role: "assistant", content: text },
          ],
        };
      }
      return next;
    });
  }

  async function handleSend(opts: {
    text: string;
    mode: "customer" | "admin";
    phone?: string;
    history: { role: string; content: string }[];
    onAppendUser: (item: TranscriptItem) => void;
    onAppendAssistant: (item: TranscriptItem, replyText: string) => void;
    onPending: (pending: boolean) => void;
    onError: (item: TranscriptItem) => void;
    onToolCalls?: (toolCalls: ToolCallInfo[]) => void;
  }) {
    const userTs = Date.now();
    opts.onPending(true);
    opts.onAppendUser({ kind: "user", content: opts.text, ts: userTs });
    try {
      const result = await sendTestMessage({
        message: opts.text,
        mode: opts.mode,
        history: opts.history,
        phone: opts.phone,
        save_conversation: saveConversation,
      });
      opts.onAppendAssistant(
        { kind: "assistant", content: result.reply, ts: Date.now() },
        result.reply
      );
      if (opts.onToolCalls && result.tool_calls?.length) {
        opts.onToolCalls(result.tool_calls);
      }
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (err as Error)?.message ||
        "Request failed";
      opts.onError({
        kind: "assistant",
        content: `[error] ${detail}`,
        ts: Date.now(),
      });
    } finally {
      opts.onPending(false);
    }
  }

  async function handleAdminSend() {
    const text = admin.input.trim();
    if (!text || admin.pending) return;
    const historyAtSend = admin.history;
    setAdmin((prev) => ({ ...prev, input: "" }));
    await handleSend({
      text,
      mode: "admin",
      history: historyAtSend,
      onPending: (pending) => setAdmin((prev) => ({ ...prev, pending })),
      onAppendUser: (item) =>
        setAdmin((prev) => ({
          ...prev,
          transcript: [...prev.transcript, item],
        })),
      onAppendAssistant: (item, replyText) =>
        setAdmin((prev) => ({
          ...prev,
          transcript: [...prev.transcript, item],
          history: [
            ...prev.history,
            { role: "user", content: text },
            { role: "assistant", content: replyText },
          ],
        })),
      onError: (item) =>
        setAdmin((prev) => ({
          ...prev,
          transcript: [...prev.transcript, item],
        })),
      onToolCalls: applyOutboundSmsPreviews,
    });
  }

  async function handleVolunteerSend(phone: string) {
    const panel = panels[phone];
    if (!panel) return;
    const text = panel.input.trim();
    if (!text || panel.pending) return;
    const historyAtSend = panel.history;
    patchVolunteer(phone, { input: "" });
    await handleSend({
      text,
      mode: "customer",
      phone,
      history: historyAtSend,
      onPending: (pending) => patchVolunteer(phone, { pending }),
      onAppendUser: (item) => appendVolunteerItems(phone, [item]),
      onAppendAssistant: (item, replyText) => {
        appendVolunteerItems(phone, [item]);
        setPanels((prev) => {
          if (!prev[phone]) return prev;
          return {
            ...prev,
            [phone]: {
              ...prev[phone],
              history: [
                ...prev[phone].history,
                { role: "user", content: text },
                { role: "assistant", content: replyText },
              ],
            },
          };
        });
      },
      onError: (item) => appendVolunteerItems(phone, [item]),
    });
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Multi-Volunteer SMS Test</h1>
          <p className="text-sm text-muted-foreground">
            Run independent test threads — one for the admin, one per selected
            volunteer. No real SMS is sent.
          </p>
        </div>
        <label className="flex cursor-pointer items-center gap-2 rounded-md border bg-card px-3 py-2 text-sm">
          <Switch
            checked={saveConversation}
            onCheckedChange={setSaveConversation}
          />
          <Label className="cursor-pointer text-sm font-medium">Save conversations</Label>
        </label>
      </div>

      {/* Volunteer picker */}
      <Card>
        <CardHeader className="py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-sm font-medium">
              Selected volunteers ({selectedCount})
            </CardTitle>
            {selectedCount > 0 && (
              <Button size="sm" variant="ghost" onClick={clearAll}>
                Clear all
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {selectedCount > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {selectedPhones.map((phone) => {
                const p = panels[phone];
                return (
                  <Badge
                    key={phone}
                    variant="secondary"
                    className="cursor-pointer"
                    onClick={() => removeVolunteer(phone)}
                  >
                    {p.name || phone}
                    <X className="ml-1 h-3 w-3" />
                  </Badge>
                );
              })}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">
              No volunteers selected yet.
            </p>
          )}
          <div className="flex gap-2">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search volunteers by name or phone..."
              className="h-9 max-w-md"
            />
          </div>
          {search.trim() && filteredCustomers.length > 0 && (
            <div className="max-h-48 overflow-y-auto rounded-md border">
              {filteredCustomers.slice(0, 10).map((c) => (
                <button
                  key={c.phone}
                  type="button"
                  className="flex w-full flex-col items-start px-3 py-2 text-left text-sm hover:bg-accent"
                  onClick={() => addVolunteer(c)}
                >
                  <span className="font-medium">{c.name || "Unnamed"}</span>
                  <span className="text-xs text-muted-foreground">{c.phone}</span>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Chat panels */}
      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <ChatPanel
          title="Admin"
          subtitle="Admin → System (admin tools)"
          icon={<ShieldCheck className="h-3.5 w-3.5" />}
          accent="emerald"
          input={admin.input}
          transcript={admin.transcript}
          pending={admin.pending}
          placeholder="Type as the admin..."
          emptyHint="Try: 'show today's schedule', 'block next Monday', 'list all services'"
          onInputChange={(v) => setAdmin((prev) => ({ ...prev, input: v }))}
          onSend={handleAdminSend}
        />
        {selectedPhones.map((phone) => {
          const p = panels[phone];
          return (
            <ChatPanel
              key={phone}
              title={p.name || "Unnamed"}
              subtitle={p.phone}
              icon={<User className="h-3.5 w-3.5" />}
              accent="default"
              input={p.input}
              transcript={p.transcript}
              pending={p.pending}
              loadingHistory={p.loadingHistory}
              placeholder="Type as this volunteer..."
              emptyHint="Try: 'what services do you offer?', 'any openings tomorrow?'"
              onInputChange={(v) => patchVolunteer(phone, { input: v })}
              onSend={() => handleVolunteerSend(phone)}
              onRemove={() => removeVolunteer(phone)}
            />
          );
        })}
      </div>

      {selectedCount === 0 && (
        <p className="pt-2 text-center text-xs text-muted-foreground">
          Add volunteers above to open additional test threads alongside the admin.
        </p>
      )}
    </div>
  );
}

interface ChatPanelProps {
  title: string;
  subtitle: string | null;
  icon: React.ReactNode;
  accent: "default" | "emerald";
  input: string;
  transcript: TranscriptItem[];
  pending: boolean;
  loadingHistory?: boolean;
  placeholder: string;
  emptyHint: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onRemove?: () => void;
}

function ChatPanel({
  title,
  subtitle,
  icon,
  accent,
  input,
  transcript,
  pending,
  loadingHistory = false,
  placeholder,
  emptyHint,
  onInputChange,
  onSend,
  onRemove,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the latest message whenever the transcript grows or a turn finishes.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [transcript.length, pending, loadingHistory]);
  return (
    <Card
      className={cn(
        "flex h-[28rem] flex-col",
        accent === "emerald" &&
          "border-emerald-300 dark:border-emerald-900"
      )}
    >
      <CardHeader
        className={cn(
          "flex flex-row items-center justify-between border-b py-2",
          accent === "emerald" && "bg-emerald-50/60 dark:bg-emerald-950/30"
        )}
      >
        <div className="flex min-w-0 items-center gap-2">
          <span
            className={cn(
              "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
              accent === "emerald"
                ? "bg-emerald-200 text-emerald-900 dark:bg-emerald-900 dark:text-emerald-200"
                : "bg-primary/10 text-primary"
            )}
          >
            {icon}
          </span>
          <div className="min-w-0">
            <CardTitle className="truncate text-sm font-medium">
              {title}
            </CardTitle>
            {subtitle && (
              <p className="truncate text-xs text-muted-foreground">{subtitle}</p>
            )}
          </div>
        </div>
        {onRemove && (
          <Button size="icon" variant="ghost" className="h-7 w-7" onClick={onRemove}>
            <X className="h-3.5 w-3.5" />
          </Button>
        )}
      </CardHeader>
      <CardContent className="flex-1 space-y-2 overflow-y-auto p-3">
        {loadingHistory && transcript.length === 0 ? (
          <p className="py-8 text-center text-xs text-muted-foreground">
            Loading the last 7 days of messages…
          </p>
        ) : transcript.length === 0 ? (
          <p className="py-8 text-center text-xs text-muted-foreground">
            {emptyHint}
          </p>
        ) : (
          transcript.map((item, i) => <TranscriptRow key={i} item={item} />)
        )}
        {pending && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Bot className="h-3.5 w-3.5" />
            <span className="inline-flex gap-0.5">
              <span className="animate-bounce" style={{ animationDelay: "0ms" }}>
                .
              </span>
              <span className="animate-bounce" style={{ animationDelay: "150ms" }}>
                .
              </span>
              <span className="animate-bounce" style={{ animationDelay: "300ms" }}>
                .
              </span>
            </span>
          </div>
        )}
        <div ref={bottomRef} />
      </CardContent>
      <div className="border-t p-2">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            placeholder={placeholder}
            className="h-8 text-sm"
            disabled={pending}
          />
          <Button
            size="sm"
            onClick={onSend}
            disabled={!input.trim() || pending}
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

function TranscriptRow({ item }: { item: TranscriptItem }) {
  const isUser = item.kind === "user";
  return (
    <div
      className={cn(
        "flex items-start gap-2 text-xs",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10">
          <Bot className="h-3 w-3 text-primary" />
        </div>
      )}
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap rounded-md px-2.5 py-1.5",
          isUser ? "bg-primary text-primary-foreground" : "bg-muted"
        )}
      >
        {item.content}
      </div>
      {isUser && (
        <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary">
          <User className="h-3 w-3 text-primary-foreground" />
        </div>
      )}
    </div>
  );
}
