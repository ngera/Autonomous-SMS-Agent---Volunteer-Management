import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TenantCreate, TenantDetailResponse } from "@/types/api";

interface TenantFormProps {
  tenant?: TenantDetailResponse;
  onSubmit: (data: TenantCreate) => void;
  isLoading?: boolean;
}

export function TenantForm({ tenant, onSubmit, isLoading }: TenantFormProps) {
  const [form, setForm] = useState<TenantCreate>({
    name: tenant?.name || "",
    slug: tenant?.slug || "",
    business_name: tenant?.business_name || "",
    business_domain: tenant?.business_domain || "",
    business_timezone: tenant?.business_timezone || "Europe/London",
    admin_panel_url: tenant?.admin_panel_url || "",
    api_domain: tenant?.api_domain || "",
    twilio_account_sid: "",
    twilio_auth_token: "",
    twilio_phone_number: tenant?.twilio_phone_number || "",
    anthropic_api_key: "",
    google_client_id: "",
    google_client_secret: "",
    google_refresh_token: "",
    resend_api_key: "",
    resend_from_email: "",
  });

  const handleChange = (field: keyof TenantCreate, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Strip empty strings for optional credential fields
    const cleaned = Object.fromEntries(
      Object.entries(form).filter(([, v]) => v !== "")
    ) as TenantCreate;
    onSubmit(cleaned);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="name">Tenant Name</Label>
            <Input
              id="name"
              value={form.name}
              onChange={(e) => handleChange("name", e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="slug">Slug</Label>
            <Input
              id="slug"
              value={form.slug}
              onChange={(e) => handleChange("slug", e.target.value)}
              required
              placeholder="my-business"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="business_name">Business Name</Label>
            <Input
              id="business_name"
              value={form.business_name}
              onChange={(e) => handleChange("business_name", e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="business_domain">Business Domain</Label>
            <Input
              id="business_domain"
              value={form.business_domain || ""}
              onChange={(e) => handleChange("business_domain", e.target.value)}
              placeholder="example.com"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="business_timezone">Timezone</Label>
            <Input
              id="business_timezone"
              value={form.business_timezone || ""}
              onChange={(e) => handleChange("business_timezone", e.target.value)}
              placeholder="Europe/London"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="admin_panel_url">Admin Panel URL</Label>
            <Input
              id="admin_panel_url"
              value={form.admin_panel_url || ""}
              onChange={(e) => handleChange("admin_panel_url", e.target.value)}
              placeholder="https://admin.example.com"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="api_domain">API Domain</Label>
            <Input
              id="api_domain"
              value={form.api_domain || ""}
              onChange={(e) => handleChange("api_domain", e.target.value)}
              placeholder="api.example.com"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            Twilio (SMS)
            {tenant?.has_twilio && (
              <span className="ml-2 text-xs font-normal text-green-600">Configured</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="twilio_account_sid">Account SID</Label>
            <Input
              id="twilio_account_sid"
              value={form.twilio_account_sid || ""}
              onChange={(e) => handleChange("twilio_account_sid", e.target.value)}
              placeholder={tenant ? "Leave blank to keep existing" : ""}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="twilio_auth_token">Auth Token</Label>
            <Input
              id="twilio_auth_token"
              type="password"
              value={form.twilio_auth_token || ""}
              onChange={(e) => handleChange("twilio_auth_token", e.target.value)}
              placeholder={tenant ? "Leave blank to keep existing" : ""}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="twilio_phone_number">Phone Number</Label>
            <Input
              id="twilio_phone_number"
              value={form.twilio_phone_number || ""}
              onChange={(e) => handleChange("twilio_phone_number", e.target.value)}
              placeholder="+1234567890"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            Anthropic (AI)
            {tenant?.has_anthropic && (
              <span className="ml-2 text-xs font-normal text-green-600">Configured</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <Label htmlFor="anthropic_api_key">API Key</Label>
            <Input
              id="anthropic_api_key"
              type="password"
              value={form.anthropic_api_key || ""}
              onChange={(e) => handleChange("anthropic_api_key", e.target.value)}
              placeholder={tenant ? "Leave blank to keep existing" : ""}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            Google Calendar
            {tenant?.has_google_calendar && (
              <span className="ml-2 text-xs font-normal text-green-600">Configured</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="google_client_id">Client ID</Label>
            <Input
              id="google_client_id"
              value={form.google_client_id || ""}
              onChange={(e) => handleChange("google_client_id", e.target.value)}
              placeholder={tenant ? "Leave blank to keep existing" : ""}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="google_client_secret">Client Secret</Label>
            <Input
              id="google_client_secret"
              type="password"
              value={form.google_client_secret || ""}
              onChange={(e) => handleChange("google_client_secret", e.target.value)}
              placeholder={tenant ? "Leave blank to keep existing" : ""}
            />
          </div>
          <div className="space-y-2 col-span-2">
            <Label htmlFor="google_refresh_token">Refresh Token</Label>
            <Input
              id="google_refresh_token"
              type="password"
              value={form.google_refresh_token || ""}
              onChange={(e) => handleChange("google_refresh_token", e.target.value)}
              placeholder={tenant ? "Leave blank to keep existing" : ""}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            Resend (Email)
            {tenant?.has_resend && (
              <span className="ml-2 text-xs font-normal text-green-600">Configured</span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="resend_api_key">API Key</Label>
            <Input
              id="resend_api_key"
              type="password"
              value={form.resend_api_key || ""}
              onChange={(e) => handleChange("resend_api_key", e.target.value)}
              placeholder={tenant ? "Leave blank to keep existing" : ""}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="resend_from_email">From Email</Label>
            <Input
              id="resend_from_email"
              value={form.resend_from_email || ""}
              onChange={(e) => handleChange("resend_from_email", e.target.value)}
              placeholder="noreply@example.com"
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Saving..." : tenant ? "Update Tenant" : "Create Tenant"}
        </Button>
      </div>
    </form>
  );
}
