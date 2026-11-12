from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import mapped_column

from .db import Base


class EmployeeAvailability(Base):
    __tablename__ = "employee_availability"
    __table_args__ = (
        UniqueConstraint("name", "service_date", "service_time", name="uq_employee_slot"),
        CheckConstraint("length(trim(name)) > 0", name="ck_employee_name_nonempty"),
        CheckConstraint(
            "attendance_status IS NULL OR attendance_status IN "
            "('present', 'absent', 'cancelled', 'replaced')",
            name="ck_attendance_status",
        ),
    )

    id = mapped_column(Integer, primary_key=True, index=True)
    employee_code = mapped_column(String(80), nullable=True, index=True)
    name = mapped_column(String(120), nullable=True, index=True)
    patient = mapped_column(String(120), nullable=True)
    shift = mapped_column(String(80), nullable=False)
    service_date = mapped_column(Date, nullable=False, index=True)
    service_time = mapped_column(Time, nullable=True)
    service_end_time = mapped_column(Time, nullable=True)
    available = mapped_column(Boolean, nullable=True)
    attendance_status = mapped_column(String(20), nullable=True)
    attendance_confirmed_at = mapped_column(DateTime(timezone=True), nullable=True)
