from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session

from .models import EmployeeAvailability


class PlantaoResult(str, Enum):
    REALIZADO = "present"
    FALTA = "absent"
    CANCELADO = "cancelled"
    SUBSTITUIDO = "replaced"


class PlantaoNotFoundError(Exception):
    pass


class PlantaoSemFuncionarioError(Exception):
    pass


class PlantaoRepository:
    def __init__(self, session: Session):
        self._session = session

    def get(self, plantao_id: int) -> EmployeeAvailability | None:
        return self._session.get(EmployeeAvailability, plantao_id)

    def save(self, plantao: EmployeeAvailability) -> EmployeeAvailability:
        self._session.commit()
        self._session.refresh(plantao)
        return plantao


class PlantaoService:
    def __init__(
        self,
        repository: PlantaoRepository,
        clock=lambda: datetime.now(timezone.utc),
    ):
        self._repository = repository
        self._clock = clock

    def confirm_result(
        self,
        plantao_id: int,
        result: PlantaoResult | None,
    ) -> EmployeeAvailability:
        plantao = self._repository.get(plantao_id)
        if plantao is None:
            raise PlantaoNotFoundError
        if plantao.name is None:
            raise PlantaoSemFuncionarioError
        plantao.attendance_status = result.value if result is not None else None
        plantao.attendance_confirmed_at = self._clock() if result is not None else None
        return self._repository.save(plantao)
