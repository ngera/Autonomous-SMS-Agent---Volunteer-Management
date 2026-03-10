import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/shared/page-header";
import { useCustomerConversations } from "@/features/customers/hooks/use-customers";
import type { ConversationResponse } from "@/types/api";
import { ConversationsList } from "../components/conversations-list";
import { ConversationMessageViewer } from "../components/conversation-message-viewer";

export function ConversationsPage() {
  const [phone, setPhone] = useState("");
  const [searchPhone, setSearchPhone] = useState("");
  const [selected, setSelected] = useState<ConversationResponse | null>(null);

  const conversations = useCustomerConversations(searchPhone);

  function handleSearch() {
    if (phone.trim()) {
      setSearchPhone(phone.trim());
      setSelected(null);
    }
  }

  if (selected) {
    return (
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSelected(null)}
        >
          <ArrowLeft className="mr-1 h-3 w-3" />
          Back to list
        </Button>
        <ConversationMessageViewer conversation={selected} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Conversations"
        description="View AI conversation threads by customer phone number."
      />

      <div className="flex items-end gap-3">
        <div className="space-y-1">
          <Label className="text-xs">Customer Phone</Label>
          <Input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+447..."
            className="w-56"
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
        </div>
        <Button size="sm" onClick={handleSearch} disabled={!phone.trim()}>
          Search
        </Button>
      </div>

      {searchPhone && (
        <ConversationsList
          conversations={conversations.data ?? []}
          isLoading={conversations.isLoading}
          onSelect={setSelected}
        />
      )}
    </div>
  );
}
