import json
import logging

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

        drinkName = drinkName.lower()

        drinkData = data.get(drinkName)
        if (drinkData != None):
            return drinkData
        else:
            return 0
    
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
        data["sweettea"] = sweetTeaDrink

        # Save data back to JSON file
        with open('drinkData.json', 'w') as file:
            json.dump(data, file, indent=4)

    def createSimpleDrink():
        pass

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

        data["arnoldpalmer"] = arnoldPalmerDrink

        # Save data back to JSON file
        with open('drinkData.json', 'w') as file:
            json.dump(data, file, indent=4)

    def createMixedDrink():
        pass
