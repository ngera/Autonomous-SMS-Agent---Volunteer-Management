import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { TenantDetailResponse } from "@/types/api";

const CONTACT_PREF_LABELS: Record<string, string> = {
  email: "Email",
  phone: "Phone",
  sms: "SMS",
};

function StatusBadge({ tenant }: { tenant: TenantDetailResponse }) {
  if (!tenant.is_active) {
    return <Badge variant="destructive">Deactivated</Badge>;
  }
  if (tenant.is_paused) {
    return <Badge variant="secondary" className="bg-yellow-100 text-yellow-800">Paused</Badge>;
  }
  return <Badge variant="default">Active</Badge>;
}

function IntegrationDot({ configured, label }: { configured: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`inline-block h-2 w-2 rounded-full ${configured ? "bg-green-500" : "bg-gray-300"}`} />
      {label}
    </div>
  );
}

interface TenantInfoCardProps {
  tenant: TenantDetailResponse;
}

export function TenantInfoCard({ tenant }: TenantInfoCardProps) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{tenant.business_name}</CardTitle>
          <StatusBadge tenant={tenant} />
        </div>
        <p className="text-sm text-muted-foreground">{tenant.slug}</p>
      </CardHeader>
      <CardContent className="space-y-4 text-sm">
        {/* Business Info */}
        <div className="space-y-1">
          <p className="font-medium text-muted-foreground">Business</p>
          {tenant.business_domain && <p>{tenant.business_domain}</p>}
          <p>{tenant.business_timezone}</p>
        </div>

        {/* Store Contact */}
        {(tenant.phone || tenant.email) && (
          <div className="space-y-1">
            <p className="font-medium text-muted-foreground">Store Contact</p>
            {tenant.phone && <p>{tenant.phone}</p>}
            {tenant.email && <p>{tenant.email}</p>}
          </div>
        )}

        {/* Address */}
        {(tenant.address_city || tenant.address_state) && (
          <div className="space-y-1">
            <p className="font-medium text-muted-foreground">Address</p>
            {tenant.address_street && <p>{tenant.address_street}</p>}
            <p>
              {[tenant.address_city, tenant.address_state, tenant.address_zip]
                .filter(Boolean)
                .join(", ")}
            </p>
            {tenant.address_country && <p>{tenant.address_country}</p>}
          </div>
        )}

        {/* Primary Contact */}
        {(tenant.contact_name || tenant.contact_email || tenant.contact_phone) && (
          <div className="space-y-1">
            <p className="font-medium text-muted-foreground">Primary Contact</p>
            {tenant.contact_name && <p>{tenant.contact_name}</p>}
            {tenant.contact_phone && <p>{tenant.contact_phone}</p>}
            {tenant.contact_email && <p>{tenant.contact_email}</p>}
            {tenant.contact_preference && (
              <p className="text-muted-foreground">
                Prefers: {CONTACT_PREF_LABELS[tenant.contact_preference] || tenant.contact_preference}
              </p>
            )}
          </div>
        )}

        {/* Integrations */}
        <div className="space-y-1">
          <p className="font-medium text-muted-foreground">Integrations</p>
          <IntegrationDot configured={tenant.has_twilio} label="Twilio (SMS)" />
          <IntegrationDot configured={tenant.has_anthropic} label="Anthropic (AI)" />
          <IntegrationDot configured={tenant.has_google_calendar} label="Google Calendar" />
          <IntegrationDot configured={tenant.has_resend} label="Resend (Email)" />
        </div>

        {/* Dates */}
        <div className="space-y-1">
          <p className="font-medium text-muted-foreground">Created</p>
          <p>{new Date(tenant.created_at).toLocaleDateString()}</p>
        </div>
      </CardContent>
    </Card>
  );
}
