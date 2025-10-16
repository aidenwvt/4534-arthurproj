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

        print(drinkName)
        print(type(drinkName))

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
