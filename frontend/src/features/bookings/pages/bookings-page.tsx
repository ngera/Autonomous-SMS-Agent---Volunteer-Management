import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Pagination } from "@/components/shared/pagination";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { AdminRole } from "@/types/enums";
import { BookingsFilters } from "../components/bookings-filters";
import { BookingsTable } from "../components/bookings-table";
import { useBookings } from "../hooks/use-bookings";

export function BookingsPage() {
  const navigate = useNavigate();
  const { hasRole } = useAuth();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("all");
  const [phone, setPhone] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const bookings = useBookings({
    page,
    page_size: 20,
    status: status === "all" ? undefined : status,
    contact_phone: phone || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });

  return (
    <div>
      <PageHeader
        title="Bookings"
        description="Manage all appointments."
        actions={
          hasRole(AdminRole.MANAGER) ? (
            <Button onClick={() => navigate("/bookings/new")}>
              <Plus className="mr-2 h-4 w-4" />
              New Booking
            </Button>
          ) : undefined
        }
      />

      <BookingsFilters
        status={status}
        onStatusChange={(v) => { setStatus(v); setPage(1); }}
        phone={phone}
        onPhoneChange={(v) => { setPhone(v); setPage(1); }}
        dateFrom={dateFrom}
        onDateFromChange={(v) => { setDateFrom(v); setPage(1); }}
        dateTo={dateTo}
        onDateToChange={(v) => { setDateTo(v); setPage(1); }}
      />

      <BookingsTable
        data={bookings.data?.items ?? []}
        isLoading={bookings.isLoading}
      />

      {bookings.data && (
        <Pagination
          page={page}
          pageSize={20}
          total={bookings.data.total}
          onPageChange={setPage}
        />
      )}
    </div>
  );
}
