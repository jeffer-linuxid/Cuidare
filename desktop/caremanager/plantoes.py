from bisect import bisect_left
from collections import defaultdict
from datetime import date, datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
)

from .api import ApiError, CareManagerApi

PLANTAO_STATUS_LABELS = {
    None: "Pendente",
    "present": "Realizado",
    "absent": "Falta",
    "cancelled": "Cancelado",
    "replaced": "Substituído",
}

_PLANTAO_COLUMNS = (
    ("employee_code", "Código"),
    ("name", "Funcionário"),
    ("service_date", "Data"),
    ("service_time", "Horário"),
    ("shift", "Turno"),
    ("attendance_status", "Resultado"),
    ("attendance_confirmed_at", "Confirmado em"),
    ("absence_risk", "Risco histórico"),
    ("absence_basis", "Base anterior"),
)


class PlantaoTableModel(QAbstractTableModel):
    def __init__(self, records=(), parent=None):
        super().__init__(parent)
        self._records = []
        self._estimates = {}
        self.set_records(records)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._records)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(_PLANTAO_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return _PLANTAO_COLUMNS[section][1]
        return str(section + 1)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._records)):
            return None
        record = self._records[index.row()]
        if role == Qt.ItemDataRole.UserRole:
            return record["id"]
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        key = _PLANTAO_COLUMNS[index.column()][0]
        if key == "employee_code":
            return record.get(key) or "—"
        if key == "service_date":
            return datetime.strptime(record[key], "%Y-%m-%d").strftime("%d/%m/%Y")
        if key == "service_time":
            start = record.get("service_time")
            end = record.get("service_end_time")
            if start and end:
                return f"{start[:5]} - {end[:5]}"
            return start[:5] if start else "—"
        if key == "attendance_status":
            return PLANTAO_STATUS_LABELS.get(record.get(key), "Pendente")
        if key == "attendance_confirmed_at":
            return self.format_confirmation(record.get(key))
        if key in {"absence_risk", "absence_basis"}:
            return self._estimates.get(record["id"], ("—", "—", None))[
                0 if key == "absence_risk" else 1
            ]
        return record.get(key) or "—"

    def set_records(self, records):
        self.beginResetModel()
        self._records = list(records)
        self._estimates = self.absence_estimates(self._records)
        self.endResetModel()

    def record_at(self, row):
        if not 0 <= row < len(self._records):
            return None
        return self._records[row]

    def update_record(self, record):
        for row, current in enumerate(self._records):
            if current["id"] == record["id"]:
                self._records[row] = {**current, **record}
                self._estimates = self.absence_estimates(self._records)
                if self._records:
                    self.dataChanged.emit(
                        self.index(0, 0),
                        self.index(len(self._records) - 1, self.columnCount() - 1),
                        [Qt.ItemDataRole.DisplayRole],
                    )
                return

    def status_counts(self):
        counts = {status: 0 for status in PLANTAO_STATUS_LABELS}
        for record in self._records:
            status = record.get("attendance_status")
            counts[status if status in counts else None] += 1
        return counts

    @property
    def records(self):
        return tuple(self._records)

    @property
    def estimates(self):
        return dict(self._estimates)

    def estimate_counts(self):
        return (
            sum(result[2] is True for result in self._estimates.values()),
            sum(result[2] is False for result in self._estimates.values()),
        )

    @classmethod
    def absence_estimates(cls, records):
        today = date.today()
        history_by_employee = defaultdict(list)
        for record in records:
            service_date = date.fromisoformat(record["service_date"])
            status = record.get("attendance_status")
            employee_key = cls.employee_key(record)
            if (
                service_date < today
                and status in {"present", "absent"}
                and record.get("attendance_confirmed_at")
                and employee_key is not None
            ):
                history_by_employee[employee_key].append(
                    (service_date, status == "absent")
                )

        indexed_history = {}
        for employee_key, history in history_by_employee.items():
            history.sort(key=lambda result: result[0])
            dates = []
            absence_totals = [0]
            for service_date, was_absent in history:
                dates.append(service_date)
                absence_totals.append(absence_totals[-1] + was_absent)
            indexed_history[employee_key] = dates, absence_totals

        estimates = {}
        for record in records:
            service_date = date.fromisoformat(record["service_date"])
            if service_date < today or record.get("attendance_status") is not None:
                continue
            employee_key = cls.employee_key(record)
            if employee_key is None:
                estimates[record["id"]] = ("Sem identificação", "—", False)
                continue
            dates, absence_totals = indexed_history.get(employee_key, ([], [0]))
            sample_size = bisect_left(dates, service_date)
            if sample_size < 10:
                estimates[record["id"]] = (
                    "Dados insuficientes",
                    f"{sample_size}/10 resultados",
                    False,
                )
                continue
            absences = absence_totals[sample_size]
            estimates[record["id"]] = (
                f"{absences / sample_size:.0%}",
                f"{absences}/{sample_size}",
                True,
            )
        return estimates

    @staticmethod
    def employee_key(record):
        employee_code = (record.get("employee_code") or "").strip().casefold()
        if employee_code:
            return "code", employee_code
        name = (record.get("name") or "").strip().casefold()
        return ("name", name) if name else None

    @staticmethod
    def format_confirmation(value):
        if not value:
            return "—"
        confirmed_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return confirmed_at.astimezone().strftime("%d/%m/%Y %H:%M")


class PlantaoController:
    def __init__(self, api: CareManagerApi):
        self._api = api

    def list_plantoes(self):
        return [
            record
            for record in self._api.list_employees()
            if record.get("name")
        ]

    def confirm_result(self, plantao_id, result):
        return self._api.update_employee_attendance(plantao_id, result)


class PlantaoControlDialog(QDialog):
    def __init__(self, api: CareManagerApi, parent=None):
        super().__init__(parent)
        self._controller = PlantaoController(api)
        self._model = PlantaoTableModel(parent=self)
        self.setWindowTitle("Controle de plantões")
        self.resize(1040, 680)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(14)

        heading = QHBoxLayout()
        heading_copy = QVBoxLayout()
        title = QLabel("Plantões")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Registre os resultados e consulte o histórico de faltas em escalas futuras."
        )
        subtitle.setStyleSheet("color: #69817d;")
        heading_copy.addWidget(title)
        heading_copy.addWidget(subtitle)
        heading.addLayout(heading_copy)
        heading.addStretch()
        refresh_button = QPushButton("Atualizar")
        refresh_button.clicked.connect(self.load_records)
        heading.addWidget(refresh_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet(
            "color: #45635e; background: #eaf3f0; border-radius: 8px; padding: 11px;"
        )
        layout.addWidget(self.summary)

        self.table = QTableView()
        self.table.setModel(self._model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setShowGrid(False)
        self.table.selectionModel().currentRowChanged.connect(self.load_selected_result)
        layout.addWidget(self.table, 1)

        result_row = QHBoxLayout()
        self.result_box = QComboBox()
        for value, label in PLANTAO_STATUS_LABELS.items():
            self.result_box.addItem(label, value)
        result_row.addWidget(QLabel("Resultado do plantão:"))
        result_row.addWidget(self.result_box)
        save_button = QPushButton("Salvar resultado")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.save_result)
        result_row.addWidget(save_button)
        result_row.addStretch()
        layout.addLayout(result_row)

        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, 0, Qt.AlignmentFlag.AlignRight)
        self.load_records()

    def load_records(self):
        try:
            records = self._controller.list_plantoes()
        except ApiError as exc:
            QMessageBox.critical(self, "Erro ao carregar plantões", str(exc))
            return
        self._model.set_records(records)
        if records:
            self.table.setCurrentIndex(self._model.index(0, 0))
        else:
            self.result_box.setCurrentIndex(0)
            self.result_box.setEnabled(False)
        self.update_summary()

    def load_selected_result(self, current, _previous):
        record = self._model.record_at(current.row())
        if record is None:
            self.result_box.setEnabled(False)
            return
        self.result_box.setEnabled(True)
        self.result_box.setCurrentIndex(
            self.result_box.findData(record.get("attendance_status"))
        )

    def save_result(self):
        record = self._model.record_at(self.table.currentIndex().row())
        if record is None:
            QMessageBox.information(
                self, "Selecione um plantão", "Escolha um plantão na lista."
            )
            return
        try:
            updated = self._controller.confirm_result(
                record["id"], self.result_box.currentData()
            )
        except ApiError as exc:
            QMessageBox.critical(
                self, "Não foi possível salvar o resultado do plantão", str(exc)
            )
            return
        self._model.update_record(updated)
        self.update_summary()

    def update_summary(self):
        counts = self._model.status_counts()
        forecastable, insufficient = self._model.estimate_counts()
        confirmed = len(self._model.records) - counts[None]
        self.summary.setText(
            f"{confirmed} resultado(s) confirmado(s) · "
            f"{counts['present']} realizado(s) · {counts['absent']} falta(s) · "
            f"{counts['cancelled']} cancelado(s) · {counts['replaced']} substituído(s) · "
            f"{counts[None]} pendente(s). Plantões futuros com histórico suficiente: "
            f"{forecastable}; com menos de 10 resultados anteriores: {insufficient}. "
            "Estimativa exploratória baseada em resultados anteriores, não é garantia."
        )
