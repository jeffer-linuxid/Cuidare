import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "desktop"))

from caremanager.api import CareManagerApi


class CareManagerApiCacheTests(unittest.TestCase):
    def test_list_employees_uses_cache_for_identical_filters(self):
        api = CareManagerApi("http://example.com", "secret")
        calls = []

        def fake_request(method, path, payload=None):
            calls.append((method, path, payload))
            return [{
                "id": 1,
                "name": "Ana",
                "employee_code": "E-01",
                "patient": "Paciente A",
                "shift": "Noite",
                "service_date": "2024-01-05",
                "service_time": "08:00:00",
                "service_end_time": "16:00:00",
                "available": True,
                "attendance_status": None,
                "attendance_confirmed_at": None,
            }]

        api.request = fake_request

        first = api.list_employees(name="Ana")
        second = api.list_employees(name="Ana")

        self.assertEqual(len(first), 1)
        self.assertEqual(second, first)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
