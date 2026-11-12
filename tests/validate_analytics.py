import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "desktop"))

from caremanager.analytics import AnalyticsDialog


def main():
    data = [
        {"name": "Ana", "shift": "Manhã", "service_date": "2024-01-01", "available": True},
        {"name": "Bia", "shift": "Tarde", "service_date": "2024-01-01", "available": False},
        {"name": "Carlos", "shift": "Manhã", "service_date": "2024-01-02", "available": True},
        {"name": "Duda", "shift": "Noite", "service_date": "2024-01-03", "available": None},
    ]
    prepared = AnalyticsDialog.prepare_data(data)
    counts = AnalyticsDialog.make_daily_counts_from_data(prepared)
    forecast = AnalyticsDialog.predict_next_day_from_counts(counts)
    print(f"rows={prepared.shape[0]}")
    print(f"counts={counts.shape}")
    print(f"forecast={forecast is not None}")


if __name__ == "__main__":
    main()
