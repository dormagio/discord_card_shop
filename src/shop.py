#!/usr/bin/env python3
import sqlite3
import json
import random
import pack
import customer
import product
import os
from collections import Counter
import csv
from enum import Enum

#Python Module for the handling of card shop inventory and pricing
#This file manages the associated database used to track customers, customer card lists, and inventory.

#Helper ENUM for determining budget type

class Wallet(Enum):
    #I am using crypto names as a joke, fuck crypto
    nocoin = 0 #Used only by admins for override packs
    birdbuckz = 1 #The standard currency used for most purchases
    otscoin = 2 #YUGIOH used to buy ots tournament packs, only awarded for participating in locals


class shop:
    
    def __init__(self, config_file_path = "./templates/config_template.json"):
        self.config_file_path = config_file_path
        self.config = self.getConfig()
        
        #Pull database paths from the config file.
        #Instance dependent database storing customer data (budget, cardlists,ots,etc.)
        #This database is not tracked by git
        self.shop_con = sqlite3.connect(self.config["shop_database"])
        self.shop_cur = self.shop_con.cursor()
        #Instance independent database containing inventory of all products
        #This database is tracked by git
        self.inventory_con = sqlite3.connect(self.config["inventory_database"])
        self.inventory_con.row_factory = sqlite3.Row #Set the row_factory to the versatile row object that can be used either as a tuple or a dictionary keyed with field names.
        self.inventory_cur = self.inventory_con.cursor()
        
        
        with open("./configs/prices.json", "r") as pricefile:
            self.prices = json.load(pricefile)
        self.updateShop(False)
        
    def __enter__(self):
        return self
        
    def __exit__(self):
        self.closeUpShop()
        
    def getConfig(self):
        with open(self.config_file_path, "r") as config_file:
            config = json.load(config_file)
            return config
    
    def saveConfig(self):
        with open(self.config_file_path, "w") as config_file:
            json.dump(self.config,config_file,sort_keys=True,indent=2)
        
    def updateShop(self,not_first_call=True):
        #If this isn't the initial call to this function, save data.
        if(not_first_call):
            self.saveAllCustomers()
        self.loadAllCustomersFromDatabase() #Get all customers from the database, retrieve as a dictionary keyed with customer ID's
        self.createNicknameMapping()
        
    #function to call when object is deleted.
    def closeUpShop(self):
        self.saveAllCustomers()
        self.shop_con.close()
        self.inventory_con.close()
        
    def printAllCustomers(self):
        print("ID\t\t\tBudget\tOTS\tName")
        for customer in self.customers.keys():
            self.customers[customer].printCustomer()
    
    def getAllCategories(self):
        return self.prices.keys()
        
    #Takes a string category and returns a list of tuples detailing every product matching that category from the database (rowid,set_name,)
    def getInventoryByCategory(self,category : str):
        self.inventory_cur.execute('SELECT rowid,set_name FROM inventory WHERE category = (?)', (category,))
        sub_inventory = self.inventory_cur.fetchall()
        return sub_inventory
        
    def mapNicknameToID(self,nickname):
        return self.ids[nickname]
        
    #Returns a list of 3 items
    #1-Boolean indicating if transaction went through
    #IF TRUE
        #2-Budget remaining after purchase
        #3-Purchase contents
    #IF FALSE
        #2-Total cost of purchase
        #3-Message indicating reason
        

    #Function that takes a product key, a boolean indicating whether that key is a number, and a boolean indicating if we should override the "overhead" category and try to open it as a pack.
    #Queries the shop database inventory table for a product based on either the row number or a setcode (not safe to use unless it is known to be unique) and returns a product object.
    #WARNING: If the admin_override parameter is set to True, behavior may be undefined if setcode does not refer to an entry with valid pack data.
    def getProductFromDatabase(self, product_key, key_is_number = True, admin_override = False):
        if(key_is_number): #Rowid case
            self.inventory_cur.execute('SELECT * FROM inventory WHERE rowid = (?)', (product_key,))
            product_entry = self.inventory_cur.fetchone()
        else: #Setcode case
            self.inventory_cur.execute('SELECT * FROM inventory WHERE set_code = (?)', (product_key.upper(),))
            product_entry = self.inventory_cur.fetchone()
        #Check if return was valid.
        if product_entry is None:
            print(f"Error: key {product_key} did not return a valid entry from the inventory database")
        else: #Create a product object using the retrieved data
            print(f"For debug purposes, the retrieved entry is\n\t{product_entry['set_name']}")
            return self.makeProduct(product_entry,key_is_number,admin_override)
        
    #Function that takes a list of values retrieved from the inventory table of the database and calls the appropriate constructor.
    #Expected fields, in order are:
    #0. set_name
    #1. set_code
    #2. num_of_cards
    #3. tcg_date
    #4. category
    #5. promos
    #6. card_list
    #7. packs
    #8. pools
    
    #FUTURE: the use of is*() functions makes this yugioh dependent, but the whole product class is kind of yugioh centric so I guess that's just a bridge I'll have to cross when I come to it.
    #WARNING: If the admin_override parameter is set to True, behavior may be undefined if setcode does not refer to an entry with valid pack data.
    def makeProduct(self, product_entry, key_is_number, admin_override = False):
        if(product.isPack(product_entry["category"])):
            constructor = product.individualPack
        elif(product_entry["category"] == "overhead" and admin_override): #If this is marked overhead and admin_override is enabled, GUESS that it is a pack (This is dangerous and should only be done by admins and experienced users)
            constructor = product.individualPack
        #The only type of product it is safe to make with a setcode is a pack.
        #If the product's category is not some kind of pack, and is also not a number, raise an error.
        elif(not key_is_number):
            raise TypeError
        elif(product.isFixedSet(product_entry["category"])):
            constructor = product.fixedSet
        elif(product.isBox(product_entry["category"])):
            constructor = product.box
        elif(product.isSpecialEdition(product_entry["category"])):
            constructor = product.specialEdition
        else:
            raise ValueError
        
        return constructor(product_entry,self.inventory_con)
    
    #FUTURE: This needs another revision to do a single return and have proper error flows
    
    #Function to attempt to buy N products
    #Takes:
    #customer_id        : str       : the ID of a customer stored in the database
    #product_key        : str       : number of product in database or setcode of pack in database
    #number_purchase    : int       : defaults to 1, number of product to attempt to purchase
    #wah                : wallet    : defaults to birdbuckz, determines which currency, if any, to use for the purchase (I named this while tired)
    def makePurchase(self, customer_id, product_key, number_purchased = 1, wah = Wallet.birdbuckz):
        #Make a product object with the given key. If it raises a ValueError it was not a valid category and if it is None, then it was not a valid key.
        
        #Attempt to convert the product key into an int. If it succeeds, then set key_is_number to true, else, false
        try:
            product_key = int(product_key)
            key_is_number = True
        except ValueError:
            key_is_number = False
            #YUGIOH
            #If the setcode starts with OP, then we must be using either ots coins or an admin override
            if(product_key[:2] == "OP" and wah != Wallet.otscoin and wah != Wallet.nocoin):
                raise ValueError
        
        #Attempt to create a product from the database
        try:
            #Query changes depending on the type of the key, but the default assumption is int.
            prod = self.getProductFromDatabase(product_key, key_is_number, (wah == Wallet.nocoin)) #We pass in the result of this check to indicate if it is an admin_override pack.
        except ValueError:
            return [False, 0, f"Value Error: {product_key} was not of a valid category"]
        except TypeError:
            return [False, 0, f"ID Error: {product_key} is not a saleable pack. If you were not trying to buy a pack, please use the product number"]
        else:
            if(prod is None):
                return [False, 0, f"Value Error: {product_key} was not a valid key"]
            else:
                #Deduct budget based on wallet type
                if(wah == Wallet.nocoin):
                    remaining_budget = 0 #Admin purchases don't have budgets
                    total_cost = 0
                elif(wah == Wallet.birdbuckz):
                    #Calculate total cost and see if the customer can afford it
                    price = self.prices[prod.category]
                    total_cost = price * number_purchased
                    
                    remaining_budget = self.customers[customer_id].removeMoney(total_cost) 
                    
                    #If there is enough money to make this purchase, remaining_budget will be an int with the remaining budget. If not, it will be a string stating "Insufficient Funds" and we need to return the cost and message
                    if(type(remaining_budget) is str):
                        return [False,total_cost,remaining_budget]
                elif(wah == Wallet.otscoin):
                    #Attempt to purchase (1 OTS Coin = 1 OTS Pack)
                    total_cost = number_purchased
                    remaining_budget = self.customers[customer_id].removeOts(number_purchased)
                    #If there is enough money to make this purchase, remaining_ots will be an int with the remaining number of OTS Fun Coins. If not, it will be a string stating "Insufficient Funds" and we need to return the cost and message
                    if(type(remaining_budget) is str):
                        return [False,number_purchased,remaining_budget]
                
                
                #If all is good, then we can open the product and complete the purchase.
                try:
                    purchase = []
                    purchase_contents = [] #This is a list of card tuples that will be passed to updateCustomerInventory()
                    for i in range(number_purchased):
                        purchase.append(f"\n\nProduct: {i+1}")
                        prod.open()
                        purchase_contents.extend(prod.getContents())
                        purchase.extend(prod.getPrintableContents())
                    #Here is where we will update the customer inventory
                    self.updateCustomerInventory(customer_id,purchase_contents)
                    return [True,remaining_budget,purchase]
                except RuntimeError as exc:
                    return [False,total_cost,f"Experienced the following error while opening your product; please consult an admin to receive a refund/fixed product:\n\n{exc}"]
    def getPriceByCategory(self, category):
        if category in self.prices:
            return self.prices[category]
        else:
            return "No category matching " + category + " found in prices."
            
    #Function that reads a central file and returns the price of the product based on the given category (Maybe this should be loaded into memory too?)
    def printProduct(self, product_name):
        myproduct = self.openProduct(product_name)
        print("Price for " + product_name + " is: $" + str(myproduct[0]) + "\n")
        
        for p in range(1, len(myproduct)):
            print(myproduct[p] + "\n")
            
    #Function that takes a list of customer ID numbers and updates the budget field of their entries with the allowance specified in config.json
    def giveAllowance(self, customer_list):
        
        for customer_id in customer_list:
            self.customers[customer_id].addMoney(self.config['allowance'])
            
    def setBudgetToGroup(self, customer_list, value):
        for customer_id in customer_list:
            self.customers[customer_id].setBudget(value)
            
    def setOTSForGroup(self, customer_list, value):
        for customer_id in customer_list:
            self.customers[customer_id].setOts(value)
            
    #Using the established connection to the database, loads all customer entries FROM THE DATABASE into a dictionary in the shop.
    def loadAllCustomersFromDatabase(self):
        self.customers = {}
        #Load the cursor with all entries from the customers table
        self.shop_cur.execute("select * from customers")
        #Get loaded values as a list of lists.
        temp = self.shop_cur.fetchall()
        
        for id,nickname,budget,ots in temp:
            self.customers[id] = customer.customer(id,nickname,budget,ots)
            
    #Returns a dictionary mapping nicknames to IDS (key:nickname,value:id)
    def createNicknameMapping(self):
        ids = {}
        
        for key in self.customers.keys():
            ids[self.customers[key].getNickname()] = self.customers[key].getId()
            
        self.ids = ids
    def getCustomersAsList(self):
        return self.ids.keys()
        
    def getCustomerIDs(self):
        return self.ids.values()
        
    def saveAllCustomers(self):
        #Write all of the customers to disk.
        for customer in self.customers.keys():
            self.shop_cur.execute("update customers set budget = (?),ots = (?) where id = (?)", (self.customers[customer].getBudget(),self.customers[customer].getOts(),self.customers[customer].getId()))
        #Save changes to database.
        self.shop_con.commit()

    def newCustomer(self, customer_id, customer_nickname):
        id_str = str(customer_id)
        
        self.shop_cur.execute('SELECT * FROM customers WHERE id = (?)', (id_str,))
        customer_entry = self.shop_cur.fetchone()
        
        if customer_entry is None:
            #Add entry to customers table
            self.shop_cur.execute("INSERT INTO customers VALUES (?,?,?,?)", (id_str,customer_nickname,self.config['Starting Budget'],0))
            #Create a table for the customer to track their cards
            make_customer_query = substituteCustomerID("CREATE TABLE {}(card_name TEXT NOT NULL, card_set TEXT NOT NULL, rarity TEXT NOT NULL, quantity INTEGER NOT NULL, PRIMARY KEY(card_name,card_set,rarity))",id_str)
            print(f"make_customer_query:\n{make_customer_query}\n")
            self.shop_cur.execute(make_customer_query)
            self.updateShop()
            return "Customer " + customer_nickname + " registered."
        else:
            return "Customer " + customer_nickname + " already exists."
            
    #In the interest of not fucking up, I am going to force people to use the primary key (Discord ID) instead of a nickname for this.
    def deleteCustomer(self, customer_id):
        id_str = str(customer_id)
        #Remove the customer from the customer table
        self.shop_cur.execute("DELETE FROM customers WHERE id=(?)",(id_str,))
        #Craft a statement to delete the customer's associated card table
        drop_customer_query = substituteCustomerID("DROP TABLE IF EXISTS {}",id_str)
        self.shop_cur.execute(drop_customer_query)
        self.updateShop()
        return "Customer " + id_str + " deleted."
        
    #Function that takes a customer_id and a list of cards where each card is a tuple of (rarity,card name,setcode) and checks the customer's ID# database table of cards.
    def updateCustomerInventory(self,customer_id,list_of_cards):
        #Using the specific function that checks the ID is a number, create our queries
        existing_card_query = substituteCustomerID("SELECT * FROM {} WHERE card_name=(?) AND card_set=(?) AND rarity=(?)",customer_id)
        insert_new_card_query = substituteCustomerID("INSERT INTO {} VALUES (?,?,?,?)",customer_id)
        update_card_query = substituteCustomerID("UPDATE {} SET quantity=(?) WHERE card_name=(?) AND card_set=(?) AND rarity=(?)",customer_id)
        print(existing_card_query)
        print(insert_new_card_query)
        print(update_card_query)
        #Before updating the database, reduce the list of card tuples into a dictionary that has a count of how many time a card appeared in the list
        #This allows us to only access the database once for each unique card.
        counted_cards = Counter(list_of_cards)
        
        #Next, query the database to see if the card already exists.
        for tup in counted_cards.keys():
            
            self.shop_cur.execute(existing_card_query,(tup[1],tup[2],tup[0])) #I have damned myself to scrambling by not paying attention to how I ordered the tuples while I ordered the database to be more human readable but I refuse to change the database.
            temp_entry = self.shop_cur.fetchone()
            if(temp_entry is None):
                self.shop_cur.execute(insert_new_card_query, (tup[1],tup[2],tup[0],counted_cards[tup]))
            else:
                new_quantity = temp_entry[3]+counted_cards[tup]
                self.shop_cur.execute(update_card_query,(new_quantity,tup[1],tup[2],tup[0]))

    #Function to retrieve the Customer's Inventory
    def getCustomerInventory(self,customer_id):
        #Use the safety function
        query = substituteCustomerID("SELECT * FROM {}",customer_id)
        self.shop_cur.execute(query)
        return self.shop_cur.fetchall()
        # return formatCustomerCardList(self.shop_cur.fetchall())
        
    #Function to retrieve all entries that match as specific card name from Customer's Inventory
    def searchCustomerInventory(self,customer_id,card_name):
        #Use the safety function
        query = substituteCustomerID("SELECT * FROM {} WHERE card_name LIKE (?)",customer_id)
        self.shop_cur.execute(query,(("%"+card_name+"%"),)) #% Is a sqlite wildcard. Adding that on either side of the card name allows for partial matching and searching things like archetypes.
        return formatCustomerCardList(self.shop_cur.fetchall())
        
    #Function to delete the card lists of every customer.
    def clearAllCustomerInventory(self):
        for id in self.getCustomerIDs():
            if(not self.clearCustomerInventory(id)):
                return False
                
        self.shop_con.commit() #This will be called at the end of seasons so we might as well commit it immediately.
        return True
    
    #Function to delete the card list of a single customer.
    #To save accesses, I don't commit on this one. I didn't make a command to call this function anyway, but I bet if I am ever directly using this I will be doing other operations anyway.
    def clearCustomerInventory(self, customer_id):
        try:
            query = substituteCustomerID("DELETE FROM {}",customer_id)
            self.shop_cur.execute(query)
        except:
            return False
        else:
            return True
    
#It is not good practice to do our own substitution, but in this function we can because the singular item we are substituting is the customer ID that MUST be a number.
def substituteCustomerID(query,customer_id):
    #Unfortunately, substitution does not work for the table name so we need to very carefully scrub the customer ID and insert it ourselves into the query. Luckily, this is easy because it will always be a number so we can just check isnumeric() and raise an error if that is not the case.
    if(customer_id.isnumeric()):
        return query.format("C" + customer_id)#We assume the query has {} in place of the customer ID in accordance with str.format(). We also prepend the character "C" to make sqlite happy with table names since it apparently doesn't like tables to start with numbers.
    else: #Customer ID will ALWAYS be a number.
        raise ValueError
        
#Function to convert a list of database card tuples into a list of neatly printed strings
def formatCustomerCardList(database_card_list):
    print_list = []
    for tup in database_card_list:
        #Because card names can be incredibly long, we print them last so we can justify things nicely.
        #Cards will be prints as: SETCODE | RARITY | QUANTITY | NAME
        print_list.append(f"{tup[1].ljust(4)} | {tup[2].ljust(5)} | {str(tup[3]).ljust(3)} | {tup[0]}\n")
    return print_list

def getListOfPacks():
    packs_in_stock = []
    for file in os.listdir("./database/"):
        if (file.endswith(".json") and file != "products.json" and file != "prices.json" and file != "inventory.json"):
            packs_in_stock.append(file[:-5])
    packs_in_stock.sort()
    return packs_in_stock
        