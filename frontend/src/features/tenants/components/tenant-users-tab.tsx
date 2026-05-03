import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useTenantUsers,
  useCreateTenantUser,
  useUpdateTenantUser,
  useUpdateTenantUserPassword,
} from "../hooks/use-tenants";
import { ADMIN_ROLE_LABELS } from "@/lib/constants";
import type { AdminRole } from "@/types/enums";

interface TenantUsersTabProps {
  tenantId: string;
}

const ROLE_OPTIONS = [
  { value: "staff", label: "Staff" },
  { value: "manager", label: "Manager" },
  { value: "owner", label: "Owner" },
];

export function TenantUsersTab({ tenantId }: TenantUsersTabProps) {
  const { data: users, isLoading } = useTenantUsers(tenantId);
  const createMutation = useCreateTenantUser();
  const updateMutation = useUpdateTenantUser();
  const passwordMutation = useUpdateTenantUserPassword();

  const [showCreate, setShowCreate] = useState(false);
  const [showPassword, setShowPassword] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({
    email: "",
    password: "",
    role: "staff",
    phone: "",
  });
  const [newPassword, setNewPassword] = useState("");

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const body = {
      ...createForm,
      role: createForm.role as AdminRole,
      phone: createForm.phone || undefined,
    };
    createMutation.mutate(body, {
      onSuccess: () => {
        setShowCreate(false);
        setCreateForm({ email: "", password: "", role: "staff", phone: "" });
      },
    });
  };

  const handlePasswordUpdate = (e: React.FormEvent) => {
    e.preventDefault();
    if (!showPassword) return;
    passwordMutation.mutate(
      { userId: showPassword, password: newPassword },
      {
        onSuccess: () => {
          setShowPassword(null);
          setNewPassword("");
        },
      }
    );
  };

  const toggleActive = (userId: string, currentlyActive: boolean) => {
    updateMutation.mutate({ userId, body: { is_active: !currentlyActive } });
  };

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setShowCreate(true)}>Create User</Button>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Email</TableHead>
            <TableHead>SMS Phone</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            <TableRow>
              <TableCell
                colSpan={6}
                className="text-center py-8 text-muted-foreground"
              >
                Loading...
              </TableCell>
            </TableRow>
          ) : !users?.length ? (
            <TableRow>
              <TableCell
                colSpan={6}
                className="text-center py-8 text-muted-foreground"
              >
                No users found for this tenant
              </TableCell>
            </TableRow>
          ) : (
            users.map((user) => (
              <TableRow key={user.id}>
                <TableCell className="font-medium">{user.email}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {user.phone || "—"}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {ADMIN_ROLE_LABELS[user.role as AdminRole] || user.role}
                  </Badge>
                </TableCell>
                <TableCell>
                  {user.is_active ? (
                    <Badge variant="default">Active</Badge>
                  ) : (
                    <Badge variant="destructive">Inactive</Badge>
                  )}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(user.created_at).toLocaleDateString()}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowPassword(user.id)}
                  >
                    Reset Password
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="ml-2"
                    onClick={() => toggleActive(user.id, user.is_active)}
                    disabled={updateMutation.isPending}
                  >
                    {user.is_active ? "Deactivate" : "Activate"}
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {/* Create User Dialog */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create User</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="user-email">Email</Label>
              <Input
                id="user-email"
                type="email"
                value={createForm.email}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, email: e.target.value }))
                }
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="user-password">Password</Label>
              <Input
                id="user-password"
                type="password"
                value={createForm.password}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, password: e.target.value }))
                }
                required
                minLength={6}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="user-role">Role</Label>
              <Select
                value={createForm.role}
                onValueChange={(v) =>
                  setCreateForm((f) => ({ ...f, role: v ?? "staff" }))
                }
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ROLE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="user-phone">Phone (for SMS admin access)</Label>
              <Input
                id="user-phone"
                type="tel"
                value={createForm.phone}
                onChange={(e) =>
                  setCreateForm((f) => ({ ...f, phone: e.target.value }))
                }
                placeholder="+1234567890 (optional)"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowCreate(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating..." : "Create"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Reset Password Dialog */}
      <Dialog
        open={showPassword !== null}
        onOpenChange={(open) => {
          if (!open) {
            setShowPassword(null);
            setNewPassword("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset Password</DialogTitle>
          </DialogHeader>
          <form onSubmit={handlePasswordUpdate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={6}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setShowPassword(null);
                  setNewPassword("");
                }}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={passwordMutation.isPending}>
                {passwordMutation.isPending ? "Updating..." : "Update Password"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
