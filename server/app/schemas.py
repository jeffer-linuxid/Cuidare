from datetime import date, datetime, time
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .plantoes import PlantaoResult

AttendanceStatus = PlantaoResult


class EmployeeFields(BaseModel):
    employee_code: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    patient: str | None = Field(default=None, max_length=120)
    shift: str = Field(min_length=1, max_length=80)
    service_date: date
    service_time: time | None = None
    service_end_time: time | None = None
    available: bool | None = None
    attendance_status: AttendanceStatus | None = None
    attendance_confirmed_at: datetime | None = None

    @field_validator("employee_code", "name", "shift")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        return value

    @field_validator("patient")
    @classmethod
    def strip_patient(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def validate_attendance_confirmation(self):
        if (self.attendance_status is None) != (self.attendance_confirmed_at is None):
            raise ValueError(
                "O resultado do plantão e a data de confirmação devem ser informados juntos."
            )
        if self.attendance_status is not None and self.name is None:
            raise ValueError("Não é possível registrar o resultado sem um funcionário escalado.")
        return self


class EmployeeCreate(EmployeeFields):
    pass


class EmployeeUpdate(EmployeeFields):
    pass


class EmployeeRead(EmployeeFields):
    model_config = ConfigDict(from_attributes=True)

    id: int


class AttendanceUpdate(BaseModel):
    attendance_status: AttendanceStatus | None


class ImportResult(BaseModel):
    created: int
    updated: int
