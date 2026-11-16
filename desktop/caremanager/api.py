import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ApiError(Exception):
    pass


class CareManagerApi:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._employee_list_cache = {}

    def _invalidate_employee_list_cache(self):
        self._employee_list_cache.clear()

    def request(self, method: str, path: str, payload=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=15) as response:
                content = response.read()
        except HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8"))
                detail = body.get("detail", str(exc))
            except (UnicodeDecodeError, json.JSONDecodeError):
                detail = str(exc)
            raise ApiError(f"Erro da API ({exc.code}): {detail}") from exc
        except (URLError, TimeoutError) as exc:
            raise ApiError(f"Não foi possível conectar ao servidor: {exc}") from exc
        if not content:
            return None
        try:
            return json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError("O servidor retornou uma resposta inválida.") from exc

    def check_connection(self):
        response = self.request("GET", "/api/employees?limit=1")
        if not isinstance(response, list):
            raise ApiError("O servidor retornou uma resposta de conexão inválida.")

    def list_employees(
        self,
        name="",
        patient="",
        shift="",
        available=None,
        service_date_from=None,
        service_date_to=None,
        service_time_from=None,
        service_time_to=None,
    ):
        filters = {}
        if name.strip():
            filters["name"] = name.strip()
        if patient.strip():
            filters["patient"] = patient.strip()
        if shift:
            filters["shift"] = shift
        if available is not None:
            filters["available"] = (
                available if isinstance(available, str) else str(available).lower()
            )
        if service_date_from:
            filters["service_date_from"] = service_date_from
        if service_date_to:
            filters["service_date_to"] = service_date_to
        if service_time_from:
            filters["service_time_from"] = service_time_from
        if service_time_to:
            filters["service_time_to"] = service_time_to

        cache_key = tuple(sorted(filters.items(), key=lambda item: item[0]))
        if cache_key in self._employee_list_cache:
            return self._employee_list_cache[cache_key]

        records = []
        offset = 0
        while True:
            query = urlencode({**filters, "limit": 500, "offset": offset})
            page = self.request("GET", f"/api/employees?{query}")
            if not isinstance(page, list):
                raise ApiError("O servidor retornou uma lista de funcionários inválida.")
            records.extend(page)
            if len(page) < 500:
                self._employee_list_cache[cache_key] = records
                return records
            offset += 500

    def create_employee(self, employee):
        result = self.request("POST", "/api/employees", employee)
        self._invalidate_employee_list_cache()
        return result

    def update_employee(self, employee_id, employee):
        result = self.request("PUT", f"/api/employees/{employee_id}", employee)
        self._invalidate_employee_list_cache()
        return result

    def update_employee_attendance(self, employee_id, attendance_status):
        result = self.request(
            "PATCH",
            f"/api/employees/{employee_id}/attendance",
            {"attendance_status": attendance_status},
        )
        self._invalidate_employee_list_cache()
        if not isinstance(result, dict) or result.get("id") != employee_id:
            raise ApiError("O servidor retornou um resultado de plantão inválido.")
        return result

    def delete_employee(self, employee_id):
        self.request("DELETE", f"/api/employees/{employee_id}")
        self._invalidate_employee_list_cache()

    def delete_assigned_employees(self):
        result = self.request("DELETE", "/api/employees/assigned")
        self._invalidate_employee_list_cache()
        if not isinstance(result, dict) or not isinstance(result.get("deleted"), int):
            raise ApiError("O servidor retornou um resultado inválido ao limpar funcionários.")
        return result["deleted"]

    def import_employees(self, employees):
        result = self.request("POST", "/api/employees/import", employees)
        self._invalidate_employee_list_cache()
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("created"), int)
            or not isinstance(result.get("updated"), int)
        ):
            raise ApiError("O servidor retornou um resultado de importação inválido.")
        return result
