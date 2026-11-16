from datetime import date, datetime, timedelta

try:
    import numpy as np
    import pandas as pd
    from matplotlib import dates as mdates
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
except ImportError as exc:  # pragma: no cover - fallback when optional deps are blocked
    np = None
    pd = None
    mdates = None
    FigureCanvasQTAgg = None
    Figure = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QDialog,
        QFrame,
        QGridLayout,
        QHeaderView,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QScrollArea,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    class QDialog:  # pragma: no cover - used only when GUI deps are unavailable
        def __init__(self, *args, **kwargs):
            pass

    class QFrame:
        Shape = type("Shape", (), {"NoFrame": 0})

        def __init__(self, *args, **kwargs):
            pass

    class QAbstractItemView:
        SelectionMode = type("SelectionMode", (), {"NoSelection": 0})
        EditTrigger = type("EditTrigger", (), {"NoEditTriggers": 0})

    class QHeaderView:
        ResizeMode = type("ResizeMode", (), {"Stretch": 0})

    class QTableWidget:
        def __init__(self, *args, **kwargs):
            pass

    class QTableWidgetItem:
        def __init__(self, *args, **kwargs):
            pass

    class Qt:
        AlignmentFlag = type("AlignmentFlag", (), {"AlignTop": 0})

    QGridLayout = QHBoxLayout = QVBoxLayout = QTabWidget = QWidget = QLabel = QPushButton = QScrollArea = None
    QHeaderView = QHeaderView
    _IMPORT_ERROR = _IMPORT_ERROR or ImportError("PySide6 não pôde ser carregado")


STATUS_LABELS = ("Disponível", "Indisponível", "Sem informação")
STATUS_COLORS = {
    "Disponível": "#19836f",
    "Indisponível": "#d27a64",
    "Sem informação": "#aab9b5",
}
ABSENCE_FEATURES = ("employee", "shift", "weekday", "month", "start_hour")
MINIMUM_TRAINING_RECORDS = 50
MINIMUM_RECORDS_PER_CLASS = 5


def require_analytics_dependencies():
    if np is None or pd is None:
        raise ImportError(
            "As dependências de análise não puderam ser carregadas: "
            f"{_IMPORT_ERROR}"
        )


class AnalyticsDialog(QDialog):
    def __init__(self, records, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Análises da equipe")
        self.resize(1080, 900)
        self.setMinimumSize(760, 560)

        self.records = records
        self.data = self.prepare_data(records)
        self.daily_counts = self.make_daily_counts()
        self.forecast_error = None
        try:
            self.forecast = self.predict_next_day()
        except ImportError as exc:
            self.forecast = None
            self.forecast_error = str(exc)
        self.absence_model_error = None
        try:
            self.absence_model = self.train_absence_model(records)
        except ImportError as exc:
            self.absence_model = None
            self.absence_model_error = str(exc)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        root_layout.addWidget(scroll_area)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        heading = QHBoxLayout()
        heading_copy = QVBoxLayout()
        title = QLabel("Análises da equipe")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Resumo dos registros de disponibilidade e dos turnos cadastrados."
        )
        subtitle.setStyleSheet("color: #69817d;")
        heading_copy.addWidget(title)
        heading_copy.addWidget(subtitle)
        heading.addLayout(heading_copy)
        heading.addStretch()
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        heading.addWidget(close_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(heading)

        metrics = self.make_metrics()
        cards = QGridLayout()
        cards.setSpacing(12)
        for column, (caption, value) in enumerate(metrics):
            cards.addWidget(self.stat_card(caption, value), 0, column)
        layout.addLayout(cards)

        chart_row = QHBoxLayout()
        chart_row.setSpacing(14)
        daily_card = self.chart_card("Disponibilidade por data")
        daily_layout = daily_card.layout()
        self.daily_canvas = FigureCanvasQTAgg(Figure(figsize=(6.3, 3.7), dpi=100))
        daily_layout.addWidget(self.daily_canvas)
        self.draw_daily_chart()

        distribution_card = self.chart_card("Distribuição")
        distribution_layout = distribution_card.layout()
        self.distribution_tabs = QTabWidget()
        availability_page = QWidget()
        availability_layout = QVBoxLayout(availability_page)
        availability_layout.setContentsMargins(0, 0, 0, 0)
        self.availability_canvas = FigureCanvasQTAgg(Figure(figsize=(6.3, 3.7), dpi=100))
        availability_layout.addWidget(self.availability_canvas)
        self.draw_availability_chart()

        shifts_page = QWidget()
        shifts_layout = QVBoxLayout(shifts_page)
        shifts_layout.setContentsMargins(0, 0, 0, 0)
        self.shift_canvas = FigureCanvasQTAgg(Figure(figsize=(6.3, 3.7), dpi=100))
        shifts_layout.addWidget(self.shift_canvas)
        self.draw_shift_chart()
        self.distribution_tabs.addTab(availability_page, "Disponibilidade")
        self.distribution_tabs.addTab(shifts_page, "Turnos")
        distribution_layout.addWidget(self.distribution_tabs)
        chart_row.addWidget(daily_card, 1)
        chart_row.addWidget(distribution_card, 1)
        layout.addLayout(chart_row, 1)

        model_card = self.chart_card("Previsão de faltas com machine learning")
        model_layout = model_card.layout()
        self.model_summary = QLabel(self.absence_model_note())
        self.model_summary.setWordWrap(True)
        self.model_summary.setStyleSheet("color: #69817d;")
        model_layout.addWidget(self.model_summary)
        absence_chart_title = QLabel("Chance média de falta por plantão · por dia")
        absence_chart_title.setObjectName("sectionTitle")
        model_layout.addWidget(absence_chart_title)
        absence_chart_note = QLabel(
            "Média das probabilidades individuais dos plantões futuros em cada data."
        )
        absence_chart_note.setWordWrap(True)
        absence_chart_note.setStyleSheet("color: #69817d;")
        model_layout.addWidget(absence_chart_note)
        self.absence_daily_canvas = FigureCanvasQTAgg(
            Figure(figsize=(9.4, 3.2), dpi=100)
        )
        self.absence_daily_canvas.setMinimumHeight(230)
        model_layout.addWidget(self.absence_daily_canvas)
        self.draw_absence_daily_chart()
        self.absence_table = QTableWidget(0, 5)
        self.absence_table.setHorizontalHeaderLabels(
            ["Data", "Horário", "Funcionário", "Turno", "Risco estimado"]
        )
        self.absence_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.absence_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.absence_table.verticalHeader().setVisible(False)
        self.absence_table.verticalHeader().setDefaultSectionSize(34)
        self.absence_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.absence_table.setShowGrid(False)
        self.absence_table.setMaximumHeight(240)
        model_layout.addWidget(self.absence_table)
        self.populate_absence_table()
        layout.addWidget(model_card)

        note = QLabel(self.forecast_note())
        note.setWordWrap(True)
        note.setStyleSheet(
            "color: #69817d; background: #eaf3f0; border-radius: 8px; padding: 10px;"
        )
        layout.addWidget(note)
        scroll_area.setWidget(content)

    @staticmethod
    def prepare_data(records):
        if pd is None:
            prepared = []
            for record in records:
                service_date_value = record.get("service_date")
                service_date = None
                if isinstance(service_date_value, str):
                    try:
                        service_date = date.fromisoformat(service_date_value)
                    except ValueError:
                        try:
                            service_date = datetime.strptime(service_date_value, "%d/%m/%Y").date()
                        except ValueError:
                            service_date = None
                elif service_date_value is not None:
                    service_date = service_date_value
                prepared.append(
                    {
                        "name": str(record.get("name") or "").strip(),
                        "shift": str(record.get("shift") or "").strip() or "Não informado",
                        "service_date": service_date,
                        "available": record.get("available"),
                        "status": (
                            "Sem informação"
                            if record.get("available") is None or record.get("available") == ""
                            else ("Disponível" if bool(record.get("available")) else "Indisponível")
                        ),
                    }
                )
            return prepared

        data = pd.DataFrame.from_records(
            records,
            columns=("name", "shift", "service_date", "available"),
        )
        data["name"] = data["name"].fillna("").astype(str).str.strip()
        data["shift"] = (
            data["shift"].fillna("").astype(str).str.strip().replace("", "Não informado")
        )
        data["service_date"] = pd.to_datetime(data["service_date"], errors="coerce")

        def availability_label(value):
            if pd.isna(value):
                return "Sem informação"
            return "Disponível" if bool(value) else "Indisponível"

        data["status"] = data["available"].map(availability_label)
        return data

    @staticmethod
    def make_daily_counts_from_data(data):
        if pd is None:
            counts = {}
            for row in data:
                service_date = row.get("service_date")
                if service_date is None:
                    continue
                status = row.get("status") or (
                    "Sem informação"
                    if row.get("available") is None or row.get("available") == ""
                    else ("Disponível" if bool(row.get("available")) else "Indisponível")
                )
                counts.setdefault(service_date, {label: 0 for label in STATUS_LABELS})
                counts[service_date][status] = counts[service_date].get(status, 0) + 1
            ordered = []
            for day in sorted(counts):
                ordered.append((day, counts[day]))
            return ordered

        dated = data.dropna(subset=["service_date"])
        if dated.empty:
            return pd.DataFrame(columns=STATUS_LABELS, dtype=int)
        daily = dated.groupby(["service_date", "status"]).size().unstack(fill_value=0)
        return daily.reindex(columns=STATUS_LABELS, fill_value=0).sort_index()

    @staticmethod
    def predict_next_day_from_counts(counts):
        if pd is None:
            if not counts:
                return None
            ordered = sorted(counts, key=lambda item: item[0])
            if len(ordered) < 3:
                return None
            x = [day.toordinal() for day, _ in ordered]
            y = [values.get("Disponível", 0) for _, values in ordered]
            mean_x = sum(x) / len(x)
            mean_y = sum(y) / len(y)
            numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
            denominator = sum((xi - mean_x) ** 2 for xi in x)
            slope = 0.0 if denominator == 0 else numerator / denominator
            intercept = mean_y - slope * mean_x
            next_day = date.fromordinal(int(x[-1]) + 1)
            estimate = max(0.0, slope * next_day.toordinal() + intercept)
            return next_day, float(estimate)

        if len(counts.index) < 3:
            return None

        x_values = [
            timestamp.to_pydatetime().date().toordinal() for timestamp in counts.index
        ]
        y_values = counts["Disponível"].to_numpy(dtype=float).tolist()
        mean_x = sum(x_values) / len(x_values)
        mean_y = sum(y_values) / len(y_values)
        numerator = sum(
            (x_value - mean_x) * (y_value - mean_y)
            for x_value, y_value in zip(x_values, y_values)
        )
        denominator = sum((x_value - mean_x) ** 2 for x_value in x_values)
        slope = 0.0 if denominator == 0 else numerator / denominator
        intercept = mean_y - slope * mean_x
        next_day = int(x_values[-1]) + 1
        estimate = max(0.0, slope * next_day + intercept)
        return counts.index[-1] + pd.Timedelta(days=1), float(estimate)

    def make_daily_counts(self):
        return self.make_daily_counts_from_data(self.data)

    def predict_next_day(self):
        return self.predict_next_day_from_counts(self.daily_counts)

    @staticmethod
    def employee_identity(record):
        employee_code = (record.get("employee_code") or "").strip().casefold()
        if employee_code:
            return employee_code
        return (record.get("name") or "").strip().casefold()

    @classmethod
    def absence_features(cls, record):
        service_date = pd.Timestamp(record["service_date"]).date()
        service_time = record.get("service_time") or ""
        return {
            "employee": cls.employee_identity(record) or "unknown",
            "shift": (record.get("shift") or "").strip() or "unknown",
            "weekday": str(service_date.weekday()),
            "month": str(service_date.month),
            "start_hour": service_time[:2] if service_time else "unknown",
        }

    @staticmethod
    def make_absence_pipeline():
        from sklearn.compose import ColumnTransformer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder

        encoder = ColumnTransformer(
            [
                (
                    "categories",
                    OneHotEncoder(handle_unknown="ignore"),
                    list(ABSENCE_FEATURES),
                )
            ]
        )
        return Pipeline(
            [
                ("features", encoder),
                ("classifier", LogisticRegression(max_iter=1000, random_state=42)),
            ]
        )

    @classmethod
    def train_absence_model(cls, records):
        try:
            from sklearn.metrics import balanced_accuracy_score
        except Exception:
            balanced_accuracy_score = None

        today = pd.Timestamp.today().date() if pd is not None else date.today()

        def _service_date_value(record):
            value = record.get("service_date")
            if pd is not None:
                return pd.Timestamp(value).date()
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value).date()
                except ValueError:
                    try:
                        return datetime.strptime(value, "%d/%m/%Y").date()
                    except ValueError:
                        return None
            return value

        historical = [
            record
            for record in records
            if record.get("attendance_status") in {"present", "absent"}
            and record.get("attendance_confirmed_at")
            and record.get("name")
            and _service_date_value(record) is not None
            and _service_date_value(record) < today
        ]
        historical.sort(key=lambda record: record["service_date"])
        targets = np.array(
            [int(record["attendance_status"] == "absent") for record in historical],
            dtype=int,
        )
        absent_count = int(np.count_nonzero(targets == 1))
        present_count = int(np.count_nonzero(targets == 0))
        result = {
            "model": None,
            "historical_count": len(historical),
            "absent_count": absent_count,
            "present_count": present_count,
            "future_records": [],
            "balanced_accuracy": None,
            "ready": False,
        }
        if (
            len(historical) < MINIMUM_TRAINING_RECORDS
            or absent_count < MINIMUM_RECORDS_PER_CLASS
            or present_count < MINIMUM_RECORDS_PER_CLASS
        ):
            return result

        future_records = [
            record
            for record in records
            if record.get("name")
            and record.get("attendance_status") is None
            and _service_date_value(record) is not None
            and _service_date_value(record) >= today
        ]

        if balanced_accuracy_score is None:
            rate_absent = absent_count / len(historical)
            result["future_records"] = sorted(
                (
                    (record, float(rate_absent))
                    for record in future_records
                ),
                key=lambda prediction: prediction[1],
                reverse=True,
            )
            result["ready"] = bool(future_records)
            return result

        frame = pd.DataFrame(
            [cls.absence_features(record) for record in historical],
            columns=ABSENCE_FEATURES,
        )
        split_at = int(len(historical) * 0.8)
        training_targets = targets[:split_at]
        validation_targets = targets[split_at:]
        if (
            split_at >= MINIMUM_TRAINING_RECORDS
            and np.count_nonzero(training_targets == 1) >= MINIMUM_RECORDS_PER_CLASS
            and np.count_nonzero(training_targets == 0) >= MINIMUM_RECORDS_PER_CLASS
            and len(np.unique(validation_targets)) == 2
        ):
            validation_model = cls.make_absence_pipeline()
            validation_model.fit(frame.iloc[:split_at], training_targets)
            predictions = validation_model.predict(frame.iloc[split_at:])
            result["balanced_accuracy"] = float(
                balanced_accuracy_score(validation_targets, predictions)
            )

        model = cls.make_absence_pipeline()
        model.fit(frame, targets)
        if future_records:
            future_frame = pd.DataFrame(
                [cls.absence_features(record) for record in future_records],
                columns=ABSENCE_FEATURES,
            )
            risks = model.predict_proba(future_frame)[:, 1]
            result["future_records"] = sorted(
                (
                    (record, float(risk))
                    for record, risk in zip(future_records, risks)
                ),
                key=lambda prediction: prediction[1],
                reverse=True,
            )
        result["model"] = model
        result["ready"] = True
        return result
    def absence_model_note(self):
        if self.absence_model_error:
            return (
                "A previsão de faltas está indisponível porque o scikit-learn não pôde ser "
                f"carregado ({self.absence_model_error})."
            )
        if self.absence_model is None:
            return "A previsão de faltas não está disponível."
        sample_count = self.absence_model["historical_count"]
        absent_count = self.absence_model["absent_count"]
        present_count = self.absence_model["present_count"]
        minimum = MINIMUM_TRAINING_RECORDS
        class_minimum = MINIMUM_RECORDS_PER_CLASS
        if not self.absence_model["ready"]:
            return (
                f"Histórico insuficiente para treinar: {sample_count}/{minimum} resultados "
                f"anteriores confirmados ({absent_count} faltas e {present_count} realizados). "
                f"São necessários pelo menos {minimum} resultados, incluindo "
                f"{class_minimum} de cada tipo. Cancelamentos, substituições e plantões "
                "pendentes não são usados como faltas."
            )
        accuracy = self.absence_model["balanced_accuracy"]
        validation_note = (
            f" Acurácia balanceada em validação temporal: {accuracy:.0%}."
            if accuracy is not None
            else " Validação temporal indisponível para esta distribuição de resultados."
        )
        return (
            f"Modelo treinado com {sample_count} resultados confirmados "
            f"({absent_count} faltas e {present_count} realizados). "
            f"Exibindo os {min(10, len(self.absence_model['future_records']))} maiores riscos "
            f"entre {len(self.absence_model['future_records'])} plantões futuros."
            f"{validation_note} Estimativa experimental, não é garantia."
        )

    def populate_absence_table(self):
        if not self.absence_model or not self.absence_model["ready"]:
            return
        predictions = self.absence_model["future_records"][:10]
        self.absence_table.setRowCount(len(predictions))
        for row, (record, risk) in enumerate(predictions):
            service_date = pd.Timestamp(record["service_date"]).strftime("%d/%m/%Y")
            service_time = record.get("service_time") or ""
            values = (
                service_date,
                service_time[:5] or "—",
                record["name"],
                record.get("shift") or "—",
                f"{risk:.0%}",
            )
            for column, value in enumerate(values):
                self.absence_table.setItem(row, column, QTableWidgetItem(value))

    def absence_daily_estimates(self):
        if not self.absence_model or not self.absence_model["ready"]:
            return []
        grouped = {}
        for record, risk in self.absence_model["future_records"]:
            service_date = pd.Timestamp(record["service_date"]).date()
            grouped.setdefault(service_date, []).append(risk)
        return [
            (service_date, float(np.mean(risks)), len(risks))
            for service_date, risks in sorted(grouped.items())
        ]

    def draw_absence_daily_chart(self):
        figure = self.absence_daily_canvas.figure
        axes = figure.add_subplot(111)
        figure.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.24)
        estimates = self.absence_daily_estimates()
        if not estimates:
            if self.absence_model and self.absence_model["ready"]:
                message = "Não há plantões futuros para estimar"
            else:
                message = "Histórico insuficiente para calcular as probabilidades"
            axes.text(
                0.5,
                0.5,
                message,
                ha="center",
                va="center",
                transform=axes.transAxes,
                color="#69817d",
                wrap=True,
            )
            axes.set_axis_off()
            self.absence_daily_canvas.draw()
            return

        dates = [pd.Timestamp(service_date).to_pydatetime() for service_date, _, _ in estimates]
        risks = [risk * 100 for _, risk, _ in estimates]
        bars = axes.bar(dates, risks, color="#d27a64", width=0.72)
        axes.set_ylim(0, 100)
        axes.set_ylabel("Chance média por plantão (%)", color="#69817d")
        axes.grid(axis="y", color="#e8efed", linewidth=0.8)
        axes.set_axisbelow(True)
        axes.spines[["top", "right", "left"]].set_visible(False)
        axes.spines["bottom"].set_color("#dce8e5")
        axes.tick_params(axis="both", colors="#69817d", labelsize=8)
        axes.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=8))
        axes.xaxis.set_major_formatter(
            mdates.ConciseDateFormatter(axes.xaxis.get_major_locator())
        )
        for bar, (_, risk, count) in zip(bars, estimates):
            axes.annotate(
                f"{risk:.0%} · {count} plantão(s)",
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color="#45635e",
            )
        self.absence_daily_canvas.draw()

    def make_metrics(self):
        status_counts = self.data["status"].value_counts()
        known_status = int(
            np.count_nonzero(self.data["status"].to_numpy() != "Sem informação")
        )
        availability_rate = (
            f"{100 * int(status_counts.get('Disponível', 0)) / known_status:.0f}%"
            if known_status
            else "—"
        )
        forecast_value = f"{self.forecast[1]:.1f}" if self.forecast else "—"
        named_employees = self.data.loc[self.data["name"].ne(""), "name"]
        metrics = [
            ("REGISTROS", f"{len(self.data):,}".replace(",", ".")),
            ("PROFISSIONAIS CADASTRADOS", f"{named_employees.nunique():,}".replace(",", ".")),
            ("DISPONIBILIDADE INFORMADA", availability_rate),
            ("FUROS DE PLANTÃO", f"{self.data['name'].eq('').sum():,}".replace(",", ".")),
            ("REGISTROS DISPONÍVEIS · ESTIMATIVA", forecast_value),
        ]
        return metrics

    @staticmethod
    def stat_card(caption, value):
        card = QFrame()
        card.setObjectName("statCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(15, 13, 15, 14)
        card_layout.setSpacing(7)
        number = QLabel(value)
        number.setObjectName("statValue")
        label = QLabel(caption)
        label.setObjectName("statCaption")
        label.setWordWrap(True)
        card_layout.addWidget(number)
        card_layout.addWidget(label)
        return card

    @staticmethod
    def chart_card(title):
        card = QFrame()
        card.setObjectName("surface")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        card_layout.addWidget(title_label)
        return card

    def draw_daily_chart(self):
        figure = self.daily_canvas.figure
        axes = figure.add_subplot(111)
        figure.subplots_adjust(left=0.11, right=0.98, top=0.92, bottom=0.22)
        if self.daily_counts.empty:
            axes.text(
                0.5, 0.5, "Sem registros com data para exibir",
                ha="center", va="center", transform=axes.transAxes, color="#69817d",
            )
            axes.set_axis_off()
            self.daily_canvas.draw()
            return

        dates = self.daily_counts.index.to_pydatetime()
        bottoms = np.zeros(len(dates), dtype=float)
        for label in STATUS_LABELS:
            values = self.daily_counts[label].to_numpy(dtype=int)
            axes.bar(
                dates,
                values,
                bottom=bottoms,
                color=STATUS_COLORS[label],
                label=label,
                width=0.72,
            )
            bottoms += values

        if self.forecast:
            forecast_date, estimate = self.forecast
            axes.scatter(
                [forecast_date.to_pydatetime()],
                [estimate],
                color="#174b43",
                marker="D",
                s=48,
                label="Estimativa linear",
                zorder=3,
            )
        axes.set_ylabel("Quantidade de registros", color="#69817d")
        axes.grid(axis="y", color="#e8efed", linewidth=0.8)
        axes.set_axisbelow(True)
        axes.spines[["top", "right", "left"]].set_visible(False)
        axes.spines["bottom"].set_color("#dce8e5")
        axes.tick_params(axis="both", colors="#69817d", labelsize=8)
        axes.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=7))
        axes.xaxis.set_major_formatter(mdates.ConciseDateFormatter(axes.xaxis.get_major_locator()))
        axes.legend(frameon=False, fontsize=8, loc="upper left")
        self.daily_canvas.draw()

    def draw_availability_chart(self):
        figure = self.availability_canvas.figure
        axes = figure.add_subplot(111)
        figure.subplots_adjust(left=0.04, right=0.96, top=0.94, bottom=0.06)
        counts = self.data["status"].value_counts().reindex(STATUS_LABELS, fill_value=0)
        counts = counts[counts > 0]
        if counts.empty:
            axes.text(
                0.5, 0.5, "Sem registros para exibir",
                ha="center", va="center", transform=axes.transAxes, color="#69817d",
            )
            axes.set_axis_off()
            self.availability_canvas.draw()
            return

        total = int(counts.sum())
        axes.pie(
            counts.to_numpy(),
            labels=counts.index,
            colors=[STATUS_COLORS[label] for label in counts.index],
            autopct=lambda percentage: (
                f"{percentage:.0f}%\n({round(percentage * total / 100)})"
            ),
            startangle=90,
            counterclock=False,
            wedgeprops={"edgecolor": "#ffffff", "linewidth": 2},
            textprops={"color": "#274541", "fontsize": 9},
        )
        axes.axis("equal")
        self.availability_canvas.draw()

    def draw_shift_chart(self):
        figure = self.shift_canvas.figure
        axes = figure.add_subplot(111)
        figure.subplots_adjust(left=0.2, right=0.98, top=0.92, bottom=0.15)
        if self.data.empty:
            axes.text(
                0.5, 0.5, "Sem registros para exibir",
                ha="center", va="center", transform=axes.transAxes, color="#69817d",
            )
            axes.set_axis_off()
            self.shift_canvas.draw()
            return

        shift_counts = self.data.groupby(["shift", "status"]).size().unstack(fill_value=0)
        shift_counts = shift_counts.reindex(columns=STATUS_LABELS, fill_value=0)
        shift_counts = shift_counts.sum(axis=1).sort_values(ascending=False).head(8)
        shift_counts = shift_counts.sort_values(ascending=True)
        counts_by_status = (
            self.data[self.data["shift"].isin(shift_counts.index)]
            .groupby(["shift", "status"])
            .size()
            .unstack(fill_value=0)
            .reindex(index=shift_counts.index, columns=STATUS_LABELS, fill_value=0)
        )

        positions = np.arange(len(counts_by_status.index))
        left = np.zeros(len(positions), dtype=float)
        for label in STATUS_LABELS:
            values = counts_by_status[label].to_numpy(dtype=int)
            axes.barh(
                positions,
                values,
                left=left,
                color=STATUS_COLORS[label],
                label=label,
            )
            left += values
        axes.set_yticks(positions, labels=counts_by_status.index)
        axes.set_xlabel("Quantidade de registros", color="#69817d")
        axes.grid(axis="x", color="#e8efed", linewidth=0.8)
        axes.set_axisbelow(True)
        axes.spines[["top", "right", "left"]].set_visible(False)
        axes.spines["bottom"].set_color("#dce8e5")
        axes.tick_params(axis="both", colors="#69817d", labelsize=8)
        axes.legend(frameon=False, fontsize=8, loc="lower right")
        self.shift_canvas.draw()

    def forecast_note(self):
        if self.forecast:
            date_label = self.forecast[0].strftime("%d/%m/%Y")
            return (
                f"Estimativa exploratória para {date_label}: "
                f"{self.forecast[1]:.1f} registros disponíveis. "
                "Calculada por regressão linear sobre as datas cadastradas; não substitui a escala."
            )
        if self.forecast_error:
            return (
                "A estimativa está indisponível porque o scikit-learn não pôde ser carregado "
                f"({self.forecast_error}). Os gráficos continuam disponíveis."
            )
        if self.data.empty:
            return "Cadastre ou importe registros para visualizar os indicadores e gráficos."
        return (
            "A estimativa linear será exibida quando houver registros em pelo menos "
            "três datas distintas."
        )
