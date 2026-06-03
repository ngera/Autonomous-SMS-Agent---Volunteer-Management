import { useState } from "react";
import { ArrowLeft, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader } from "@/components/shared/page-header";
import { Pagination } from "@/components/shared/pagination";
import { SearchInput } from "@/components/shared/search-input";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import type { ConversationResponse } from "@/types/api";
import { useConversations } from "../hooks/use-conversations";
import { ConversationsList } from "../components/conversations-list";
import { ConversationMessageViewer } from "../components/conversation-message-viewer";
import { ConversationTraceTab } from "../components/conversation-trace-tab";
import { BulkDeleteDialog } from "../components/bulk-delete-dialog";

export function ConversationsPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<ConversationResponse | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDialogOpen, setBulkDialogOpen] = useState(false);
  const [selectionDialogOpen, setSelectionDialogOpen] = useState(false);
  const { hasRole } = useAuth();
  const canBulkDelete = hasRole(AdminRole.MANAGER);

  const conversations = useConversations({
    search: search || undefined,
    page,
    page_size: 20,
  });

  function handleSearchChange(value: string) {
    setSearch(value);
    setPage(1);
    setSelected(null);
    setSelectedIds(new Set());
  }

  function toggleRow(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll(checked: boolean, allIds: string[]) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) allIds.forEach((id) => next.add(id));
      else allIds.forEach((id) => next.delete(id));
      return next;
    });
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
        <Tabs defaultValue="messages">
          <TabsList>
            <TabsTrigger value="messages">Messages</TabsTrigger>
            <TabsTrigger value="trace">Agent trace</TabsTrigger>
          </TabsList>
          <TabsContent value="messages" className="mt-4">
            <ConversationMessageViewer conversation={selected} />
          </TabsContent>
          <TabsContent value="trace" className="mt-4">
            <ConversationTraceTab conversationId={selected.id} />
          </TabsContent>
        </Tabs>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Conversations"
        description="View AI conversation threads."
        actions={
          canBulkDelete ? (
            <div className="flex gap-2">
              {selectedIds.size > 0 && (
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => setSelectionDialogOpen(true)}
                >
                  <Trash2 className="mr-1 h-3 w-3" />
                  Delete selected ({selectedIds.size})
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                onClick={() => setBulkDialogOpen(true)}
              >
                <Trash2 className="mr-1 h-3 w-3" />
                Delete old…
              </Button>
            </div>
          ) : undefined
        }
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
        selectedIds={canBulkDelete ? selectedIds : undefined}
        onToggleRow={canBulkDelete ? toggleRow : undefined}
        onToggleAll={canBulkDelete ? toggleAll : undefined}
      />

      {conversations.data && conversations.data.total > 20 && (
        <Pagination
          page={page}
          pageSize={20}
          total={conversations.data.total}
          onPageChange={setPage}
        />
      )}

      <BulkDeleteDialog
        open={bulkDialogOpen}
        onOpenChange={setBulkDialogOpen}
        onDeleted={() => setSelectedIds(new Set())}
      />
      <BulkDeleteDialog
        open={selectionDialogOpen}
        onOpenChange={setSelectionDialogOpen}
        selectedIds={[...selectedIds]}
        onDeleted={() => setSelectedIds(new Set())}
      />
    </div>
  );
}
