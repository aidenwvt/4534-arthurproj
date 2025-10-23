import sys
from time import sleep as wait
from PyQt5.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget
# Class for drinks. Each drink has a name, container number, availability status, and amount of mls in container. If a drink runs out or is not in one of the 12 containers,
# it will be marked as unavailable. The drinks will not be shown to the user.
class drink:
    def __init__(self, name, container, available):
        self.name = name
        self.container = container
        self.available = available
        self.amount = 1000  # Default amount in ml
    
    def setName(self, name):
        self.name = name

    def setContainer(self, container):
        self.container = container
    
    def setAvailable(self, available):
        self.available = available

    def setAmount(self, amount):
        self.amount = amount

    def getName(self):
        return self.name 

    def getContainer(self):
        return self.container
    
    def getAvailable(self):
        return self.available
    
    def getAmount(self):
        return self.amount
    
# List of drinks
drinks = [
    drink("Lemonade", 1, True),
    drink("Sweet Tea", 2, True),]

# Class for making a mixed drink. For now this class will only have three differnt values creatd for it.
# Each mixed drink will have a name, a number of drink items it uses, a list of those drink items, an amount in ml for each item, and 
# an availability status. The mixed drinks are what will be shown to the user. If a mixed drink uses a drink that is not available, it will be marked as unavailable.
class mixedDrink(drink):
    def __init__(self, name, numItems, items, amounts):
        self.name = name
        self.numItems = numItems
        self.items = items  # List of drink names
        self.amounts = amounts  # List of amounts in ml
        self.available = True  # Assume available by default

    def setNumItems(self, numItems):
        self.numItems = numItems

    def setItems(self, items):
        self.items = items

    def setAmounts(self, amounts):
        self.amounts = amounts

    def setAvailable(self, available):
        self.available = available

    def getNumItems(self):
        return self.numItems

    def getItems(self):
        return self.items

    def getAmounts(self):
        return self.amounts
    
    def getAvailable(self):
        return self.available
    
    # Function to update the amounts of each drink used in the mixed drink. If any drink does not have enough amount, the mixed drink will be marked as unavailable.
    # returns True if the mixed drink can be made, False otherwise.
    def updateAmounts(self):
        for i in range(self.numItems):
            item_name = self.items[i]
            item_amount = self.amounts[i]
            # Find the drink object that matches the item name
            drink_found = False
            for d in drinks:
                if d.getName() == item_name:
                    drink_found = True
                    if d.getAmount() >= item_amount:
                        d.setAmount(d.getAmount() - item_amount)
                    else:
                        self.available = False
                        return False
            if not drink_found:
                self.available = False
                return False
        return True

# List of the 3 available mixed drinks
mixedDrinks = [
    mixedDrink("Arnold Palmer", 2, ["Lemonade", "Sweet Tea"], [150, 150]),
    mixedDrink("Lemonade", 2, ["Lemonade"], [300]),
    mixedDrink("Sweet Tea", 3, ["Sweet Tea"], [300])
]

# Function to display available drinks
def displayAvailableDrinks():
    print("Available Drinks:")
    i = 1
    for md in mixedDrinks:
        if md.getAvailable():
            print(f"{i}: {md.getName()}")
            i = i + 1

# Function that will set a vector of all available mixed drinks
def getAvailableDrinks():
    availableDrinks = []
    for md in mixedDrinks:
        if md.getAvailable():
            availableDrinks.append(md)
    return availableDrinks

# Function that will handle making of drink.
def makeDrink(selected_drink):
    wait(1)  # Simulate time taken to make drink
    print(f"Your {selected_drink.getName()} is ready!")

# Main function to run the drink selection process
def main():
    displayAvailableDrinks()
    availableDrinks = getAvailableDrinks()
    choice = int(input("Select your drink by entering the corresponding number: "))
    if 1 <= choice <= len(availableDrinks):
        selected_drink = availableDrinks[choice - 1]
    else:
        selected_drink = None
    if selected_drink:
        if selected_drink.updateAmounts():
            print(f"You have selected: {selected_drink.getName()}, Now preparing your drink...")
            makeDrink(selected_drink)
        else:
            print(f"Sorry, {selected_drink.getName()} is currently unavailable due to insufficient ingredients.")
    else:
        print("Invalid selection or drink not available.")

if __name__ == "__main__":
    while True:
        main()