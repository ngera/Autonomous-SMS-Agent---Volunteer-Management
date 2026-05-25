import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, ShieldCheck, User, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { useCustomers } from "@/features/customers/hooks/use-customers";
import {
  getCustomer,
  getCustomerRecentMessages,
} from "@/features/customers/api";
import type { CustomerResponse } from "@/types/api";
import { sendTestMessage, type ToolCallInfo } from "../api";

const STORAGE_KEY = "multi-volunteer-test-selected-phones";
const HISTORY_DAYS = 7;
// UI-only cap. The full message_history is preserved in state (and sent to
// the AI for context) but the transcript only ever shows the most recent
// DISPLAY_MESSAGE_LIMIT items so the panel doesn't fill up.
const DISPLAY_MESSAGE_LIMIT = 10;
// The test_conversation endpoint stores admin-mode chats under this
// fallback phone when the admin user has no real phone configured. Used
// to seed the admin panel's history on page load.
const ADMIN_TEST_PHONE = "+10000000000";
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
  // Debounce the search text before passing it to the API so each keystroke
  // doesn't fire a request. 200ms matches the typing-feels-instant threshold.
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(search.trim()), 200);
    return () => clearTimeout(id);
  }, [search]);
  // Two queries:
  //  - baseCustomers: the rolling "first 100 by name" list used to backfill
  //    saved panels with names + to render the empty state.
  //  - searchCustomers: fires only when there's text in the box, asks the
  //    server to filter so we can find customers OUTSIDE the first 100.
  //    Without this, searching for "Zoe" in a tenant with 300 volunteers
  //    just returns nothing — the previous behavior the user hit.
  const { data: customersData } = useCustomers({ page: 1, page_size: 100 });
  const customers = customersData?.items ?? [];
  const { data: searchData, isFetching: searchFetching } = useCustomers({
    page: 1,
    page_size: 20,
    search: debouncedSearch || undefined,
  });
  const searchHits = debouncedSearch ? (searchData?.items ?? []) : [];

  const [admin, setAdmin] = useState<ChatState>({ ...EMPTY_CHAT });
  const [panels, setPanels] = useState<Record<string, VolunteerChatState>>({});
  const [saveConversation, setSaveConversation] = useState(true);

  const selectedPhones = useMemo(() => Object.keys(panels), [panels]);
  const selectedCount = selectedPhones.length;

  // Rehydrate from localStorage on first mount — runs synchronously and does
  // NOT depend on the customer list, so phones beyond the first page (or for
  // customers not yet in the cached list) are still restored. The name fills
  // in from the customer list when that resolves; history is fetched directly
  // from the server by phone.
  const [hydrated, setHydrated] = useState(false);
  useEffect(() => {
    if (hydrated) return;
    // Admin history is fetched unconditionally — independent of whether
    // any volunteer panels were rehydrated from localStorage. This used
    // to be skipped on a fresh page load (no saved phones) because of an
    // early return below.
    void loadAdminHistory();

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
    if (phones.length > 0) {
      setPanels((prev) => {
        const next = { ...prev };
        for (const phone of phones) {
          if (!next[phone]) {
            next[phone] = {
              ...EMPTY_CHAT,
              phone,
              name: null, // backfilled below
              loadingHistory: true,
            };
          }
        }
        return next;
      });
      phones.forEach((phone) => void loadHistoryForPhone(phone));
      // Resolve each rehydrated phone to a full Contact so we have the name,
      // independent of whether the customer is in the first page of the
      // `useCustomers` cache. Failures are silent — panel will just show
      // the phone number.
      phones.forEach((phone) => {
        getCustomer(phone)
          .then((c) => {
            if (!c.name) return;
            setPanels((prev) => {
              const panel = prev[phone];
              if (!panel || panel.name) return prev;
              return { ...prev, [phone]: { ...panel, name: c.name } };
            });
          })
          .catch((err) => {
            // 404 = the saved phone doesn't belong to the active tenant
            // (common after a tenant switch). Drop the panel so the user
            // isn't stuck looking at a permanently-Unnamed chat with no
            // way to recover short of clearing localStorage by hand.
            // Other errors stay non-fatal — the title falls back to the
            // phone number, the user can still see which thread is which.
            if (err?.response?.status === 404) {
              setPanels((prev) => {
                if (!(phone in prev)) return prev;
                const next = { ...prev };
                delete next[phone];
                return next;
              });
            }
          });
      });
    }
    setHydrated(true);
  }, [hydrated]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadAdminHistory() {
    try {
      const resp = await getCustomerRecentMessages(
        ADMIN_TEST_PHONE,
        HISTORY_DAYS
      );
      const transcript: TranscriptItem[] = resp.messages.map((m, i) => ({
        kind: m.role,
        content: m.content,
        ts: new Date(m.timestamp).getTime() || Date.now() + i,
      }));
      const history = resp.messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));
      setAdmin((prev) => {
        // If the admin has already typed something, don't clobber it —
        // just merge the loaded history before whatever is in transcript.
        if (prev.transcript.length > 0 || prev.history.length > 0) {
          return prev;
        }
        return { ...prev, transcript, history };
      });
    } catch {
      // Silent — admin panel just stays empty if the seed fails.
    }
  }

  // Persist selection: write phone list to localStorage whenever it changes.
  // Guarded behind `hydrated` so the initial render doesn't clobber saved state.
  useEffect(() => {
    if (!hydrated) return;
    if (selectedPhones.length > 0) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(selectedPhones));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [selectedPhones, hydrated]);

  // Backfill names as the customer list resolves — rehydrated panels start
  // with name=null and pick up the real name on the next render where the
  // matching CustomerResponse is available. Considers BOTH the first-100
  // cache and any current search hits so customers beyond page 1 still get
  // their names filled when the user types to find them.
  useEffect(() => {
    if (!hydrated) return;
    const allKnown = [...customers, ...searchHits];
    if (allKnown.length === 0) return;
    setPanels((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const phone of Object.keys(next)) {
        const panel = next[phone];
        if (panel.name) continue;
        const match = allKnown.find((c) => c.phone === phone);
        if (match && match.name && match.name !== panel.name) {
          next[phone] = { ...panel, name: match.name };
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [customers, searchHits, hydrated]);

  // Catch-all: any panel still without a name after both list-based
  // backfills get a targeted lookup. Covers panels added in-session via
  // addVolunteer (where the click-time customer record had name=null) and
  // any rehydrated panel whose first getCustomer call raced.
  //
  // attemptedNameLookups guards against infinite loops: if getCustomer
  // succeeds but returns null name (or 404s), the panel stays without a
  // name AND would otherwise re-trigger this effect forever. The Set
  // records every phone we've already asked about; cleared only when the
  // panel is removed, so a later remove+re-add will re-try.
  const attemptedNameLookups = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (!hydrated) return;
    const presentPhones = new Set(Object.keys(panels));
    // Prune the attempt tracker so removed-then-re-added panels can retry.
    for (const phone of attemptedNameLookups.current) {
      if (!presentPhones.has(phone)) {
        attemptedNameLookups.current.delete(phone);
      }
    }
    const missing = Object.values(panels).filter(
      (p) =>
        !p.name &&
        !p.loadingHistory &&
        !attemptedNameLookups.current.has(p.phone)
    );
    if (missing.length === 0) return;
    missing.forEach((p) => {
      attemptedNameLookups.current.add(p.phone);
      getCustomer(p.phone)
        .then((c) => {
          if (!c.name) return;
          setPanels((prev) => {
            const panel = prev[p.phone];
            if (!panel || panel.name) return prev;
            return { ...prev, [p.phone]: { ...panel, name: c.name } };
          });
        })
        .catch(() => {
          // 404 = stale localStorage from another tenant; the rehydration
          // path's 404 handler already evicts those. Other errors stay
          // silent — title falls back to the phone.
        });
    });
  }, [panels, hydrated]);

  // Poll the admin's sender_type='admin' conversation for backend
  // appends — recruitment planner summaries, daily reports, escalation
  // alerts. Without this poll the test-page admin panel only shows local
  // turn-by-turn replies and misses anything written outside the request.
  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;
    async function pollAdmin() {
      try {
        const resp = await getCustomerRecentMessages(
          ADMIN_TEST_PHONE,
          HISTORY_DAYS
        );
        if (cancelled) return;
        setAdmin((prev) => {
          // Build a Set of (role|content) keys we already know about so
          // we can append only NEW server-side messages without replacing
          // the local transcript (which carries client-side timestamps).
          const seen = new Set(
            prev.transcript.map((m) => `${m.kind}|${m.content}`)
          );
          const newItems: TranscriptItem[] = [];
          for (const m of resp.messages) {
            const key = `${m.role}|${m.content}`;
            if (seen.has(key)) continue;
            seen.add(key);
            newItems.push({
              kind: m.role,
              content: m.content,
              ts: new Date(m.timestamp).getTime() || Date.now(),
            });
          }
          if (newItems.length === 0) return prev;
          return {
            ...prev,
            transcript: [...prev.transcript, ...newItems].sort(
              (a, b) => a.ts - b.ts
            ),
          };
        });
      } catch {
        // ignore — next tick will retry
      }
    }
    const id = setInterval(pollAdmin, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [hydrated]);

  // When the user is searching, prefer the server-side hits (which can
  // reach customers outside the first 100). When the box is empty, use
  // the local cache. Either way, exclude phones already showing as panels.
  const filteredCustomers = useMemo(() => {
    const source = debouncedSearch ? searchHits : customers;
    return source.filter((c) => !panels[c.phone]);
  }, [customers, searchHits, debouncedSearch, panels]);

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
          {search.trim() && (
            <div className="max-h-48 overflow-y-auto rounded-md border">
              {searchFetching && filteredCustomers.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted-foreground">
                  Searching…
                </p>
              ) : filteredCustomers.length === 0 ? (
                <p className="px-3 py-2 text-xs text-muted-foreground">
                  No volunteers match "{search.trim()}". Check the spelling
                  or the active tenant in the top-bar filter.
                </p>
              ) : (
                filteredCustomers.slice(0, 10).map((c) => (
                  <button
                    key={c.phone}
                    type="button"
                    className="flex w-full flex-col items-start px-3 py-2 text-left text-sm hover:bg-accent"
                    onClick={() => addVolunteer(c)}
                  >
                    <span className="font-medium">
                      {(c.name && c.name.trim()) || c.phone}
                    </span>
                    {c.name && c.name.trim() && (
                      <span className="text-xs text-muted-foreground">{c.phone}</span>
                    )}
                  </button>
                ))
              )}
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
              // Fall back to the phone number rather than "Unnamed" — at
              // least the panel is identifiable. The empty-string check
              // handles contacts whose name field is an empty string in
              // the DB (otherwise `"" || ...` still picks the fallback).
              title={(p.name && p.name.trim()) || p.phone}
              subtitle={(p.name && p.name.trim()) ? p.phone : ""}
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
  const inputRef = useRef<HTMLInputElement>(null);
  // Track whether THIS panel was the one that initiated a send, so that only
  // its input gets refocused when pending flips back to false — sending from
  // panel A while typing in panel B should NOT steal focus from B.
  const justSentRef = useRef(false);

  // Auto-scroll to the latest message whenever the transcript grows or a turn finishes.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [transcript.length, pending, loadingHistory]);

  // Refocus the input after a send completes. requestAnimationFrame defers
  // until after the Input has re-enabled (disabled→enabled in the same tick
  // would otherwise leave the cursor blurred).
  useEffect(() => {
    if (!pending && justSentRef.current) {
      justSentRef.current = false;
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [pending]);

  function triggerSend() {
    if (pending || !input.trim()) return;
    justSentRef.current = true;
    onSend();
  }
  return (
    <div className="flex h-[28rem] flex-col overflow-hidden rounded-2xl border border-[#9CADC2] bg-[#D2DBE8] shadow-sm">
      {/* iOS-style contact strip */}
      <div className="flex items-center justify-between gap-2 border-b border-[#9CADC2] bg-[#BCC9DA]/95 px-3 py-2 backdrop-blur">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-full",
              accent === "emerald"
                ? "bg-emerald-200 text-emerald-900 dark:bg-emerald-900 dark:text-emerald-200"
                : "bg-zinc-200 text-zinc-700 dark:bg-zinc-700 dark:text-zinc-200"
            )}
          >
            {icon}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold leading-tight text-black">{title}</p>
            {subtitle && (
              <p className="truncate text-[11px] leading-tight text-black">
                {subtitle}
              </p>
            )}
          </div>
        </div>
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            aria-label="Close conversation"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[#3f4a5c] hover:bg-[#9CADC2]"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 space-y-1.5 overflow-y-auto bg-[#D2DBE8] px-3 py-3">
        {loadingHistory && transcript.length === 0 ? (
          <p className="py-8 text-center text-xs text-muted-foreground">
            Loading the last 7 days of messages…
          </p>
        ) : transcript.length === 0 ? (
          <p className="py-8 text-center text-xs text-muted-foreground">
            {emptyHint}
          </p>
        ) : (
          transcript
            .slice(-DISPLAY_MESSAGE_LIMIT)
            .map((item, i) => <TranscriptRow key={i} item={item} />)
        )}
        {transcript.length > DISPLAY_MESSAGE_LIMIT && (
          <p className="text-center text-[10px] text-muted-foreground">
            Showing last {DISPLAY_MESSAGE_LIMIT} of {transcript.length} messages
          </p>
        )}
        {pending && <TypingBubble />}
        <div ref={bottomRef} />
      </div>

      {/* iMessage compose bar */}
      <div className="flex items-center gap-2 border-t border-[#9CADC2] bg-[#BCC9DA]/95 px-2 py-2 backdrop-blur">
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              triggerSend();
            }
          }}
          placeholder={placeholder || "iMessage"}
          disabled={pending}
          className="h-8 flex-1 rounded-full border border-[#9CADC2] bg-[#FBF6EE] px-3 text-sm text-[#1c1c1e] placeholder:text-[#7e8a9c] outline-none focus:border-[#6b7e96] disabled:opacity-50"
        />
        <button
          type="button"
          onClick={triggerSend}
          disabled={!input.trim() || pending}
          aria-label="Send"
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-full transition-colors",
            input.trim() && !pending
              ? "bg-[#007AFF] text-white hover:bg-[#0066d6]"
              : "bg-[#9CADC2] text-white"
          )}
        >
          <ArrowUp className="h-4 w-4" strokeWidth={3} />
        </button>
      </div>
    </div>
  );
}

function TranscriptRow({ item }: { item: TranscriptItem }) {
  const isUser = item.kind === "user";
  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[78%] whitespace-pre-wrap border border-[#9CADC2] px-3 py-1.5 text-sm leading-snug text-[#1c1c1e]",
          isUser
            ? "rounded-[18px] rounded-br-[4px] bg-[#FBF6EE]"
            : "rounded-[18px] rounded-bl-[4px] bg-[#FBF6EE]"
        )}
      >
        {item.content}
      </div>
    </div>
  );
}

function TypingBubble() {
  return (
    <div className="flex justify-start">
      <div className="flex items-end gap-1 rounded-[18px] rounded-bl-[4px] border border-[#9CADC2] bg-[#FBF6EE] px-3 py-2">
        <span
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-500 dark:bg-zinc-400"
          style={{ animationDelay: "0ms" }}
        />
        <span
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-500 dark:bg-zinc-400"
          style={{ animationDelay: "150ms" }}
        />
        <span
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-zinc-500 dark:bg-zinc-400"
          style={{ animationDelay: "300ms" }}
        />
      </div>
    </div>
  );
}
