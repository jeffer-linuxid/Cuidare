import hmac
from contextlib import asynccontextmanager
from datetime import date, time
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from sqlalchemy import and_, delete, inspect, insert, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import API_KEY
from .db import Base, engine, get_db
from .models import EmployeeAvailability
from .plantoes import (
    PlantaoNotFoundError,
    PlantaoRepository,
    PlantaoSemFuncionarioError,
    PlantaoService,
)
from .schemas import AttendanceUpdate, EmployeeCreate, EmployeeRead, EmployeeUpdate, ImportResult


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_employee_availability_schema()
    yield


app = FastAPI(title="CareManager API", version="0.1.0", lifespan=lifespan)


def migrate_employee_availability_schema() -> None:
    columns = {
        column["name"]: column
        for column in inspect(engine).get_columns(EmployeeAvailability.__tablename__)
    }
    requires_migration = (
        "employee_code" not in columns
        or "patient" not in columns
        or "service_end_time" not in columns
        or "attendance_status" not in columns
        or "attendance_confirmed_at" not in columns
        or not columns["name"]["nullable"]
        or not columns["service_time"]["nullable"]
        or not columns["available"]["nullable"]
    )
    if not requires_migration:
        return
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            if "employee_code" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE employee_availability ADD COLUMN employee_code VARCHAR(80)"
                )
            if "patient" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE employee_availability ADD COLUMN patient VARCHAR(120)"
                )
            if "service_end_time" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE employee_availability ADD COLUMN service_end_time TIME"
                )
            if "attendance_status" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE employee_availability ADD COLUMN attendance_status VARCHAR(20)"
                )
                connection.exec_driver_sql(
                    "ALTER TABLE employee_availability ADD CONSTRAINT ck_attendance_status "
                    "CHECK (attendance_status IS NULL OR attendance_status IN "
                    "('present', 'absent', 'cancelled', 'replaced'))"
                )
            if "attendance_confirmed_at" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE employee_availability "
                    "ADD COLUMN attendance_confirmed_at TIMESTAMP WITH TIME ZONE"
                )
            connection.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_employee_availability_employee_code "
                "ON employee_availability (employee_code)"
            )
            for name in ("name", "service_time", "available"):
                if name in columns and not columns[name]["nullable"]:
                    connection.exec_driver_sql(
                        f"ALTER TABLE employee_availability ALTER COLUMN {name} DROP NOT NULL"
                    )
        return
    if engine.dialect.name != "sqlite":
        raise RuntimeError(
            f"Não há migração de escala para {engine.dialect.name}."
        )

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE employee_availability_new (
                id INTEGER NOT NULL PRIMARY KEY,
                employee_code VARCHAR(80),
                name VARCHAR(120),
                patient VARCHAR(120),
                shift VARCHAR(80) NOT NULL,
                service_date DATE NOT NULL,
                service_time TIME,
                service_end_time TIME,
                available BOOLEAN,
                attendance_status VARCHAR(20),
                attendance_confirmed_at DATETIME,
                CONSTRAINT uq_employee_slot UNIQUE (name, service_date, service_time),
                CONSTRAINT ck_employee_name_nonempty CHECK (
                    name IS NULL OR length(trim(name)) > 0
                ),
                CONSTRAINT ck_attendance_status CHECK (
                    attendance_status IS NULL OR attendance_status IN
                    ('present', 'absent', 'cancelled', 'replaced')
                )
            )
            """
        )
        new_columns = (
            "id", "employee_code", "name", "patient", "shift", "service_date",
            "service_time", "service_end_time", "available",
            "attendance_status", "attendance_confirmed_at",
        )
        shared_columns = [name for name in new_columns if name in columns]
        selected_columns = ", ".join(shared_columns)
        connection.exec_driver_sql(
            "INSERT INTO employee_availability_new "
            f"({selected_columns}) SELECT {selected_columns} FROM employee_availability"
        )
        connection.exec_driver_sql("DROP TABLE employee_availability")
        connection.exec_driver_sql(
            "ALTER TABLE employee_availability_new RENAME TO employee_availability"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_employee_availability_id ON employee_availability (id)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_employee_availability_employee_code "
            "ON employee_availability (employee_code)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_employee_availability_name ON employee_availability (name)"
        )
        connection.exec_driver_sql(
            "CREATE INDEX ix_employee_availability_service_date "
            "ON employee_availability (service_date)"
        )


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if x_api_key is None or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave de API inválida")


def apply_fields(record: EmployeeAvailability, fields: EmployeeCreate | EmployeeUpdate) -> None:
    if "employee_code" in fields.model_fields_set:
        record.employee_code = fields.employee_code
    record.name = fields.name
    if "patient" in fields.model_fields_set:
        record.patient = fields.patient
    record.shift = fields.shift
    record.service_date = fields.service_date
    record.service_time = fields.service_time
    record.service_end_time = fields.service_end_time
    record.available = fields.available
    if "attendance_status" in fields.model_fields_set:
        record.attendance_status = fields.attendance_status
    if "attendance_confirmed_at" in fields.model_fields_set:
        record.attendance_confirmed_at = fields.attendance_confirmed_at
    elif "attendance_status" in fields.model_fields_set and fields.attendance_status is None:
        record.attendance_confirmed_at = None


def employee_import_identity(fields: EmployeeCreate | EmployeeAvailability) -> tuple:
    identity = (fields.name, fields.service_date, fields.service_time)
    if fields.name is None:
        return (*identity, fields.patient, fields.shift)
    return identity


def employee_import_identity_clause(identity: tuple):
    name, service_date, service_time, *unassigned_fields = identity
    conditions = [
        EmployeeAvailability.name.is_(None)
        if name is None
        else EmployeeAvailability.name == name,
        EmployeeAvailability.service_date == service_date,
        EmployeeAvailability.service_time.is_(None)
        if service_time is None
        else EmployeeAvailability.service_time == service_time,
    ]
    if name is None:
        patient, shift = unassigned_fields
        conditions.extend(
            [
                EmployeeAvailability.patient.is_(None)
                if patient is None
                else EmployeeAvailability.patient == patient,
                EmployeeAvailability.shift == shift,
            ]
        )
    return and_(*conditions)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


@app.get("/api/employees", response_model=list[EmployeeRead], dependencies=[Depends(require_api_key)])
def list_employees(
    db: Session = Depends(get_db),
    name: str | None = None,
    patient: str | None = None,
    shift: str | None = None,
    available: Literal["true", "false", "null"] | None = None,
    service_date: date | None = None,
    service_date_from: date | None = None,
    service_date_to: date | None = None,
    service_time_from: time | None = None,
    service_time_to: time | None = None,
    limit: int = Query(default=500, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    if (
        service_date_from is not None
        and service_date_to is not None
        and service_date_from > service_date_to
    ):
        raise HTTPException(status_code=422, detail="A data inicial não pode ser posterior à data final")
    if (
        service_time_from is not None
        and service_time_to is not None
        and service_time_from > service_time_to
    ):
        raise HTTPException(status_code=422, detail="A hora inicial não pode ser posterior à hora final")
    query = select(EmployeeAvailability)
    if name:
        query = query.where(EmployeeAvailability.name.ilike(f"%{name.strip()}%"))
    if patient:
        query = query.where(EmployeeAvailability.patient.ilike(f"%{patient.strip()}%"))
    if shift:
        query = query.where(EmployeeAvailability.shift == shift)
    if available == "null":
        query = query.where(EmployeeAvailability.available.is_(None))
    elif available is not None:
        query = query.where(EmployeeAvailability.available == (available == "true"))
    if service_date is not None:
        query = query.where(EmployeeAvailability.service_date == service_date)
    if service_date_from is not None:
        query = query.where(EmployeeAvailability.service_date >= service_date_from)
    if service_date_to is not None:
        query = query.where(EmployeeAvailability.service_date <= service_date_to)
    if service_time_from is not None:
        query = query.where(EmployeeAvailability.service_time >= service_time_from)
    if service_time_to is not None:
        query = query.where(EmployeeAvailability.service_time <= service_time_to)
    query = query.order_by(
        EmployeeAvailability.service_date,
        EmployeeAvailability.service_time,
        EmployeeAvailability.name,
    )
    return db.scalars(query.limit(limit).offset(offset)).all()


@app.post("/api/employees", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_api_key)])
def create_employee(fields: EmployeeCreate, db: Session = Depends(get_db)):
    record = EmployeeAvailability()
    apply_fields(record, fields)
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe disponibilidade para esse funcionário, data e horário") from exc
    db.refresh(record)
    return record


@app.put("/api/employees/{employee_id}", response_model=EmployeeRead, dependencies=[Depends(require_api_key)])
def update_employee(employee_id: int, fields: EmployeeUpdate, db: Session = Depends(get_db)):
    record = db.get(EmployeeAvailability, employee_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    apply_fields(record, fields)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe disponibilidade para esse funcionário, data e horário") from exc
    db.refresh(record)
    return record


@app.patch(
    "/api/employees/{employee_id}/attendance",
    response_model=EmployeeRead,
    dependencies=[Depends(require_api_key)],
)
def update_employee_attendance(
    employee_id: int,
    fields: AttendanceUpdate,
    db: Session = Depends(get_db),
):
    service = PlantaoService(PlantaoRepository(db))
    try:
        return service.confirm_result(employee_id, fields.attendance_status)
    except PlantaoNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Registro não encontrado") from exc
    except PlantaoSemFuncionarioError as exc:
        raise HTTPException(
            status_code=422,
            detail="Não é possível registrar o resultado sem um funcionário escalado",
        ) from exc


@app.delete("/api/employees/assigned", dependencies=[Depends(require_api_key)])
def delete_assigned_employees(db: Session = Depends(get_db)):
    result = db.execute(
        delete(EmployeeAvailability).where(EmployeeAvailability.name.is_not(None))
    )
    db.commit()
    return {"deleted": result.rowcount or 0}


@app.delete("/api/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_api_key)])
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    record = db.get(EmployeeAvailability, employee_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    db.delete(record)
    db.commit()


@app.post("/api/employees/import", response_model=ImportResult, dependencies=[Depends(require_api_key)])
def import_employees(rows: list[EmployeeCreate], db: Session = Depends(get_db)):
    if not rows:
        raise HTTPException(status_code=422, detail="O arquivo não contém registros")
    if len(rows) > 5000:
        raise HTTPException(status_code=413, detail="Importe no máximo 5.000 registros por arquivo")

    created = 0
    updated = 0
    try:
        identities = list(dict.fromkeys(employee_import_identity(fields) for fields in rows))
        existing_by_identity = {}
        for start in range(0, len(identities), 200):
            batch = identities[start : start + 200]
            conditions = [employee_import_identity_clause(identity) for identity in batch]
            records = db.scalars(
                select(EmployeeAvailability).where(or_(*conditions))
            ).all()
            for record in records:
                existing_by_identity.setdefault(
                    employee_import_identity(record), record
                )

        new_records = []
        for fields in rows:
            identity = employee_import_identity(fields)
            record = existing_by_identity.get(identity)
            if record is None:
                record = EmployeeAvailability()
                apply_fields(record, fields)
                existing_by_identity[identity] = record
                new_records.append(record)
                created += 1
            else:
                updated += 1
                apply_fields(record, fields)
        if new_records:
            db.execute(
                insert(EmployeeAvailability),
                [
                    {
                        "employee_code": record.employee_code,
                        "name": record.name,
                        "patient": record.patient,
                        "shift": record.shift,
                        "service_date": record.service_date,
                        "service_time": record.service_time,
                        "service_end_time": record.service_end_time,
                        "available": record.available,
                        "attendance_status": record.attendance_status,
                        "attendance_confirmed_at": record.attendance_confirmed_at,
                    }
                    for record in new_records
                ],
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Não foi possível concluir a importação por conflito de registros") from exc
    return ImportResult(created=created, updated=updated)




@app.get("/dashboard/{object}", dependencies=[Depends(require_api_key)])
def get_dashboard_object(object: str, db: Session = Depends(get_db)):
    if object == "employees":
        return list_employees(db)
    else:
        raise HTTPException(status_code=404, detail="Objeto de dashboard não encontrado")   
    
    