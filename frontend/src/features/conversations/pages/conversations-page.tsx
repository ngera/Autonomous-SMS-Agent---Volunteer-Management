import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/shared/page-header";
import { Pagination } from "@/components/shared/pagination";
import type { ConversationResponse } from "@/types/api";
import { useConversations } from "../hooks/use-conversations";
import { ConversationsList } from "../components/conversations-list";
import { ConversationMessageViewer } from "../components/conversation-message-viewer";

export function ConversationsPage() {
  const [searchInput, setSearchInput] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<ConversationResponse | null>(null);

  const conversations = useConversations({
    search: searchTerm || undefined,
    page,
    page_size: 20,
  });

  function handleSearch() {
    if (searchInput.trim()) {
      setSearchTerm(searchInput.trim());
      setPage(1);
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
        description="View AI conversation threads."
      />

      <div className="flex items-end gap-3">
        <div className="space-y-1">
          <Label className="text-xs">Search by phone or name</Label>
          <Input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Phone number or customer name..."
            className="w-72"
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
        </div>
        <Button size="sm" onClick={handleSearch} disabled={!searchInput.trim()}>
          Search
        </Button>
      </div>

      {searchTerm && (
        <>
          <ConversationsList
            conversations={conversations.data?.items ?? []}
            isLoading={conversations.isLoading}
            onSelect={setSelected}
          />

          {conversations.data && conversations.data.total > 20 && (
            <Pagination
              page={page}
              pageSize={20}
              total={conversations.data.total}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </div>
  );
}
