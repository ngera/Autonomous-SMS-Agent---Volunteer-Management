import { useState } from "react";
import { Plus } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DataTable, type Column } from "@/components/shared/data-table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ADMIN_ROLE_LABELS } from "@/lib/constants";
import { AdminRole } from "@/types/enums";
import { formatDateTime } from "@/lib/utils";
import type { AdminUserResponse } from "@/types/api";
import { useAdminUsers, useUpdateAdminUser } from "../hooks/use-settings";
import { CreateAdminUserDialog } from "./create-admin-user-dialog";

export function AdminUsersTable() {
  const { data, isLoading } = useAdminUsers();
  const updateUser = useUpdateAdminUser();
  const [showCreate, setShowCreate] = useState(false);

  const columns: Column<AdminUserResponse>[] = [
    { key: "email", header: "Email", render: (u) => u.email },
    {
      key: "role",
      header: "Role",
      render: (u) => (
        <Select
          value={u.role}
          onValueChange={(v) => {
            if (v) updateUser.mutate({ id: u.id, body: { role: v as AdminRole } });
          }}
        >
          <SelectTrigger className="w-32 h-8">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {Object.values(AdminRole).map((r) => (
              <SelectItem key={r} value={r}>
                {ADMIN_ROLE_LABELS[r]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      ),
    },
    {
      key: "active",
      header: "Active",
      render: (u) => (
        <Switch
          checked={u.is_active}
          onCheckedChange={(v) =>
            updateUser.mutate({ id: u.id, body: { is_active: v } })
          }
        />
      ),
    },
    {
      key: "lastLogin",
      header: "Last Login",
      render: (u) =>
        u.last_login_at ? formatDateTime(u.last_login_at) : "Never",
    },
    {
      key: "created",
      header: "Created",
      render: (u) => formatDateTime(u.created_at),
    },
  ];

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Admin Users</CardTitle>
        <Button size="sm" variant="outline" onClick={() => setShowCreate(true)}>
          <Plus className="mr-1 h-3 w-3" />
          Add User
        </Button>
      </CardHeader>
      <CardContent>
        <DataTable
          columns={columns}
          data={data ?? []}
          isLoading={isLoading}
          emptyMessage="No admin users."
        />
      </CardContent>
      <CreateAdminUserDialog
        open={showCreate}
        onClose={() => setShowCreate(false)}
      />
    </Card>
  );
}
