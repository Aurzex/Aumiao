import sys  # noqa: I001

from gui import MainWindow

from PyQt5.QtWidgets import QApplication

def main() -> None:
	app = QApplication(sys.argv)
	window = MainWindow()
	window.show()
	sys.exit(app.exec())

if __name__ == "__main__":
	main()
