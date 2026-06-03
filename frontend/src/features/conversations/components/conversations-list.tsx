import { DataTable, type Column } from "@/components/shared/data-table";
import { StatusBadge } from "@/components/shared/status-badge";
import { formatDateTime } from "@/lib/utils";
import type { ConversationResponse } from "@/types/api";

interface ConversationsListProps {
  conversations: ConversationResponse[];
  isLoading: boolean;
  onSelect: (conversation: ConversationResponse) => void;
  selectedIds?: Set<string>;
  onToggleRow?: (id: string) => void;
  onToggleAll?: (checked: boolean, allIds: string[]) => void;
}

const columns: Column<ConversationResponse>[] = [
  { key: "phone", header: "Phone", render: (c) => c.contact_phone },
  {
    key: "status",
    header: "Status",
    render: (c) => <StatusBadge type="conversation" value={c.status} />,
  },
  {
    key: "step",
    header: "Current Step",
    render: (c) => c.current_step || "—",
  },
  {
    key: "messages",
    header: "Messages",
    render: (c) => c.message_history?.length ?? 0,
  },
  {
    key: "lastMessage",
    header: "Last Message",
    render: (c) => formatDateTime(c.last_message_at),
  },
];

export function ConversationsList({
  conversations,
  isLoading,
  onSelect,
  selectedIds,
  onToggleRow,
  onToggleAll,
}: ConversationsListProps) {
  const selection =
    selectedIds && onToggleRow && onToggleAll
      ? {
          getRowId: (c: ConversationResponse) => c.id,
          selectedIds,
          onToggleRow: (id: string) => onToggleRow(id),
          onToggleAll,
        }
      : undefined;

  return (
    <DataTable
      columns={columns}
      data={conversations}
      isLoading={isLoading}
      emptyMessage="No conversations found."
      onRowClick={onSelect}
      selection={selection}
    />
  );
}
