import os
import logging
import secrets
import sys
import threading
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
import uvicorn


def main() -> int:
    data_directory = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Cuidare-Morumbi"
    data_directory.mkdir(parents=True, exist_ok=True)
    log_path = data_directory / "caremanager.log"
    logging.basicConfig(filename=log_path, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    database_path = (data_directory / "caremanager.sqlite3").as_posix()
    requested_port = os.environ.get("CAREMANAGER_LOCAL_PORT")
    port = int(requested_port) if requested_port else 0
    os.environ["CAREMANAGER_DATABASE_URL"] = f"sqlite:///{database_path}"
    os.environ["CAREMANAGER_API_KEY"] = secrets.token_urlsafe(32)
    os.environ["CAREMANAGER_API_URL"] = f"http://127.0.0.1:{port}"

    app = QApplication(sys.argv)
    app.setApplicationName("CareManager")
    app.setStyle("Fusion")

    from caremanager.main_window import APP_STYLESHEET, ConnectionDialog, MainWindow
    from app.main import app as api_app

    app.setStyleSheet(APP_STYLESHEET)
    config = uvicorn.Config(
        api_app,
        host="127.0.0.1",
        port=port,
        http="h11",
        log_config=None,
        log_level="error",
        access_log=False,
        loop="asyncio",
        ws="none",
    )
    server = uvicorn.Server(config)
    server_errors = []

    def run_server():
        try:
            server.run()
        except Exception as exc:
            server_errors.append(exc)
            logging.exception("Falha ao iniciar a API local")

    server_thread = threading.Thread(target=run_server, name="CareManager API", daemon=True)
    server_thread.start()
    deadline = time.monotonic() + 20
    while not server.started and server_thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.1)

    if not server.started:
        server.should_exit = True
        server_thread.join(timeout=5)
        detail = str(server_errors[0]) if server_errors else "Tempo limite de inicialização excedido."
        QMessageBox.critical(
            None,
            "Não foi possível iniciar o CareManager",
            f"A API local não iniciou na porta {port}.\n\n{detail}\n\nLog: {log_path}",
        )
        return 1

    port = server.servers[0].sockets[0].getsockname()[1]
    os.environ["CAREMANAGER_API_URL"] = f"http://127.0.0.1:{port}"

    try:
        connection = ConnectionDialog()
        if connection.exec() != ConnectionDialog.DialogCode.Accepted:
            return 0
        window = MainWindow(connection.api)
        window.show()
        return app.exec()
    except Exception:
        logging.exception("Falha ao iniciar a interface do CareManager")
        QMessageBox.critical(
            None,
            "Erro ao iniciar o CareManager",
            f"Não foi possível abrir o aplicativo.\n\nConsulte o log em:\n{log_path}",
        )
        return 1
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
