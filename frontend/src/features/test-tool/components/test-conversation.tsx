import { useState, useRef, useEffect, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Send, RotateCcw, User, Bot, Wrench, ChevronDown, ChevronRight, Search, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useTestConversation } from "../hooks/use-test-conversation";
import { useCustomers } from "@/features/customers/hooks/use-customers";
import type { ToolCallInfo } from "../api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  toolCalls?: ToolCallInfo[];
}

export function TestConversation() {
  const [mode, setMode] = useState<"customer" | "admin">("customer");
  const [selectedPhone, setSelectedPhone] = useState("");
  const [saveConversation, setSaveConversation] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [expandedTools, setExpandedTools] = useState<Record<number, boolean>>({});
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [volunteerSearch, setVolunteerSearch] = useState("");
  const [volunteerDropdownOpen, setVolunteerDropdownOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const volunteerDropdownRef = useRef<HTMLDivElement>(null);
  const volunteerListRef = useRef<HTMLDivElement>(null);

  const mutation = useTestConversation();
  const { data: customersData } = useCustomers({ page: 1, page_size: 100 });
  const customers = customersData?.items ?? [];

  const selectedCustomer = useMemo(
    () => customers.find((c) => c.phone === selectedPhone),
    [customers, selectedPhone],
  );

  const filteredCustomers = useMemo(() => {
    if (!volunteerSearch.trim()) return customers;
    const q = volunteerSearch.toLowerCase();
    return customers.filter(
      (c) =>
        (c.name && c.name.toLowerCase().includes(q)) ||
        c.phone.includes(q),
    );
  }, [customers, volunteerSearch]);

  // Reset highlight when filtered list changes
  useEffect(() => {
    setHighlightedIndex(-1);
  }, [filteredCustomers.length, volunteerSearch]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (volunteerDropdownRef.current && !volunteerDropdownRef.current.contains(e.target as Node)) {
        setVolunteerDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleReset() {
    setMessages([]);
    setExpandedTools({});
    setInput("");
    setSelectedPhone("");
    inputRef.current?.focus();
  }

  function handleModeChange(newMode: "customer" | "admin") {
    setMode(newMode);
    handleReset();
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || mutation.isPending) return;

    const userMsg: ChatMessage = { role: "user", content: text };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");

    // Build history (exclude the current message)
    const history = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const result = await mutation.mutateAsync({
        message: text,
        mode,
        history,
        phone: mode === "customer" && selectedPhone ? selectedPhone : undefined,
        save_conversation: saveConversation,
      });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.reply,
          toolCalls: result.tool_calls.length > 0 ? result.tool_calls : undefined,
        },
      ]);
    } catch (err: unknown) {
      let errorMsg = "Error: Failed to get a response.";
      if (err && typeof err === "object" && "response" in err) {
        const axiosErr = err as { response?: { status?: number; data?: { detail?: string } } };
        const detail = axiosErr.response?.data?.detail;
        const status = axiosErr.response?.status;
        if (detail) {
          errorMsg = `Error (${status}): ${detail}`;
        } else if (status) {
          errorMsg = `Error: Server returned ${status}`;
        }
      } else if (err instanceof Error) {
        errorMsg = `Error: ${err.message}`;
      }
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: errorMsg,
        },
      ]);
    } finally {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function toggleToolExpand(msgIndex: number) {
    setExpandedTools((prev) => ({
      ...prev,
      [msgIndex]: !prev[msgIndex],
    }));
  }

  function formatToolOutput(output: string): string {
    try {
      return JSON.stringify(JSON.parse(output), null, 2);
    } catch {
      return output;
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Controls */}
      <Card className="mb-4 overflow-visible">
        <CardContent className="py-3 overflow-visible">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Label className="text-sm font-medium whitespace-nowrap">Mode</Label>
              <Select value={mode} onValueChange={(v) => handleModeChange(v as "customer" | "admin")}>
                <SelectTrigger className="w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="customer">Volunteer</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {mode === "customer" && (
              <div className="flex items-center gap-2">
                <Label className="text-sm font-medium whitespace-nowrap">
                  Volunteer
                </Label>
                <div className="relative w-72" ref={volunteerDropdownRef}>
                  <div
                    className="flex items-center gap-2 h-9 rounded-md border border-input bg-background px-3 text-sm cursor-pointer hover:bg-accent/50 transition-colors"
                    onClick={() => setVolunteerDropdownOpen((o) => !o)}
                  >
                    <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    {selectedPhone && !volunteerDropdownOpen ? (
                      <span className="flex-1 truncate">
                        {selectedCustomer?.name || "Unnamed"} — {selectedPhone}
                      </span>
                    ) : (
                      <input
                        className="flex-1 bg-transparent outline-none placeholder:text-muted-foreground text-sm"
                        placeholder="Search volunteers..."
                        value={volunteerSearch}
                        onChange={(e) => {
                          setVolunteerSearch(e.target.value);
                          setVolunteerDropdownOpen(true);
                        }}
                        onFocus={() => setVolunteerDropdownOpen(true)}
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={(e) => {
                          if (!volunteerDropdownOpen || filteredCustomers.length === 0) return;
                          if (e.key === "ArrowDown") {
                            e.preventDefault();
                            setHighlightedIndex((prev) => {
                              const next = prev < filteredCustomers.length - 1 ? prev + 1 : 0;
                              volunteerListRef.current?.children[next]?.scrollIntoView({ block: "nearest" });
                              return next;
                            });
                          } else if (e.key === "ArrowUp") {
                            e.preventDefault();
                            setHighlightedIndex((prev) => {
                              const next = prev > 0 ? prev - 1 : filteredCustomers.length - 1;
                              volunteerListRef.current?.children[next]?.scrollIntoView({ block: "nearest" });
                              return next;
                            });
                          } else if (e.key === "Enter" && highlightedIndex >= 0) {
                            e.preventDefault();
                            const c = filteredCustomers[highlightedIndex];
                            setSelectedPhone(c.phone);
                            setVolunteerSearch("");
                            setVolunteerDropdownOpen(false);
                            setHighlightedIndex(-1);
                            setMessages([]);
                            setExpandedTools({});
                          } else if (e.key === "Escape") {
                            setVolunteerDropdownOpen(false);
                            setHighlightedIndex(-1);
                          }
                        }}
                      />
                    )}
                    {selectedPhone && (
                      <button
                        className="text-muted-foreground hover:text-foreground"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedPhone("");
                          setVolunteerSearch("");
                          setMessages([]);
                          setExpandedTools({});
                        }}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                  {volunteerDropdownOpen && (
                    <div ref={volunteerListRef} className="absolute z-50 mt-1 w-full rounded-md border bg-popover shadow-md max-h-56 overflow-y-auto">
                      {filteredCustomers.length === 0 ? (
                        <div className="px-3 py-4 text-sm text-center text-muted-foreground">
                          {customers.length === 0
                            ? "No volunteers found. Select a tenant first."
                            : "No matching volunteers."}
                        </div>
                      ) : (
                        filteredCustomers.map((c, idx) => (
                          <button
                            key={c.phone}
                            className={cn(
                              "flex flex-col w-full px-3 py-2 text-left text-sm hover:bg-accent transition-colors",
                              c.phone === selectedPhone && "bg-accent",
                              idx === highlightedIndex && "bg-accent"
                            )}
                            onMouseEnter={() => setHighlightedIndex(idx)}
                            onClick={() => {
                              setSelectedPhone(c.phone);
                              setVolunteerSearch("");
                              setVolunteerDropdownOpen(false);
                              setMessages([]);
                              setExpandedTools({});
                            }}
                          >
                            <span className="font-medium">{c.name || "Unnamed"}</span>
                            <span className="text-xs text-muted-foreground">{c.phone}</span>
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="flex items-center gap-2 ml-auto">
              <div className="flex items-center gap-1.5">
                <Switch
                  checked={saveConversation}
                  onCheckedChange={setSaveConversation}
                />
                <Label className="text-sm font-medium whitespace-nowrap">Save</Label>
              </div>
              <Badge variant={mode === "customer" ? "default" : "secondary"}>
                {mode === "customer" ? "6 tools" : "13 tools"}
              </Badge>
              <Button variant="outline" size="sm" onClick={handleReset}>
                <RotateCcw className="h-4 w-4 mr-1" />
                Reset
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Chat area */}
      <Card className="flex-1 flex flex-col min-h-0">
        <CardHeader className="py-3 border-b">
          <CardTitle className="text-sm font-medium">
            {mode === "customer" ? "Volunteer SMS Simulation" : "Admin SMS Simulation"}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              <div className="text-center space-y-2">
                <p>
                  {mode === "customer"
                    ? "Simulate a volunteer SMS conversation. Try booking, checking availability, or cancelling."
                    : "Simulate an admin SMS conversation. Try searching bookings, managing services, or sending announcements."}
                </p>
                <div className="flex flex-wrap gap-1 justify-center">
                  {mode === "customer" ? (
                    <>
                      <Button variant="outline" size="sm" className="text-xs h-6" onClick={() => setInput("What services do you offer?")}>What services do you offer?</Button>
                      <Button variant="outline" size="sm" className="text-xs h-6" onClick={() => setInput("Do you have any openings tomorrow?")}>Any openings tomorrow?</Button>
                      <Button variant="outline" size="sm" className="text-xs h-6" onClick={() => setInput("I'd like to book an appointment")}>Book an appointment</Button>
                      <Button variant="outline" size="sm" className="text-xs h-6" onClick={() => setInput("What are my upcoming appointments?")}>My appointments</Button>
                    </>
                  ) : (
                    <>
                      <Button variant="outline" size="sm" className="text-xs h-6" onClick={() => setInput("Show me today's schedule")}>Today's schedule</Button>
                      <Button variant="outline" size="sm" className="text-xs h-6" onClick={() => setInput("Search bookings for tomorrow")}>Search bookings</Button>
                      <Button variant="outline" size="sm" className="text-xs h-6" onClick={() => setInput("Block next Monday for maintenance")}>Block a date</Button>
                      <Button variant="outline" size="sm" className="text-xs h-6" onClick={() => setInput("List all services")}>List services</Button>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "justify-start")}>
              {msg.role === "assistant" && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
              )}
              <div className={cn("max-w-[75%] space-y-1", msg.role === "user" ? "items-end" : "items-start")}>
                <div
                  className={cn(
                    "rounded-lg px-3 py-2 text-sm whitespace-pre-wrap",
                    msg.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  )}
                >
                  {msg.content}
                </div>

                {/* Tool calls */}
                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <button
                    onClick={() => toggleToolExpand(i)}
                    className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Wrench className="h-3 w-3" />
                    {msg.toolCalls.length} tool call{msg.toolCalls.length > 1 ? "s" : ""}
                    {expandedTools[i] ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  </button>
                )}
                {msg.toolCalls && expandedTools[i] && (
                  <div className="space-y-2 mt-1">
                    {msg.toolCalls.map((tc, j) => (
                      <div key={j} className="rounded border bg-card p-2 text-xs font-mono space-y-1">
                        <div className="flex items-center gap-1 text-muted-foreground">
                          <Wrench className="h-3 w-3" />
                          <span className="font-semibold text-foreground">{tc.tool}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Input: </span>
                          <pre className="inline whitespace-pre-wrap break-all">
                            {JSON.stringify(tc.input, null, 2)}
                          </pre>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Output: </span>
                          <pre className="inline whitespace-pre-wrap break-all">
                            {formatToolOutput(tc.output)}
                          </pre>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              {msg.role === "user" && (
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
                  <User className="h-4 w-4 text-primary-foreground" />
                </div>
              )}
            </div>
          ))}

          {mutation.isPending && (
            <div className="flex gap-3 justify-start">
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="h-4 w-4 text-primary" />
              </div>
              <div className="rounded-lg px-3 py-2 bg-muted text-sm text-muted-foreground">
                <span className="inline-flex gap-1">
                  <span className="animate-bounce" style={{ animationDelay: "0ms" }}>.</span>
                  <span className="animate-bounce" style={{ animationDelay: "150ms" }}>.</span>
                  <span className="animate-bounce" style={{ animationDelay: "300ms" }}>.</span>
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </CardContent>

        {/* Input area */}
        <div className="border-t p-3">
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                mode === "customer"
                  ? "Type a message as a volunteer..."
                  : "Type a message as an admin..."
              }
              disabled={mutation.isPending}
              autoFocus
            />
            <Button onClick={handleSend} disabled={mutation.isPending || !input.trim() || (mode === "customer" && !selectedPhone)}>
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
