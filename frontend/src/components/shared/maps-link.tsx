import { MapPin } from "lucide-react";

interface MapsLinkProps {
  address: string | null | undefined;
  /** Optional className override applied to the anchor. */
  className?: string;
  /** Show the address text alongside the icon. Default: just the icon. */
  showText?: boolean;
}

/**
 * Icon link that opens the given address in Google Maps. Uses the public
 * `?api=1&query=` URL pattern so no API key is required.
 */
export function MapsLink({ address, className, showText = false }: MapsLinkProps) {
  const trimmed = (address ?? "").trim();
  if (!trimmed) return null;
  const href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(trimmed)}`;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      title="View on Google Maps"
      aria-label={`View ${trimmed} on Google Maps`}
      className={
        className ??
        "inline-flex items-center gap-1 text-muted-foreground hover:text-foreground"
      }
    >
      <MapPin className="h-3.5 w-3.5 shrink-0" />
      {showText && <span className="truncate">{trimmed}</span>}
    </a>
  );
}
