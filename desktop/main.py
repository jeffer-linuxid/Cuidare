import sys

from PySide6.QtWidgets import QApplication

from caremanager.main_window import APP_STYLESHEET, ConnectionDialog, MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CareManager")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    connection = ConnectionDialog()
    if connection.exec() != ConnectionDialog.DialogCode.Accepted:
        return 0
    window = MainWindow(connection.api)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
