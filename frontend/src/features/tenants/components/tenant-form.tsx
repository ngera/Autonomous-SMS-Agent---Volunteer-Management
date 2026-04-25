import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { ContactPreference } from "@/types/enums";
import type { TenantCreate, TenantDetailResponse } from "@/types/api";

const CONTACT_PREF_LABELS: Record<string, string> = {
  [ContactPreference.EMAIL]: "Email",
  [ContactPreference.PHONE]: "Phone",
  [ContactPreference.SMS]: "SMS",
};

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
    business_timezone: tenant?.business_timezone || "America/New_York",
    admin_panel_url: tenant?.admin_panel_url || "",
    api_domain: tenant?.api_domain || "",
    phone: tenant?.phone || "",
    email: tenant?.email || "",
    address_street: tenant?.address_street || "",
    address_city: tenant?.address_city || "",
    address_state: tenant?.address_state || "",
    address_zip: tenant?.address_zip || "",
    address_country: tenant?.address_country || "",
    billing_email: tenant?.billing_email || "",
    billing_address_street: tenant?.billing_address_street || "",
    billing_address_city: tenant?.billing_address_city || "",
    billing_address_state: tenant?.billing_address_state || "",
    billing_address_zip: tenant?.billing_address_zip || "",
    billing_address_country: tenant?.billing_address_country || "",
    contact_name: tenant?.contact_name || "",
    contact_phone: tenant?.contact_phone || "",
    contact_email: tenant?.contact_email || "",
    contact_preference: tenant?.contact_preference || undefined,
    twilio_account_sid: "",
    twilio_auth_token: "",
    twilio_phone_number: tenant?.twilio_phone_number || "",
    anthropic_api_key: "",
    google_client_id: "",
    google_client_secret: "",
    google_refresh_token: "",
    resend_api_key: "",
    resend_from_email: tenant?.resend_from_email || "",
    admin_email: "",
    admin_password: "",
  });

  const handleChange = (field: keyof TenantCreate, value: string | undefined) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = Object.fromEntries(
      Object.entries(form).filter(([, v]) => v !== "" && v !== undefined)
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
              placeholder="America/New_York"
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

      {!tenant && (
        <Card>
          <CardHeader>
            <CardTitle>Admin Login</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="admin_email">Admin Email</Label>
              <Input
                id="admin_email"
                type="email"
                value={form.admin_email || ""}
                onChange={(e) => handleChange("admin_email", e.target.value)}
                placeholder="admin@tenant.com"
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin_password">Admin Password</Label>
              <Input
                id="admin_password"
                type="password"
                value={form.admin_password || ""}
                onChange={(e) => handleChange("admin_password", e.target.value)}
                placeholder="Minimum 6 characters"
                required
                minLength={6}
              />
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Store Information</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="phone">Store Phone</Label>
            <Input
              id="phone"
              value={form.phone || ""}
              onChange={(e) => handleChange("phone", e.target.value)}
              placeholder="+1234567890"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Store Email</Label>
            <Input
              id="email"
              type="email"
              value={form.email || ""}
              onChange={(e) => handleChange("email", e.target.value)}
              placeholder="info@example.com"
            />
          </div>
          <div className="space-y-2 col-span-2">
            <Label htmlFor="address_street">Street Address</Label>
            <Input
              id="address_street"
              value={form.address_street || ""}
              onChange={(e) => handleChange("address_street", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="address_city">City</Label>
            <Input
              id="address_city"
              value={form.address_city || ""}
              onChange={(e) => handleChange("address_city", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="address_state">State / Region</Label>
            <Input
              id="address_state"
              value={form.address_state || ""}
              onChange={(e) => handleChange("address_state", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="address_zip">ZIP / Postal Code</Label>
            <Input
              id="address_zip"
              value={form.address_zip || ""}
              onChange={(e) => handleChange("address_zip", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="address_country">Country</Label>
            <Input
              id="address_country"
              value={form.address_country || ""}
              onChange={(e) => handleChange("address_country", e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Billing Information</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2 col-span-2">
            <Label htmlFor="billing_email">Billing Email</Label>
            <Input
              id="billing_email"
              type="email"
              value={form.billing_email || ""}
              onChange={(e) => handleChange("billing_email", e.target.value)}
              placeholder="billing@example.com"
            />
          </div>
          <div className="space-y-2 col-span-2">
            <Label htmlFor="billing_address_street">Billing Street</Label>
            <Input
              id="billing_address_street"
              value={form.billing_address_street || ""}
              onChange={(e) => handleChange("billing_address_street", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="billing_address_city">City</Label>
            <Input
              id="billing_address_city"
              value={form.billing_address_city || ""}
              onChange={(e) => handleChange("billing_address_city", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="billing_address_state">State / Region</Label>
            <Input
              id="billing_address_state"
              value={form.billing_address_state || ""}
              onChange={(e) => handleChange("billing_address_state", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="billing_address_zip">ZIP / Postal Code</Label>
            <Input
              id="billing_address_zip"
              value={form.billing_address_zip || ""}
              onChange={(e) => handleChange("billing_address_zip", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="billing_address_country">Country</Label>
            <Input
              id="billing_address_country"
              value={form.billing_address_country || ""}
              onChange={(e) => handleChange("billing_address_country", e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Primary Contact</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="contact_name">Contact Name</Label>
            <Input
              id="contact_name"
              value={form.contact_name || ""}
              onChange={(e) => handleChange("contact_name", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="contact_phone">Contact Phone</Label>
            <Input
              id="contact_phone"
              value={form.contact_phone || ""}
              onChange={(e) => handleChange("contact_phone", e.target.value)}
              placeholder="+1234567890"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="contact_email">Contact Email</Label>
            <Input
              id="contact_email"
              type="email"
              value={form.contact_email || ""}
              onChange={(e) => handleChange("contact_email", e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="contact_preference">Preferred Contact Method</Label>
            <Select
              value={form.contact_preference ?? null}
              onValueChange={(v) => handleChange("contact_preference", v ?? undefined)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select..." />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(CONTACT_PREF_LABELS).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
              placeholder={tenant?.twilio_account_sid_masked || (tenant ? "Leave blank to keep existing" : "")}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="twilio_auth_token">Auth Token</Label>
            <Input
              id="twilio_auth_token"
              type="password"
              value={form.twilio_auth_token || ""}
              onChange={(e) => handleChange("twilio_auth_token", e.target.value)}
              placeholder={tenant?.twilio_auth_token_masked || (tenant ? "Leave blank to keep existing" : "")}
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
              placeholder={tenant?.anthropic_api_key_masked || (tenant ? "Leave blank to keep existing" : "")}
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
              placeholder={tenant?.google_client_id_masked || (tenant ? "Leave blank to keep existing" : "")}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="google_client_secret">Client Secret</Label>
            <Input
              id="google_client_secret"
              type="password"
              value={form.google_client_secret || ""}
              onChange={(e) => handleChange("google_client_secret", e.target.value)}
              placeholder={tenant?.google_client_secret_masked || (tenant ? "Leave blank to keep existing" : "")}
            />
          </div>
          <div className="space-y-2 col-span-2">
            <Label htmlFor="google_refresh_token">Refresh Token</Label>
            <Input
              id="google_refresh_token"
              type="password"
              value={form.google_refresh_token || ""}
              onChange={(e) => handleChange("google_refresh_token", e.target.value)}
              placeholder={tenant?.google_refresh_token_masked || (tenant ? "Leave blank to keep existing" : "")}
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
              placeholder={tenant?.resend_api_key_masked || (tenant ? "Leave blank to keep existing" : "")}
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
