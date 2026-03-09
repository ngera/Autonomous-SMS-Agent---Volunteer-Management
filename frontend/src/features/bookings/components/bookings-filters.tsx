import { SearchInput } from "@/components/shared/search-input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { BookingStatus } from "@/types/enums";
import { BOOKING_STATUS_LABELS } from "@/lib/constants";

interface BookingsFiltersProps {
  status: string;
  onStatusChange: (v: string) => void;
  phone: string;
  onPhoneChange: (v: string) => void;
  dateFrom: string;
  onDateFromChange: (v: string) => void;
  dateTo: string;
  onDateToChange: (v: string) => void;
}

export function BookingsFilters({
  status,
  onStatusChange,
  phone,
  onPhoneChange,
  dateFrom,
  onDateFromChange,
  dateTo,
  onDateToChange,
}: BookingsFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      <div className="w-48">
        <Select value={status} onValueChange={onStatusChange}>
          <SelectTrigger>
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {Object.values(BookingStatus).map((s) => (
              <SelectItem key={s} value={s}>
                {BOOKING_STATUS_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="w-52">
        <SearchInput
          value={phone}
          onChange={onPhoneChange}
          placeholder="Filter by phone..."
        />
      </div>
      <Input
        type="date"
        value={dateFrom}
        onChange={(e) => onDateFromChange(e.target.value)}
        className="w-40"
        placeholder="From"
      />
      <Input
        type="date"
        value={dateTo}
        onChange={(e) => onDateToChange(e.target.value)}
        className="w-40"
        placeholder="To"
      />
    </div>
  );
}
