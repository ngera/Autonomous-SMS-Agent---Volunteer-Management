import { cn } from "@/lib/utils";

interface VolunteerAvatarProps {
  name: string | null;
  phone: string;
  className?: string;
}

const PALETTE = [
  "bg-amber-200 text-amber-900",
  "bg-rose-200 text-rose-900",
  "bg-emerald-200 text-emerald-900",
  "bg-sky-200 text-sky-900",
  "bg-violet-200 text-violet-900",
  "bg-orange-200 text-orange-900",
  "bg-teal-200 text-teal-900",
  "bg-pink-200 text-pink-900",
];

function hashKey(input: string): number {
  let h = 0;
  for (let i = 0; i < input.length; i++) {
    h = (h * 31 + input.charCodeAt(i)) >>> 0;
  }
  return h;
}

function initialsFrom(name: string | null, phone: string): string {
  const source = (name || "").trim();
  if (!source) return phone.slice(-2).toUpperCase();
  const parts = source.split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function VolunteerAvatar({ name, phone, className }: VolunteerAvatarProps) {
  const initials = initialsFrom(name, phone);
  const tone = PALETTE[hashKey(name || phone) % PALETTE.length];
  return (
    <span
      className={cn(
        "inline-flex h-9 w-9 shrink-0 select-none items-center justify-center rounded-full text-xs font-semibold",
        tone,
        className
      )}
    >
      {initials}
    </span>
  );
}
