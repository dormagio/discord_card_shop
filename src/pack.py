#!/usr/bin/env python3

import random
import json
import sqlite3
#TCG module consists of a tcg class with a bunch of useful helper functions, and tcg specific subclasses that make use of them.
from tcg import yugioh as tcg #Import the yugioh subclass of the tcg class so we can access abreviations. All tcg subclasses are designed to not be instantiated to avoid wasting time per pack.
import tools.inventoryManager as dbtools

#Define some error classes for clarity
class NoPackEntryError(Exception):
    pass
    
class NoPackCardsError(Exception):
    pass

class InvalidRarityError(Exception):
    pass

class pack:
    #In addition to the setcode, we will now take a sqlite3 database cursor that is used to get the card lists on demand.
    #I think accessing the database a few more times will still be faster than loading the json, but I could be wrong.
    #FUTURE: Investigate whether a preprocess step to pull the entire cardlist and split into lists by rarity would have better performance.
    def __init__(self, setcode, con):
        self.cur = con.cursor() #Make a new cursor just for this object using the passed in database connection so we don't step on anyone else's access when we change row_factory
        try:
            self.verifySetcode(setcode)
        except NoPackEntryError as exc:
            raise ValueError from exc
            
        #For the purposes of the pack object, once we have verified the setcode, we will only be needing to access the pack's card table so we will set our personal cursor's row factory to a lambda that gets the first entry of the return tuple.
        self.cur.row_factory = lambda cursor, row: row[0]
        
    #Function to both sanitize the set_code input and ensure it returns a valid record before proceeding.
    #It is distinctly possible that product.py, which only uses setcode through the safe cur.execute replacement could pass us a malicious setcode so we have to be careful.
    def verifySetcode(self,setcode):
        #Query the database for the set_code using the setcode.
        self.cur.execute("SELECT set_code,pools FROM inventory WHERE set_code = (?)",(setcode,))
        #Replace the stored setcode with the new result that should be safe to use.
        packinfo = self.cur.fetchone()
        if(packinfo is None):
            raise NoPackEntryError
        self.setcode = packinfo[0]
        #Expand the pools string back into a list of lists
        pools = dbtools.splitDatabaseField(packinfo[1])
        #Unfortunately, the ints are now strings so we need to change them back for the rest of our logic.
        #I think this is about as efficient as I can make this without backtracking and figuring out how to store the pools as ints.
        self.pools = [list(map(lambda ele : int(ele) if ele.isdigit() else ele, x)) for x in pools]            
        
    #Function that generates the rarity slots for a pack then generates the contents.
    #Can be called multiple times.
    def open(self):
        try:
            self.calculatePackSlots()
        except TypeError as exc:
            raise RuntimeError(f'Experienced a type error in calculatePackSlots(). It is likely that the pools field for {self.setcode} has not been updated') from exc
        try:
            self.populatePack()
        except NoPackCardsError as exc:
            raise RuntimeError('Pack open method failed. There is either a spelling error in the rarities of the pools or cardlist, or the specified cardlist doesn\'t exist') from exc
        
    #This function expects pools to be shaped as (probability,rarity,quantity)
    #If the probability of a pool is less than 100, it is expected that the next pools, in order, will be the next possibilities for a pack slot, in ascending order, ending at 100.
    #i.e. [(100,"Common",7),(100,"Rare",1),(63,"Common",1),(84,"Super Rare",1),(94,"Ultra Rare",1),(100,"Secret Rare",1)]
    def calculatePackSlots(self):
        roll = 0
        self.slots = []
        for pool in self.pools:
            #On 100 pools, we reset roll to 0 because we are either at the end of a set of a variable slot and are ready to reroll, or this is a fixed slot and it doesn't matter if we do it and make the logic simpler
            if(pool[0] == 100):
                #If roll = 101, then we are at the end of a variable pool and have already selected a pool. Otherwise we are either in a variable slot and haven't picked a pool, or this is a fixed slot.
                if(roll != 101):
                    self.slots.append(pool)
                roll = 0
            else:
                #If we have just left a 100 pool, and thus know that we are at the start of a new variable slot, roll a number between 1 and 100
                if(roll == 0):
                    # Select a random integer between 1 and 100 (inclusive)
                    roll = random.randrange(1, 100, 1)
                #Check if we rolled this pool
                if(roll < pool[0]):
                    self.slots.append(pool)
                    roll = 101
                    
    #This function takes the calculated slots and randomly generates the contents of each slot.
    #For the purposes of database management, the cardlist field contains a list of [rarity,card,setcode] while the packstring is a nice, printable string of the packs contents.
    def populatePack(self):
        self.cardlist = []
        #For num_cards_per_slot, slot_rarity, pull cards and add them to the cardlist
        for p,r,n in self.slots:
            pool = self.getRarityPool(r)
            pulls = random.sample(pool, n)
            #For each pull, form a list of abreviated rarity,card,setcode.
            rarity = tcg.abreviations[r]
            markedpulls = [(rarity,card,self.setcode) for card in pulls]
            self.cardlist.extend(markedpulls)
            
        #Once contents have been generated, parse them into a single string for printing
        self.packstring = f"\nPack of {self.setcode} contains:\n\n" #This should clear the packstring if rerun.
        for r,c,s in self.cardlist: #The s is setcode, but that is only used by things that make pack objects, not the pack object itself.
            self.packstring = self.packstring + r.ljust(5) + c + "\n"                    
            
    def getRarityPool(self, rarity):
        #Query database using the sanitized setcode and the given rarity and return the result as a list of strings per the row_factory
        query = f"SELECT card_name FROM {self.setcode} WHERE rarity = (?)"
        try:
            self.cur.execute(query, (rarity,))
        except sqlite3.OperationalError as exc:
            raise NoPackCardsError from exc
        
        pool = self.cur.fetchall()
        
        if(pool is None):
            raise NoPackCardsError
        else:
            return pool
        
    def getPackString(self):
        return self.packstring
    
    
    #Return the packlist
    def getPulls(self):
        return self.cardlist 

                
                

#With slight modifications, the old style of pack is now a subclass of pack.
#The new pack class will have better performance with the database integration, but the old style that uses json is useful for debug and small custom applications so it will be maintained as a subclass.
class jsonPack(pack):
    #Instantiation takes a setcodecode and generates a pack from it.
    def __init__(self, setcode):
        
        self.verifySetcode(setcode)
        self.pools = self.packinfo["pools"]
    
    #Because we don't have database for this class, we instead overload this method to load the json instead.
    def verifySetcode(self):
        #Open, load, and close the json file named with the setcode
        try:
            file = open("./database/" + setcode + ".json", "r")
        except FileNotFoundError as exc:
            raise NoPackEntryError
        #Dictionary holding dictionary loaded from json file
        self.packinfo           = json.load(file)
        file.close()
        
    def getRarityPool(self, rarity):
        try:
            return self.packinfo[rarity]
        except KeyError as exc:
            raise NoPackCardsError

def openPack(setcode): 
    #Everything wants an all caps setcode so just make sure it is all caps
    mypack = pack(setcode.upper())
    return mypack.getPackString()
    
def printPack(setcode):
    print(openPack(setcode))

def openPacks(setcode, num_packs):    #Everything wants an all caps setcode so just make sure it is all caps
    mypack = pack(setcode.upper()) #Pack contents are populated when the object is made.
    packlist = []
    for i in range(num_packs):
        packstring = "\nPack " + str(i+1) + "\n" + mypack.getPackString() #For clarity, packs are numbered
        packlist.append(packstring)
        mypack.reopenPack() #Regenerate pack contents
    return packlist
        
def printPacks(setcode, num_packs):
    # print(openPacks(setcode, num_packs))
    packlist = openPacks(setcode, num_packs)
    #Print each pack with an extra space between
    for s in packlist:
        print("\n",s)