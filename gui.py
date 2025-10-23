import sys
from time import sleep as wait
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QStackedWidget,
    QVBoxLayout,
    QGridLayout,
    QPushButton,
    QCheckBox,
    QLabel,
    QMessageBox,
    QSlider,
)

from PyQt5.QtCore import QTimer, Qt, pyqtSignal as signal

# Main Window
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Create stacked widget to switch between screens
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        # Create pages
        self.main_menu = MainMenu()
        self.custom_page = CustomDrinkPage()
        self.making_page = MakingDrinkPage()

        # Add them to the stack
        self.stack.addWidget(self.main_menu)
        self.stack.addWidget(self.custom_page)
        self.stack.addWidget(self.making_page)

        # Connect signals
        self.main_menu.drinkSelected.connect(self.start_making_drink)
        self.main_menu.customSelected.connect(self.show_custom_page)
        self.custom_page.submitSelected.connect(self.start_making_drink)

    def show_main_menu(self):
        self.stack.setCurrentWidget(self.main_menu)

    def show_custom_page(self):
        self.stack.setCurrentWidget(self.custom_page)

    def start_making_drink(self, drink_info=None):
        """Switch to making page and start a 10-second timer."""
        self.stack.setCurrentWidget(self.making_page)
        self.making_page.start_timer(callback=self.show_main_menu)

# Main Menu Page
class MainMenu(QWidget):
    drinkSelected = signal(str)
    customSelected = signal()

    def __init__(self):
        super().__init__()
        layout = QGridLayout()
        for i in range(9):
            btn = QPushButton(f"Drink {i+1}")
            btn.clicked.connect(lambda: self.drinkSelected.emit(f"Drink {i+1}"))
            layout.addWidget(btn, i//3, i%3)

        custom_btn = QPushButton("Make Your Own Drink")
        custom_btn.clicked.connect(self.customSelected.emit)
        layout.addWidget(custom_btn, 3, 1)

        self.setLayout(layout)

# Custom Drink Page
class CustomDrinkPage(QWidget):
    submitSelected = signal(list)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.drink_buttons = []
        self.drink_sliders = []

        # create 8 selectable options
        for i in range(8):
            row = QVBoxLayout()
            btn = QCheckBox(f"Option {i+1}")
    
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 300)
            slider.setMinimum(0)
            slider.setValue(0)
            slider.setMaximum(300)
            slider.setTickInterval(50)
            slider.setTickPosition(QSlider.TicksBelow)

            sliderLabel = QLabel("Amount: 0 ml")
            slider.valueChanged.connect(lambda value, label=sliderLabel: label.setText(f"Amount: {value} ml"))

            row.addWidget(btn)
            row.addWidget(slider)
            row.addWidget(sliderLabel)

            self.drink_buttons.append(btn)
            self.drink_sliders.append(slider)
            layout.addLayout(row)

        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self.handle_submit)
        layout.addWidget(submit_btn)

        self.setLayout(layout)

    def handle_submit(self):
        selected = [b.text() for b in self.drink_buttons if b.isChecked()]
        totalAmount = sum(slider.value() for i, slider in enumerate(self.drink_sliders) if self.drink_buttons[i].isChecked())
        if len(selected) > 3:
            QMessageBox.warning(self, "Selection Error", "Please select at most 3 drinks")
            #self.label = QLabel("Please select at most 3 drinks")
        elif totalAmount > 300:
            QMessageBox.warning(self, "Amount Error", "Please select a total amount of 300 ml or less")
            #self.label = QLabel("Please select a total amount of 300 ml or less")
        else:
            self.submitSelected.emit(selected)

class MakingDrinkPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.label = QLabel("Making Drink...")
        layout.addWidget(self.label)
        self.setLayout(layout)

    def start_timer(self, callback):
        """Start 10-second timer then call callback."""
        QTimer.singleShot(10000, callback)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle("Arthur")
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()