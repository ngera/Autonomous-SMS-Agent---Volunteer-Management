import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/shared/page-header";
import { Pagination } from "@/components/shared/pagination";
import { SearchInput } from "@/components/shared/search-input";
import type { ConversationResponse } from "@/types/api";
import { useConversations } from "../hooks/use-conversations";
import { ConversationsList } from "../components/conversations-list";
import { ConversationMessageViewer } from "../components/conversation-message-viewer";

export function ConversationsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<ConversationResponse | null>(null);

  const conversations = useConversations({
    search: search || undefined,
    page,
    page_size: 20,
  });

  function handleSearchChange(value: string) {
    setSearch(value);
    setPage(1);
    setSelected(null);
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

      <SearchInput
        value={search}
        onChange={handleSearchChange}
        placeholder="Search by phone or customer name..."
      />

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
    </div>
  );
}
