import json
import logging
import os

logger = logging.getLogger(__name__)

class drinkDatabase:
    def clearDatabase():
        with open('drinkData.json', 'w') as f:
            json.dump({}, f)

    def displayDatabase():
        with open('drinkData.json', "r") as file:
            data = json.load(file)

        print(json.dumps(data, indent=4))

    def retrieveDrink(drinkName):
        with open('drinkData.json', "r") as file:
            data = json.load(file)

        if isinstance(drinkName, bytes):
            drinkName = drinkName.decode("utf-8")

        try:
            drinkData = data.get(drinkName)
            return drinkData
        except:
            logger.error(f"Requested drink does not exist")
    
class simpleDrinks:
    def initializeSimpleDrinks():
        try:
            with open('drinkData.json', 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            data = {}

        lemonadeDrink = {
            "drink_name": "lemonade",
            "liquids": {
                "lemonade": 300
            },
            "ice": True,
        }

        sweetTeaDrink = {
            "drink_name": "sweetTea",
            "liquids": {
                "sweetTea": 300
            },
            "ice": True,
        }

        data["lemonade"] = lemonadeDrink
        data["sweetTea"] = sweetTeaDrink

        # Save data back to JSON file
        with open('drinkData.json', 'w') as file:
            json.dump(data, file, indent=4)

class mixedDrinks:
    def initializeMixedDrinks():
        try:
            with open('drinkData.json', 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            data = {}

        arnoldPalmerDrink = {
            "drink_name": "arnoldPalmer",
            "liquids": {
                "lemonade": 150,
                "sweetTea": 150,
            },
            "ice": True,
        }

        # Store booking data
        data["arnoldPalmer"] = arnoldPalmerDrink

        # Save data back to JSON file
        with open('drinkData.json', 'w') as file:
            json.dump(data, file, indent=4)

class Queue:
    FILE = "queue.json"

    @staticmethod
    def addToQueue(drinkData):
        """Append a new drink to the queue list."""
        if not os.path.exists(Queue.FILE):
            data = []
        else:
            with open(Queue.FILE, "r") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = []

        drinkData = drinkData[:3]

        liquids = {liquid: 150 for liquid in drinkData}
        customDrink = {
            "drink_name": "customDrink",
            "liquids": liquids,
            "ice": True
        }

        # Append to queue
        data.append(customDrink)

        with open(Queue.FILE, "w") as f:
            json.dump(data, f, indent=4)

    @staticmethod
    def getQueue():
        """Return and remove the first item from the queue."""
        if not os.path.exists(Queue.FILE):
            return None

        with open(Queue.FILE, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                return None

        if not data: 
            return None

        next_item = data.pop(0) 

        with open(Queue.FILE, "w") as f:
            json.dump(data, f, indent=4)

        return next_item