import csv
import io
import os
import re
from datetime import date, datetime
from pathlib import Path
import unicodedata

from PySide6.QtCore import QRegularExpression, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .api import ApiError, CareManagerApi
from .analytics import AnalyticsDialog
from .plantoes import PLANTAO_STATUS_LABELS, PlantaoControlDialog

APP_STYLESHEET = """
QWidget {
    color: #203b39;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QDialog {
    background: #f3f7f6;
}
QLabel#eyebrow {
    color: #64817d;
    font-size: 9pt;
    font-weight: 700;
}
QLabel#pageTitle {
    color: #173a36;
    font-size: 23pt;
    font-weight: 700;
}
QLabel#sectionTitle {
    color: #173a36;
    font-size: 13pt;
    font-weight: 700;
}
QFrame#sidebar {
    background: #123b36;
}
QLabel#brandName {
    color: #444444;
    font-size: 15pt;
    font-weight: 700;
}
QLabel#brandCaption, QLabel#sidebarCaption {
    color: #aac3be;
    font-size: 9pt;
}
QLabel#sidebarSection {
    color: #8eaca6;
    font-size: 8pt;
    font-weight: 700;
}
QPushButton {
    color: #234541;
    background: #ffffff;
    border: 1px solid #dce8e5;
    border-radius: 9px;
    padding: 10px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background: #edf6f3;
    border-color: #b7d5cd;
}
QPushButton:pressed {
    background: #deeee9;
}
QPushButton#primaryButton {
    color: #ffffff;
    background: #167966;
    border: 1px solid #167966;
}
QPushButton#primaryButton:hover {
    background: #126b5a;
}
QPushButton#sidebarButton {
    color: #d3e2de;
    background: transparent;
    border: 0;
    border-radius: 8px;
    text-align: left;
    padding: 12px 14px;
}
QPushButton#sidebarButton:hover, QPushButton#sidebarButton[active="true"] {
    color: #ffffff;
    background: #24574f;
}
QPushButton#dangerButton {
    color: #a63d42;
    background: #fff8f7;
    border-color: #f1d8d6;
}
QLineEdit, QComboBox {
    color: #203b39;
    background: #ffffff;
    border: 1px solid #d8e4e1;
    border-radius: 8px;
    padding: 9px 11px;
    selection-background-color: #167966;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #53a28e;
}
QComboBox::drop-down {
    border: 0;
    width: 25px;
}
QFrame#surface, QFrame#statCard {
    background: #ffffff;
    border: 1px solid #e3ece9;
    border-radius: 13px;
}
QFrame#heroCard {
    background: #174b43;
    border: 0;
    border-radius: 16px;
}
QLabel#heroTitle {
    color: #444444;
    font-size: 21pt;
    font-weight: 700;
}
QLabel#heroText {
    color: #d2e8e1;
    font-size: 10pt;
}
QLabel#statValue {
    color: #173a36;
    font-size: 23pt;
    font-weight: 700;
}
QLabel#statCaption {
    color: #69817d;
    font-size: 9pt;
}
QTableWidget {
    color: #274541;
    background: #ffffff;
    alternate-background-color: #f7faf9;
    border: 1px solid #e3ece9;
    border-radius: 9px;
    gridline-color: #edf2f0;
    selection-background-color: #e2f2ed;
    selection-color: #173a36;
}
QHeaderView::section {
    color: #66807b;
    background: #f5f8f7;
    border: 0;
    border-bottom: 1px solid #e3ece9;
    padding: 11px 9px;
    font-size: 9pt;
    font-weight: 700;
}
QDialogButtonBox QPushButton {
    min-width: 90px;
}
"""

FIELDS = [
    ("employee_code", "Código do funcionário"),
    ("name", "Funcionário"),
    ("patient", "Paciente"),
    ("shift", "Turno"),
    ("service_date", "Data"),
    ("service_time", "Horário inicial"),
    ("service_end_time", "Horário final"),
    ("available", "Disponibilidade"),
    ("attendance_status", "Resultado do plantão"),
    ("attendance_confirmed_at", "Data da confirmação"),
]


def as_employee(record):
    return {
        "id": record["id"],
        "employee_code": record.get("employee_code"),
        "name": record["name"],
        "patient": record.get("patient"),
        "shift": record["shift"],
        "service_date": record["service_date"],
        "service_time": record["service_time"],
        "service_end_time": record.get("service_end_time"),
        "available": record["available"],
        "attendance_status": record.get("attendance_status"),
        "attendance_confirmed_at": record.get("attendance_confirmed_at"),
    }


class ConnectionDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Conectar ao CareManager")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 28, 30, 24)
        layout.setSpacing(16)
        title = QLabel("Bem-vindo ao CareManager")
        title.setObjectName("sectionTitle")
        description = QLabel("Conecte-se ao servidor para acessar a gestão da equipe.")
        description.setWordWrap(True)
        description.setStyleSheet("color: #69817d;")
        form = QFormLayout()
        form.setVerticalSpacing(12)
        self.url = QLineEdit(os.environ.get("CAREMANAGER_API_URL", "http://127.0.0.1:8000"))
        self.key = QLineEdit(os.environ.get("CAREMANAGER_API_KEY", ""))
        self.key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Endereço do servidor", self.url)
        form.addRow("Chave de acesso", self.key)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(form)
        buttons = QDialogButtonBox()
        connect = buttons.addButton("Conectar", QDialogButtonBox.ButtonRole.AcceptRole)
        connect.setObjectName("primaryButton")
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        connect.clicked.connect(self.connect_to_server)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.api = None

    def connect_to_server(self):
        address = self.url.text().strip()
        if not address.startswith(("http://", "https://")):
            QMessageBox.warning(self, "Endereço inválido", "Informe um endereço iniciado por http:// ou https://.")
            return
        self.api = CareManagerApi(address, self.key.text())
        try:
            self.api.check_connection()
        except ApiError as exc:
            QMessageBox.critical(self, "Falha na conexão", str(exc))
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, api: CareManagerApi):
        super().__init__()
        self.api = api
        self.setWindowTitle("CareManager")
        self.resize(1160, 780)
        self.setMinimumSize(500, 380)
        content = QWidget()
        root = QHBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(228)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 24, 18, 20)
        side_layout.setSpacing(10)
        brand = QHBoxLayout()
        brand_mark = QLabel("CM")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setFixedSize(42, 42)
        brand_mark.setStyleSheet(
            "color: #ffffff; background: #2f7668; border-radius: 12px; "
            "font-size: 13pt; font-weight: 700;"
        )
        brand_text = QVBoxLayout()
        brand_name = QLabel("CareManager")
        brand_name.setObjectName("brandName")
        brand_caption = QLabel("GESTÃO DE CUIDADOS")
        brand_caption.setObjectName("brandCaption")
        brand_text.addWidget(brand_name)
        brand_text.addWidget(brand_caption)
        brand.addWidget(brand_mark)
        brand.addLayout(brand_text)
        side_layout.addLayout(brand)
        side_layout.addSpacing(34)
        nav_caption = QLabel("ESPAÇO DE TRABALHO")
        nav_caption.setObjectName("sidebarSection")
        side_layout.addWidget(nav_caption)
        overview_button = QPushButton("Visão geral")
        overview_button.setObjectName("sidebarButton")
        overview_button.setProperty("active", True)
        overview_button.setEnabled(False)
        control_button = QPushButton("Controle de funcionários")
        control_button.setObjectName("sidebarButton")
        control_button.clicked.connect(self.open_control)
        import_button = QPushButton("Importar funcionários")
        import_button.setObjectName("sidebarButton")
        import_button.clicked.connect(self.open_import)
        plantoes_button = QPushButton("Plantões")
        plantoes_button.setObjectName("sidebarButton")
        plantoes_button.clicked.connect(self.open_plantoes)
        analytics_button = QPushButton("Análises")
        analytics_button.setObjectName("sidebarButton")
        analytics_button.clicked.connect(self.open_analytics)
        side_layout.addWidget(overview_button)
        side_layout.addWidget(control_button)
        side_layout.addWidget(import_button)
        side_layout.addWidget(plantoes_button)
        side_layout.addWidget(analytics_button)
        side_layout.addStretch()
        connected = QLabel("●  SERVIDOR CONECTADO")
        connected.setStyleSheet("color: #9ce0c7; font-size: 8pt; font-weight: 700;")
        server_address = QLabel(api.base_url)
        server_address.setObjectName("sidebarCaption")
        server_address.setWordWrap(True)
        side_layout.addWidget(connected)
        side_layout.addWidget(server_address)

        main_area = QWidget()
        main_area.setStyleSheet("background: #f3f7f6;")
        page = QVBoxLayout(main_area)
        page.setContentsMargins(36, 27, 36, 30)
        page.setSpacing(22)
        topbar = QHBoxLayout()
        breadcrumb = QLabel("PAINEL  /  VISÃO GERAL")
        breadcrumb.setObjectName("eyebrow")
        topbar.addWidget(breadcrumb)
        topbar.addStretch()
        profile = QLabel("  CM   Administrador")
        profile.setStyleSheet(
            "color: #45635e; background: #ffffff; border: 1px solid #e3ece9; "
            "border-radius: 18px; padding: 8px 12px; font-weight: 600;"
        )
        topbar.addWidget(profile)
        page.addLayout(topbar)

        heading = QVBoxLayout()
        heading.setSpacing(5)
        title = QLabel("Sua equipe, em harmonia.")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Acompanhe a disponibilidade e organize os turnos de atendimento.")
        subtitle.setStyleSheet("color: #6a827e; font-size: 10pt;")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        page.addLayout(heading)

        hero = QFrame()
        hero.setObjectName("heroCard")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(26, 22, 24, 22)
        hero_layout.setSpacing(16)
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(8)
        hero_kicker = QLabel("CUIDADO QUE CONECTA")
        hero_kicker.setStyleSheet("color: #9ed5c4; font-size: 8pt; font-weight: 700;")
        hero_title = QLabel("Uma equipe bem cuidada\ntransforma cada atendimento.")
        hero_title.setObjectName("heroTitle")
        hero_description = QLabel("Mantenha horários e disponibilidade sempre organizados.")
        hero_description.setObjectName("heroText")
        hero_description.setWordWrap(True)
        hero_copy.addWidget(hero_kicker)
        hero_copy.addWidget(hero_title)
        hero_copy.addWidget(hero_description)
        hero_layout.addLayout(hero_copy, 1)
        self.manage_button = QPushButton("Abrir controle da equipe")
        self.manage_button.setObjectName("primaryButton")
        self.manage_button.setMinimumHeight(44)
        self.manage_button.clicked.connect(self.open_control)
        hero_layout.addWidget(self.manage_button, 0, Qt.AlignmentFlag.AlignBottom)
        page.addWidget(hero)

        cards = QGridLayout()
        cards.setSpacing(14)
        self.total_value = self.add_stat_card(cards, 0, "REGISTROS DE DISPONIBILIDADE", "—")
        self.available_value = self.add_stat_card(cards, 1, "DISPONÍVEIS", "—")
        self.shifts_value = self.add_stat_card(cards, 2, "TURNOS CADASTRADOS", "—")
        page.addLayout(cards)

        section_header = QHBoxLayout()
        section_title = QLabel("Acesso rápido")
        section_title.setObjectName("sectionTitle")
        section_header.addWidget(section_title)
        section_header.addStretch()
        section_hint = QLabel("Escolha por onde deseja começar")
        section_hint.setStyleSheet("color: #78908b;")
        section_header.addWidget(section_hint)
        page.addLayout(section_header)

        shortcuts = QHBoxLayout()
        shortcuts.setSpacing(14)
        control_card = self.make_shortcut(
            "01", "Controle de funcionários",
            "Pesquise, atualize e exporte os registros da equipe.",
            self.open_control,
        )
        import_card = self.make_shortcut(
            "02", "Importar arquivo CSV",
            "Traga os dados da sua equipe com pré-visualização.",
            self.open_import,
        )
        analytics_card = self.make_shortcut(
            "03", "Análises da equipe",
            "Visualize disponibilidade, turnos e tendências dos registros.",
            self.open_analytics,
        )
        shortcuts.addWidget(control_card)
        shortcuts.addWidget(import_card)
        shortcuts.addWidget(analytics_card)
        page.addLayout(shortcuts)
        page.addStretch()

        footer = QLabel("CareManager  ·  Organização simples para um cuidado melhor")
        footer.setStyleSheet("color: #91a49f; font-size: 9pt;")
        page.addWidget(footer)
        root.addWidget(sidebar)
        root.addWidget(main_area, 1)
        self.setCentralWidget(content)
        self.refresh_dashboard()

    @staticmethod
    def add_stat_card(layout, column, caption, value):
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 15, 18, 16)
        card_layout.setSpacing(8)
        number = QLabel(value)
        number.setObjectName("statValue")
        label = QLabel(caption)
        label.setObjectName("statCaption")
        card_layout.addWidget(number)
        card_layout.addWidget(label)
        layout.addWidget(card, 0, column)
        return number

    @staticmethod
    def make_shortcut(number, title, description, callback):
        card = QFrame()
        card.setObjectName("surface")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 17)
        card_layout.setSpacing(8)
        marker = QLabel(number)
        marker.setStyleSheet("color: #16816b; font-size: 9pt; font-weight: 700;")
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: #738a85;")
        action = QPushButton("Acessar")
        action.setObjectName("primaryButton")
        action.clicked.connect(callback)
        card_layout.addWidget(marker)
        card_layout.addWidget(title_label)
        card_layout.addWidget(description_label)
        card_layout.addStretch()
        card_layout.addWidget(action, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    def refresh_dashboard(self):
        try:
            records = self.api.list_employees()
        except ApiError as exc:
            QMessageBox.warning(self, "Painel desatualizado", str(exc))
            return
        self.total_value.setText(str(len(records)))
        self.available_value.setText(str(sum(bool(record["available"]) for record in records)))
        self.shifts_value.setText(str(len({record["shift"] for record in records})))

    def open_import(self):
        dialog = CsvImportDialog(self.api, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh_dashboard()
            QMessageBox.information(self, "Importação concluída", dialog.result_message)

    def open_control(self):
        EmployeeControlDialog(self.api, self).exec()
        self.refresh_dashboard()

    def open_analytics(self):
        try:
            records = self.api.list_employees()
        except ApiError as exc:
            QMessageBox.warning(self, "Não foi possível carregar as análises", str(exc))
            return
        AnalyticsDialog(records, self).exec()

    def open_plantoes(self):
        PlantaoControlDialog(self.api, self).exec()


class EmployeeFormDialog(QDialog):
    def __init__(self, parent=None, record=None, choices=None):
        super().__init__(parent)
        choices = choices or {}
        self.setWindowTitle("Editar funcionário" if record else "Adicionar funcionário")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(18)
        heading = QLabel("Atualize as informações do turno." if record else "Cadastre uma nova disponibilidade.")
        heading.setStyleSheet("color: #69817d;")
        form = QFormLayout()
        form.setVerticalSpacing(12)
        self.employee_code = QLineEdit(
            (record.get("employee_code") or "") if record else ""
        )
        self.employee_code.setMaxLength(80)
        self.employee_code.setPlaceholderText("Opcional; identificador estável")
        if record:
            self.name = QLineEdit(record.get("name") or "")
            self.patient = QLineEdit(record.get("patient") or "")
            self.shift = QLineEdit(record["shift"])
        else:
            self.name = ChoiceTextField(
                "Funcionário", choices.get("name", ())
            )
            self.name.setMaxLength(120)
            self.patient = ChoiceTextField(
                "Paciente", choices.get("patient", ())
            )
            self.patient.setMaxLength(120)
            self.shift = ChoiceTextField(
                "Turno", choices.get("shift", ())
            )
            self.shift.setMaxLength(80)
        self.service_date = QLineEdit(record["service_date"] if record else date.today().isoformat())
        self.service_date.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"\d{4}-\d{2}-\d{2}"), self.service_date)
        )
        self.service_time = QLineEdit(
            record["service_time"][:5] if record and record["service_time"] else "08:00"
        )
        self.service_time.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"\d{2}:\d{2}"), self.service_time)
        )
        self.service_end_time = QLineEdit(
            record["service_end_time"][:5]
            if record and record.get("service_end_time")
            else ""
        )
        self.service_end_time.setPlaceholderText("Opcional (HH:MM)")
        self.service_end_time.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"\d{2}:\d{2}"), self.service_end_time)
        )
        self.available = QComboBox()
        self.available.addItem("Sim", True)
        self.available.addItem("Não", False)
        self.available.addItem("Não informado", None)
        if record:
            self.available.setCurrentIndex(self.available.findData(record["available"]))
        form.addRow("Código do funcionário (opcional)", self.employee_code)
        form.addRow("Funcionário", self.name)
        form.addRow("Paciente (opcional)", self.patient)
        form.addRow("Turno", self.shift)
        form.addRow("Data (AAAA-MM-DD)", self.service_date)
        form.addRow("Início (HH:MM)", self.service_time)
        form.addRow("Fim (HH:MM)", self.service_end_time)
        form.addRow("Disponível", self.available)

        layout.addWidget(heading)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("primaryButton")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def employee(self):
        name = self.field_text(self.name)
        patient = self.field_text(self.patient)
        shift = self.field_text(self.shift)
        if not shift:
            raise ValueError("Preencha o turno.")
        if len(patient) > 120:
            raise ValueError("O nome do paciente deve ter até 120 caracteres.")
        try:
            service_date = datetime.strptime(self.service_date.text().strip(), "%Y-%m-%d").date()
            service_time_text = self.service_time.text().strip()
            service_end_time_text = self.service_end_time.text().strip()
            service_time = (
                datetime.strptime(service_time_text, "%H:%M").time()
                if service_time_text
                else None
            )
            service_end_time = (
                datetime.strptime(service_end_time_text, "%H:%M").time()
                if service_end_time_text
                else None
            )
        except ValueError as exc:
            raise ValueError("Data ou hora inválida. Use AAAA-MM-DD e HH:MM.") from exc
        if name and service_time is None:
            raise ValueError("Informe o horário de início quando houver funcionário escalado.")
        if service_end_time and service_time is None:
            raise ValueError("Informe o início do plantão antes do horário de fim.")
        return {
            "employee_code": self.employee_code.text().strip() or None,
            "name": name or None,
            "patient": patient or None,
            "shift": shift,
            "service_date": service_date.isoformat(),
            "service_time": service_time.strftime("%H:%M:%S") if service_time else None,
            "service_end_time": (
                service_end_time.strftime("%H:%M:%S") if service_end_time else None
            ),
            "available": self.available.currentData(),
        }

    @staticmethod
    def field_text(field):
        if isinstance(field, ChoiceTextField):
            return field.text().strip()
        return field.text().strip()


class ChoiceTextField(QWidget):
    def __init__(self, placeholder, values=(), parent=None):
        super().__init__(parent)
        self._values = sorted(
            {str(value).strip() for value in values if value and str(value).strip()}
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.line_edit = QLineEdit()
        self.line_edit.setPlaceholderText(placeholder)
        self.button = QToolButton()
        self.button.setText("▼")
        self.button.setToolTip("Selecionar um valor cadastrado")
        self.button.clicked.connect(self.open_choices)
        layout.addWidget(self.line_edit, 1)
        layout.addWidget(self.button)

    def setMaxLength(self, length):
        self.line_edit.setMaxLength(length)

    def text(self):
        return self.line_edit.text()

    def open_choices(self):
        self.choice_menu().exec(
            self.button.mapToGlobal(self.button.rect().bottomLeft())
        )

    def choice_menu(self):
        menu = QMenu(self)
        if self._values:
            for value in self._values:
                action = menu.addAction(value)
                action.triggered.connect(
                    lambda _checked=False, selected=value:
                    self.line_edit.setText(selected)
                )
        else:
            unavailable = menu.addAction("Nenhum valor cadastrado")
            unavailable.setEnabled(False)
        menu.addSeparator()
        manual_action = menu.addAction("Digitar manualmente")
        manual_action.triggered.connect(
            lambda _checked=False: self.line_edit.setFocus()
        )
        return menu

class EmployeeControlDialog(QDialog):
    def __init__(self, api: CareManagerApi, parent=None):
        super().__init__(parent)
        self.api = api
        self.records = []
        self.setWindowTitle("Controle de funcionários")
        self.resize(1040, 650)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(16)
        heading = QHBoxLayout()
        heading_copy = QVBoxLayout()
        title = QLabel("Controle da equipe")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Consulte e mantenha as disponibilidades em dia.")
        subtitle.setStyleSheet("color: #69817d;")
        heading_copy.addWidget(title)
        heading_copy.addWidget(subtitle)
        heading.addLayout(heading_copy)
        heading.addStretch()
        layout.addLayout(heading)

        filter_panel = QFrame()
        filter_panel.setObjectName("surface")
        filter_layout = QVBoxLayout(filter_panel)
        filter_layout.setContentsMargins(16, 14, 16, 14)
        filter_layout.setSpacing(10)
        filter_title = QLabel("Filtros")
        filter_title.setObjectName("eyebrow")
        filter_layout.addWidget(filter_title)
        filters = QGridLayout()
        filters.setHorizontalSpacing(10)
        filters.setVerticalSpacing(10)
        self.name_filter = QLineEdit()
        self.name_filter.setPlaceholderText("Buscar funcionário pelo nome")
        self.patient_filter = QLineEdit()
        self.patient_filter.setPlaceholderText("Buscar paciente")
        self.shift_filter = QComboBox()
        self.shift_filter.setMinimumWidth(170)
        self.shift_filter.addItems(["Todos os turnos"])
        self.available_filter = QComboBox()
        self.available_filter.setMinimumWidth(185)
        self.available_filter.addItem("Disponibilidade: todas", None)
        self.available_filter.addItem("Disponíveis", True)
        self.available_filter.addItem("Indisponíveis", False)
        self.available_filter.addItem("Não informado", "null")
        self.date_from_filter = QLineEdit()
        self.date_from_filter.setPlaceholderText("Data a partir de (AAAA-MM-DD)")
        self.date_from_filter.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"\d{4}-\d{2}-\d{2}"), self.date_from_filter)
        )
        self.time_from_filter = QLineEdit()
        self.time_from_filter.setPlaceholderText("Hora inicial (HH:MM)")
        self.time_from_filter.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"\d{2}:\d{2}"), self.time_from_filter)
        )
        self.time_to_filter = QLineEdit()
        self.time_to_filter.setPlaceholderText("Hora final (HH:MM)")
        self.time_to_filter.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"\d{2}:\d{2}"), self.time_to_filter)
        )
        filter_button = QPushButton("Aplicar filtros")
        filter_button.setObjectName("primaryButton")
        filter_button.clicked.connect(self.load_records)
        self.name_filter.returnPressed.connect(self.load_records)
        self.patient_filter.returnPressed.connect(self.load_records)
        filters.addWidget(self.name_filter, 0, 0)
        filters.addWidget(self.patient_filter, 0, 1)
        filters.addWidget(self.shift_filter, 0, 2)
        filters.addWidget(self.available_filter, 0, 3)
        filters.addWidget(filter_button, 0, 4)
        filters.addWidget(self.date_from_filter, 1, 0)
        filters.addWidget(self.time_from_filter, 1, 1)
        filters.addWidget(self.time_to_filter, 1, 2)
        filter_layout.addLayout(filters)
        layout.addWidget(filter_panel)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Funcionário", "Paciente", "Turno", "Data", "Hora", "Disponibilidade"]
        )
        self.weekday_tables = {}
        self.selected_weekday_table = None
        self.weekday_view = QScrollArea()
        self.weekday_view.setWidgetResizable(True)
        self.weekday_view.setFrameShape(QFrame.Shape.NoFrame)
        weekday_content = QWidget()
        weekday_layout = QVBoxLayout(weekday_content)
        weekday_layout.setContentsMargins(2, 2, 2, 2)
        weekday_layout.setSpacing(14)
        weekdays = (
            "segunda-feira",
            "terça-feira",
            "quarta-feira",
            "quinta-feira",
            "sexta-feira",
            "sábado",
            "domingo",
        )
        for weekday in weekdays:
            weekday_section = QVBoxLayout()
            weekday_title = QLabel(weekday.capitalize())
            weekday_title.setObjectName("sectionTitle")
            weekday_section.addWidget(weekday_title)
            table = QTableWidget(0, 6)
            table.setHorizontalHeaderLabels(
                ["Funcionário", "Paciente", "Turno", "Data", "Horário", "Disponibilidade"]
            )
            table.doubleClicked.connect(self.edit_record)
            table.itemSelectionChanged.connect(
                lambda table=table: setattr(self, "selected_weekday_table", table)
            )
            self.weekday_tables[weekday] = table
            weekday_section.addWidget(table)
            weekday_layout.addLayout(weekday_section)
        weekday_layout.addStretch()
        self.weekday_view.setWidget(weekday_content)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.table, "Registros")
        self.tabs.addTab(self.weekday_view, "Dias da semana")
        for table in (self.table, *self.weekday_tables.values()):
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.verticalHeader().setDefaultSectionSize(42)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.setShowGrid(False)
        self.table.doubleClicked.connect(self.edit_record)
        layout.addWidget(self.tabs)
        actions = QHBoxLayout()
        for label, callback, object_name in (
            ("Adicionar funcionário", self.add_record, "primaryButton"),
            ("Editar", self.edit_record, ""),
            ("Excluir", self.delete_record, "dangerButton"),
            ("Exportar filtrados CSV", self.export_records, ""),
            ("Baixar todos CSV", self.download_all_records, ""),
            ("Limpar funcionários", self.clear_employees, "dangerButton"),
        ):
            button = QPushButton(label)
            if object_name:
                button.setObjectName(object_name)
            button.clicked.connect(callback)
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.status = QLabel()
        self.status.setStyleSheet("color: #718984;")
        layout.addWidget(self.status)
        self.load_records()

    def load_records(self):
        try:
            service_date_from = self.parse_optional_filter(
                self.date_from_filter.text(), "%Y-%m-%d", "Data inicial"
            )
            service_time_from = self.parse_optional_filter(
                self.time_from_filter.text(), "%H:%M", "Hora inicial"
            )
            service_time_to = self.parse_optional_filter(
                self.time_to_filter.text(), "%H:%M", "Hora final"
            )
            if service_time_from and service_time_to and service_time_from > service_time_to:
                raise ValueError("A hora inicial não pode ser posterior à hora final.")
        except ValueError as exc:
            QMessageBox.warning(self, "Filtro inválido", str(exc))
            return
        try:
            selected_shift = self.shift_filter.currentText()
            records = self.api.list_employees(
                name=self.name_filter.text(),
                patient=self.patient_filter.text(),
                shift="" if selected_shift == "Todos os turnos" else selected_shift,
                available=self.available_filter.currentData(),
                service_date_from=service_date_from,
                service_time_from=service_time_from,
                service_time_to=service_time_to,
            )
        except ApiError as exc:
            QMessageBox.critical(self, "Erro ao carregar", str(exc))
            return
        self.records = [as_employee(record) for record in records]
        if (
            not self.name_filter.text().strip()
            and not self.patient_filter.text().strip()
            and selected_shift == "Todos os turnos"
            and self.available_filter.currentData() is None
            and not service_date_from
            and not service_time_from
            and not service_time_to
        ):
            shifts = sorted({record["shift"] for record in self.records})
            current = self.shift_filter.currentText()
            self.shift_filter.blockSignals(True)
            self.shift_filter.clear()
            self.shift_filter.addItem("Todos os turnos")
            self.shift_filter.addItems(shifts)
            self.shift_filter.setCurrentText(current)
            self.shift_filter.blockSignals(False)
        self.populate_table(
            self.table,
            [(index, record) for index, record in enumerate(self.records)],
        )
        self.selected_weekday_table = None
        records_by_weekday = {weekday: [] for weekday in self.weekday_tables}
        for index, record in enumerate(self.records):
            records_by_weekday[self.weekday_name(record["service_date"])].append((index, record))
        for weekday, table in self.weekday_tables.items():
            weekday_records = records_by_weekday[weekday]
            self.populate_table(table, weekday_records)
            table.setFixedHeight(
                table.horizontalHeader().height() + table.rowCount() * 42 + 2
            )
        self.status.setText(f"{len(self.records)} registro(s) exibido(s).")

    def populate_table(self, table, indexed_records):
        table.setRowCount(len(indexed_records))
        for row, (record_index, record) in enumerate(indexed_records):
            values = (
                record["name"] or "(sem escalado)",
                record.get("patient") or "",
                record["shift"],
                datetime.strptime(record["service_date"], "%Y-%m-%d").strftime("%d/%m/%Y"),
                self.format_service_time(record) or "—",
                self.availability_label(record["available"]),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, record_index)
                table.setItem(row, column, item)

    @staticmethod
    def weekday_name(service_date):
        weekdays = (
            "segunda-feira",
            "terça-feira",
            "quarta-feira",
            "quinta-feira",
            "sexta-feira",
            "sábado",
            "domingo",
        )
        return weekdays[date.fromisoformat(service_date).weekday()]

    @staticmethod
    def parse_optional_filter(value, pattern, label):
        value = value.strip()
        if not value:
            return None
        try:
            return datetime.strptime(value, pattern).strftime(pattern)
        except ValueError as exc:
            expected_format = pattern.replace("%Y-%m-%d", "AAAA-MM-DD").replace("%H:%M", "HH:MM")
            raise ValueError(f"{label} inválida. Use {expected_format}.") from exc

    @staticmethod
    def availability_label(value):
        if value is None:
            return "Não informado"
        return "Sim" if value else "Não"

    @staticmethod
    def format_service_time(record):
        if not record["service_time"]:
            return ""
        start = record["service_time"][:5]
        end_time = record.get("service_end_time")
        return f"{start} - {end_time[:5]}" if end_time else start

    def selected_record(self):
        if self.tabs.currentWidget() is self.table:
            row = self.table.currentRow()
            item = self.table.item(row, 0) if row >= 0 else None
            record_index = item.data(Qt.ItemDataRole.UserRole) if item else None
        else:
            selected_table = self.selected_weekday_table
            row = selected_table.currentRow() if selected_table else -1
            item = selected_table.item(row, 0) if row >= 0 else None
            record_index = item.data(Qt.ItemDataRole.UserRole) if item else None
        if row < 0:
            QMessageBox.information(self, "Selecione um registro", "Selecione um funcionário na tabela.")
            return None
        if record_index is None:
            return None
        return self.records[record_index]

    def add_record(self):
        try:
            records = self.api.list_employees()
        except ApiError as exc:
            QMessageBox.critical(
                self, "Não foi possível carregar as opções", str(exc)
            )
            return
        choices = {
            field: {
                record[field].strip()
                for record in records
                if record.get(field) and record[field].strip()
            }
            for field in ("name", "patient", "shift")
        }
        dialog = EmployeeFormDialog(self, choices=choices)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.api.create_employee(dialog.employee())
        except (ApiError, ValueError) as exc:
            QMessageBox.critical(self, "Não foi possível adicionar", str(exc))
            return
        self.load_records()

    def edit_record(self):
        record = self.selected_record()
        if record is None:
            return
        dialog = EmployeeFormDialog(self, record)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.api.update_employee(record["id"], dialog.employee())
        except (ApiError, ValueError) as exc:
            QMessageBox.critical(self, "Não foi possível editar", str(exc))
            return
        self.load_records()

    def delete_record(self):
        record = self.selected_record()
        if record is None:
            return
        answer = QMessageBox.question(
            self,
            "Confirmar exclusão",
            f"Excluir o registro de {record['name'] or 'furo de plantão'} em {record['service_date']}?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_employee(record["id"])
        except ApiError as exc:
            QMessageBox.critical(self, "Não foi possível excluir", str(exc))
            return
        self.load_records()

    def clear_employees(self):
        answer = QMessageBox.warning(
            self,
            "Limpar funcionários",
            "Isso apagará permanentemente todos os registros associados a funcionários "
            "no banco conectado, inclusive os que não aparecem com os filtros atuais.\n\n"
            "Os furos de plantão sem funcionário serão mantidos. Esta ação não pode ser desfeita.\n\n"
            "Deseja continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = self.api.delete_assigned_employees()
        except ApiError as exc:
            QMessageBox.critical(self, "Não foi possível limpar funcionários", str(exc))
            return
        QMessageBox.information(
            self,
            "Limpeza concluída",
            f"{deleted} registro(s) de funcionários apagado(s). Os furos sem funcionário foram mantidos.",
        )
        self.load_records()

    def export_records(self):
        if not self.records:
            QMessageBox.information(self, "Sem dados", "Não há registros filtrados para exportar.")
            return
        self.save_records_csv(self.records, "funcionarios_filtrados.csv")

    def download_all_records(self):
        try:
            records = [
                as_employee(record) for record in self.api.list_employees()
            ]
        except ApiError as exc:
            QMessageBox.critical(self, "Não foi possível baixar os cadastros", str(exc))
            return
        if not records:
            QMessageBox.information(self, "Sem dados", "Não há cadastros de funcionários para baixar.")
            return
        self.save_records_csv(records, "cadastros_funcionarios.csv")

    def save_records_csv(self, records, default_name):
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar cadastros de funcionários", default_name, "CSV (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(
                    [
                        "ID",
                        "Data",
                        "Dia da semana",
                        "Código do funcionário",
                        "Funcionário",
                        "Paciente",
                        "Turno",
                        "Hora de início",
                        "Hora de fim",
                        "Disponibilidade",
                        "Resultado do plantão",
                        "Confirmado em",
                    ]
                )
                for record in records:
                    writer.writerow([
                        record["id"],
                        datetime.strptime(record["service_date"], "%Y-%m-%d").strftime("%d/%m/%Y"),
                        self.weekday_name(record["service_date"]),
                        record.get("employee_code") or "",
                        record["name"] or "(sem escalado)",
                        record["patient"] or "",
                        record["shift"],
                        record["service_time"][:5] if record["service_time"] else "",
                        record["service_end_time"][:5] if record.get("service_end_time") else "",
                        (
                            "verdadeiro"
                            if record["available"] is True
                            else "falso"
                            if record["available"] is False
                            else ""
                        ),
                        {
                            "present": "realizado",
                            "absent": "falta",
                            "cancelled": "cancelado",
                            "replaced": "substituído",
                        }.get(record.get("attendance_status"), ""),
                        record.get("attendance_confirmed_at") or "",
                    ])
        except OSError as exc:
            QMessageBox.critical(self, "Erro ao exportar", str(exc))
            return
        QMessageBox.information(self, "Exportação concluída", f"Arquivo salvo em:\n{Path(path)}")


class CsvImportDialog(QDialog):
    def __init__(self, api: CareManagerApi, parent=None):
        super().__init__(parent)
        self.api = api
        self.headers = []
        self.rows = []
        self.result_message = ""
        self.setWindowTitle("Importar funcionários CSV")
        self.resize(900, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 24)
        layout.setSpacing(15)
        title = QLabel("Importar funcionários")
        title.setObjectName("pageTitle")
        description = QLabel("Selecione seu CSV, confira o mapeamento e revise os dados antes de importar.")
        description.setWordWrap(True)
        description.setStyleSheet("color: #69817d;")
        layout.addWidget(title)
        layout.addWidget(description)
        file_row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        browse = QPushButton("Selecionar CSV")
        browse.clicked.connect(self.choose_file)
        file_row.addWidget(self.file_path)
        file_row.addWidget(browse)
        layout.addLayout(file_row)
        self.mapping_form = QFormLayout()
        self.mapping_boxes = {}
        for key, label in FIELDS:
            combo = QComboBox()
            combo.currentIndexChanged.connect(self.update_preview)
            self.mapping_boxes[key] = combo
            self.mapping_form.addRow(f"Coluna para {label}", combo)
        layout.addLayout(self.mapping_form)
        layout.addWidget(QLabel("Pré-visualização (até 8 linhas):"))
        self.preview = QTableWidget(0, len(FIELDS))
        self.preview.setHorizontalHeaderLabels([label for _, label in FIELDS])
        self.preview.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.preview)
        self.summary = QLabel("Selecione um arquivo CSV para começar.")
        layout.addWidget(self.summary)
        buttons = QDialogButtonBox()
        self.import_button = buttons.addButton("Importar", QDialogButtonBox.ButtonRole.AcceptRole)
        self.import_button.setObjectName("primaryButton")
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self.import_file)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar CSV", "", "CSV (*.csv);;Todos os arquivos (*)")
        if not path:
            return
        try:
            content = Path(path).read_bytes()
            try:
                text = content.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = content.decode("cp1252")
            try:
                dialect = csv.Sniffer().sniff(text[:4096], delimiters=";,|\t")
            except csv.Error:
                dialect = csv.excel
            reader = csv.DictReader(io.StringIO(text), dialect=dialect)
            raw_headers = reader.fieldnames or []
            self.headers = [header.strip() if header else "" for header in raw_headers]
            if not self.headers or any(not header for header in self.headers):
                raise ValueError("O CSV precisa ter uma linha de cabeçalho com nomes de coluna.")
            if len(set(self.headers)) != len(self.headers):
                raise ValueError("O CSV possui nomes de coluna repetidos após remover espaços.")
            self.rows = [
                {clean: row.get(raw) or "" for raw, clean in zip(raw_headers, self.headers)}
                for row in reader
            ]
            if not self.rows:
                raise ValueError("O CSV não contém linhas de dados.")
        except (OSError, UnicodeDecodeError, csv.Error, ValueError) as exc:
            QMessageBox.critical(self, "CSV inválido", str(exc))
            return
        self.file_path.setText(path)
        self.configure_mapping()

    @staticmethod
    def normalize(value):
        normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
        return re.sub(r"[^a-z0-9]", "", normalized)

    def configure_mapping(self):
        defaults = {
            "employee_code": {
                "codigo",
                "codigodofuncionario",
                "matricula",
                "employeeid",
                "employeecode",
            },
            "name": {"nome", "funcionario", "colaborador", "pessoadaescala", "name"},
            "patient": {"paciente", "patient"},
            "shift": {"turno", "shift"},
            "service_date": {"data", "date"},
            "service_time": {
                "hora",
                "horario",
                "horadeinicio",
                "start",
                "starttime",
                "time",
            },
            "service_end_time": {
                "fim",
                "horafim",
                "horadefim",
                "horariofim",
                "end",
                "endtime",
                "serviceendtime",
            },
            "available": {"disponibilidade", "disponivel", "available"},
            "attendance_status": {
                "resultado",
                "resultadodoplantao",
                "presenca",
                "attendance",
                "attendancestatus",
            },
            "attendance_confirmed_at": {
                "confirmadoem",
                "datadaconfirmacao",
                "dataconfirmacao",
                "attendanceconfirmedat",
            },
        }
        for key, combo in self.mapping_boxes.items():
            combo.clear()
            combo.addItem("— não mapear —", "")
            for header in self.headers:
                combo.addItem(header, header)
            match = next(
                (header for header in self.headers if self.normalize(header) in defaults[key]),
                None,
            )
            if match:
                combo.setCurrentText(match)
        self.update_preview()

    @staticmethod
    def parse_availability(value):
        normalized = value.strip().lower()
        if normalized in {"", "null", "nulo", "nula", "não informado", "nao informado"}:
            return None
        if normalized in {"true", "verdadeiro", "verdadeira", "sim", "yes", "1"}:
            return True
        if normalized in {"false", "falso", "falsa", "não", "nao", "no", "0"}:
            return False
        raise ValueError(f"disponibilidade inválida: {value!r}")

    @staticmethod
    def parse_attendance_status(value):
        normalized = CsvImportDialog.normalize(value.strip())
        if not normalized:
            return None
        statuses = {
            "presente": "present",
            "realizado": "present",
            "realizada": "present",
            "compareceu": "present",
            "present": "present",
            "faltou": "absent",
            "falta": "absent",
            "ausente": "absent",
            "absent": "absent",
            "cancelado": "cancelled",
            "cancelada": "cancelled",
            "cancelled": "cancelled",
            "substituido": "replaced",
            "substituida": "replaced",
            "replaced": "replaced",
        }
        if normalized not in statuses:
            raise ValueError(f"resultado de plantão inválido: {value!r}")
        return statuses[normalized]

    @staticmethod
    def parse_attendance_confirmed_at(value):
        value = value.strip()
        if not value:
            return None
        try:
            confirmed_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            for pattern in ("%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d"):
                try:
                    confirmed_at = datetime.strptime(value, pattern)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError(
                    f"data de confirmação inválida: {value!r}. Use DD/MM/AAAA ou ISO."
                )
        return confirmed_at.isoformat(timespec="seconds")

    @staticmethod
    def parse_date(value):
        value = value.strip()
        for pattern in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(value, pattern).date().isoformat()
            except ValueError:
                continue
        raise ValueError(f"data inválida: {value!r}")

    @staticmethod
    def parse_time(value):
        value = value.strip()
        for pattern in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(value, pattern).time().strftime("%H:%M:%S")
            except ValueError:
                continue
        raise ValueError(f"hora inválida: {value!r}")

    @classmethod
    def parse_time_range(cls, value):
        value = value.strip()
        if not value:
            return None, None
        range_match = re.fullmatch(
            r"\s*(\d{1,2})(?::(\d{2}))?\s*h?\s*[-–—]\s*"
            r"(\d{1,2})(?::(\d{2}))?\s*h?\s*",
            value,
            flags=re.IGNORECASE,
        )
        if range_match:
            start_hour, start_minute, end_hour, end_minute = range_match.groups()
            start = cls.parse_time(f"{int(start_hour):02d}:{start_minute or '00'}")
            end = cls.parse_time(f"{int(end_hour):02d}:{end_minute or '00'}")
            return start, end
        return cls.parse_time(value), None

    def mapped_rows(self):
        columns = {key: combo.currentData() for key, combo in self.mapping_boxes.items()}
        required_fields = ("name", "shift", "service_date", "service_time")
        if any(not columns[key] for key in required_fields):
            raise ValueError("Mapeie as colunas de funcionário, turno, data e horário.")
        if bool(columns["attendance_status"]) != bool(columns["attendance_confirmed_at"]):
            raise ValueError(
                "Mapeie as colunas de resultado e confirmação do plantão juntas."
            )
        mapped_columns = [header for header in columns.values() if header]
        if len(set(mapped_columns)) != len(mapped_columns):
            raise ValueError("Cada campo deve usar uma coluna diferente do CSV.")
        mapped = []
        for row_number, row in enumerate(self.rows, start=2):
            try:
                patient = (
                    (row.get(columns["patient"]) or "").strip()
                    if columns["patient"]
                    else None
                )
                employee_name = (row.get(columns["name"]) or "").strip()
                if self.normalize(employee_name) in {
                    "semescalado",
                    "naoescalado",
                    "semfuncionario",
                    "naoalocado",
                }:
                    employee_name = ""
                service_time, service_end_time = self.parse_time_range(
                    row.get(columns["service_time"]) or ""
                )
                end_time_value = (
                    (row.get(columns["service_end_time"]) or "").strip()
                    if columns["service_end_time"]
                    else ""
                )
                if end_time_value:
                    service_end_time = self.parse_time(end_time_value)
                attendance_status = (
                    self.parse_attendance_status(row.get(columns["attendance_status"]) or "")
                    if columns["attendance_status"]
                    else None
                )
                attendance_confirmed_at = (
                    self.parse_attendance_confirmed_at(
                        row.get(columns["attendance_confirmed_at"]) or ""
                    )
                    if columns["attendance_confirmed_at"]
                    else None
                )
                if (attendance_status is None) != (attendance_confirmed_at is None):
                    raise ValueError(
                        "informe o resultado e a data de confirmação juntos"
                    )
                employee = {
                    "name": employee_name or None,
                    "patient": patient or None,
                    "shift": (row.get(columns["shift"]) or "").strip(),
                    "service_date": self.parse_date(row.get(columns["service_date"]) or ""),
                    "service_time": service_time,
                    "service_end_time": service_end_time,
                    "available": self.parse_availability(row.get(columns["available"]) or ""),
                }
                if columns["employee_code"]:
                    employee["employee_code"] = (
                        row.get(columns["employee_code"]) or ""
                    ).strip() or None
                if columns["attendance_status"]:
                    employee["attendance_status"] = attendance_status
                    employee["attendance_confirmed_at"] = attendance_confirmed_at
                if not employee["shift"]:
                    raise ValueError("turno é obrigatório")
                if employee["name"] and employee["service_time"] is None:
                    raise ValueError("informe o horário para funcionário escalado")
                if (
                    (employee.get("employee_code") and len(employee["employee_code"]) > 80)
                    or (employee["name"] and len(employee["name"]) > 120)
                    or len(employee["shift"]) > 80
                    or (employee["patient"] and len(employee["patient"]) > 120)
                ):
                    raise ValueError("nome e paciente devem ter até 120 caracteres e turno até 80")
                mapped.append(employee)
            except ValueError as exc:
                raise ValueError(f"Linha {row_number}: {exc}") from exc
        return mapped

    def update_preview(self):
        try:
            mapped = self.mapped_rows()
        except ValueError as exc:
            self.import_button.setEnabled(False)
            self.summary.setText(str(exc))
            self.preview.setRowCount(0)
            return
        self.import_button.setEnabled(True)
        self.summary.setText(f"{len(mapped)} linha(s) válida(s).")
        preview_rows = mapped[:8]
        self.preview.setRowCount(len(preview_rows))
        for row_index, employee in enumerate(preview_rows):
            for column, (key, _) in enumerate(FIELDS):
                value = employee.get(key)
                if key == "attendance_status":
                    value = PLANTAO_STATUS_LABELS.get(value, "")
                elif key == "attendance_confirmed_at" and value:
                    value = value.replace("T", " ")
                elif key == "available":
                    value = (
                        "Sim" if value is True
                        else "Não" if value is False
                        else ""
                    )
                self.preview.setItem(
                    row_index, column, QTableWidgetItem("" if value is None else str(value))
                )
        
            
    def import_file(self):
        try:
            employees = self.mapped_rows()
            result = self.api.import_employees(employees)
        except (ApiError, ValueError) as exc:
            QMessageBox.critical(self, "Importação não concluída", str(exc))
            return
        self.result_message = (
            f"Importação concluída: {result['created']} registro(s) criado(s) e "
            f"{result['updated']} atualizado(s)."
        )
        self.accept()
