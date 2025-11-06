from drinkSelect import drink, mixedDrink
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
    QLineEdit,
    QHBoxLayout,
)

from PyQt5.QtCore import QTimer, Qt, pyqtSignal as signal
from PyQt5.QtGui import QFont

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
        self.password_page = PasswordPage()
        self.admin_page = AdminPage()

        # Add them to the stack
        self.stack.addWidget(self.main_menu)
        self.stack.addWidget(self.custom_page)
        self.stack.addWidget(self.making_page)
        self.stack.addWidget(self.password_page)
        self.stack.addWidget(self.admin_page)

        # Connect signals
        self.main_menu.drinkSelected.connect(self.start_making_drink)
        self.main_menu.customSelected.connect(self.show_custom_page)
        self.main_menu.adminSelected.connect(self.show_password_page)
        self.custom_page.submitSelected.connect(self.start_making_drink)
        self.password_page.accessGranted.connect(self.show_admin_page)
        self.password_page.returnToMain.connect(self.show_main_menu)
        self.main_menu.updateDrinkButtons()

    def show_main_menu(self):
        self.stack.setCurrentWidget(self.main_menu)

    def show_custom_page(self):
        self.stack.setCurrentWidget(self.custom_page)

    def start_making_drink(self, drink_info=None):
        # Switch to making page and start a 10-second timer.
        self.stack.setCurrentWidget(self.making_page)
        self.making_page.start_timer(callback=self.show_main_menu)

    def show_admin_page(self):
        self.stack.setCurrentWidget(self.admin_page)
    
    def show_password_page(self):
        self.stack.setCurrentWidget(self.password_page)

# Main Menu Page
class MainMenu(QWidget):
    drinkSelected = signal(str)
    customSelected = signal()
    adminSelected = signal()

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


        admin_btn = QPushButton("Admin")
        admin_btn.clicked.connect(self.adminSelected.emit)
        layout.addWidget(admin_btn, 4, 1)
        self.setLayout(layout)

    def setDrinkButtons(self, availableDrinks):
        # Clear existing buttons
        for i in reversed(range(self.layout().count())):
            widget = self.layout().itemAt(i).widget()
            if isinstance(widget, QPushButton) and widget.text() != "Make Your Own Drink" and widget.text() != "Admin":
                self.layout().removeWidget(widget)
                widget.deleteLater()

        # Add buttons for available drinks
        for i, drink in enumerate(availableDrinks):
            btn = QPushButton(drink.getName())
            btn.clicked.connect(lambda _, d=drink.getName(): self.drinkSelected.emit(d))
            self.layout().addWidget(btn, i//3, i%3)

    def updateDrinkButtons(self):
        availableDrinks = []
        for md in mixedDrinks:
            if md.getAvailable():
                availableDrinks.append(md)
        self.setDrinkButtons(availableDrinks)

# Custom Drink Page
class CustomDrinkPage(QWidget):
    submitSelected = signal(list)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.drink_buttons = []
        self.drink_sliders = []
        checkbox_font = QFont()
        checkbox_font.setPointSize(16)
        checkbox_style = "QCheckBox::indicator { width: 30px; height: 30px; }"

        # create 8 selectable options
        for d in drinks:
            i = drinks.index(d)
            row = QVBoxLayout()

            top_row = QHBoxLayout()
            btn = QCheckBox(d.getName())
            btn.setFont(checkbox_font)
            btn.setStyleSheet(checkbox_style)
            sliderLabel = QLabel("Amount: 0 ml")

            top_row.addWidget(btn)
            top_row.addWidget(sliderLabel)
    
            slider = QSlider(Qt.Horizontal)
            slider.setFixedHeight(40)
            slider.setStyleSheet("""QSlider::handle:horizontal {width: 35px; height: 35px;margin: -8px 0;}""")
            slider.setRange(0, 300)
            slider.setMinimum(0)
            slider.setValue(0)
            slider.setMaximum(300)
            slider.setTickInterval(50)
            slider.setSingleStep(10)
            slider.setTickPosition(QSlider.TicksBelow)

            #sliderLabel = QLabel("Amount: 0 ml")
            slider.valueChanged.connect(lambda value, label=sliderLabel: label.setText(f"Amount: {value} ml"))

            row.addLayout(top_row)
            row.addWidget(slider)

            self.drink_buttons.append(btn)
            self.drink_sliders.append(slider)
            layout.addLayout(row)

        submit_btn = QPushButton("Submit")
        submit_btn.clicked.connect(self.handle_submit)
        layout.addWidget(submit_btn, alignment=Qt.AlignCenter)

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

    def resetSelections(self):
        for btn in self.drink_buttons:
            btn.setChecked(False)
        for slider in self.drink_sliders:
            slider.setValue(0)


# Making Drink Page
class MakingDrinkPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.label = QLabel("Making Drink...")
        font = self.label.font()
        font.setPointSize(24)
        self.label.setFont(font)
        layout.addWidget(self.label, alignment=Qt.AlignCenter)
        self.setLayout(layout)

    def start_timer(self, callback):
        """Start 10-second timer then call callback."""
        QTimer.singleShot(10000, callback)

# Password Page
class PasswordPage(QWidget):
    accessGranted = signal()
    returnToMain = signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.label = QLabel("Enter Admin Password")
        self.input = QLineEdit()
        self.input.setEchoMode(QLineEdit.Password)
        self.submit_btn = QPushButton("Submit")
        self.submit_btn.clicked.connect(self.check_password)
        self.return_btn = QPushButton("Return to Main Menu")
        self.return_btn.clicked.connect(self.returnToMain.emit)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.submit_btn)
        layout.addWidget(self.return_btn)
        layout.addWidget(self.error_label)
        self.setLayout(layout)

    def check_password(self):
        if self.input.text() == "admin123":
            self.error_label.setText("")
            self.accessGranted.emit()
        else:
            self.error_label.setText("Incorrect Password. Try Again.")
            self.input.clear()

# Admin Page
class AdminPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        self.label = QLabel("Admin Page - Settings and Controls")
        layout.addWidget(self.label)
        self.setLayout(layout)

# List of drinks
drinks = [
    drink("Lemonade", 1, True),
    drink("Sweet Tea", 2, True),
    drink("Coke", 3, True),
    drink("Diet Coke", 4, True),
    drink("Rum", 5, True),
    drink("Vodka", 6, True),
    drink("Tequila", 7, True),
    drink("Orange Juice", 8, True),]

# List of the 3 available mixed drinks
mixedDrinks = [
    mixedDrink("Arnold Palmer", 2, ["Lemonade", "Sweet Tea"], [150, 150]),
    mixedDrink("Lemonade", 1, ["Lemonade"], [300]),
    mixedDrink("Sweet Tea", 1, ["Sweet Tea"], [300]),
    mixedDrink("Rum and Coke", 2, ["Rum", "Coke"], [100, 200]),
    mixedDrink("Vodka Lemonade", 2, ["Vodka", "Lemonade"], [100, 200]), 
    mixedDrink("Rum and Diet Coke", 2, ["Rum", "Diet Coke"], [100, 200]),
    mixedDrink("Coke", 1, ["Coke"], [300]),
    mixedDrink("Tequila Orange Juice", 2, ["Tequila", "Orange Juice"], [100, 200]),
    mixedDrink("Orange Juice", 1, ["Orange Juice"], [300])
]

def main():
    app = QApplication(sys.argv)
    font = app.font()
    font.setPointSize(12)
    app.setFont(font)
    window = MainWindow()
    window.setWindowTitle("Arthur")
    window.resize(2000, 2000)
    window.showMaximized()
    # Use full screen on touch screen
    #window.showFullScreen()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()