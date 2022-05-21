#!/usr/bin/env python3

#This is a collection of useful functions for manipulating data in the inventory database, as well as a command line tool to manipulate the inventory database (mostly by adding new entries to inventory and new pack tables)


import argparse
import json
import pathlib
import sqlite3
import tools.dbinterface as dbi
from tcg import yugioh as tcg,listPoolTypes,getPools
import glob

#Function that takes a list with up to 1 set of sublists and converts it to a single string using passed delimiters
def flattenListHierarchy(hierarchical_list,level_1_delimiter : str = "^",level_2_delimiter : str = "{}"):
    if(isinstance(hierarchical_list,list)): #First check if it is actually a list because I made this utter maddness.
        if(isinstance(hierarchical_list[0],list)): #If the first element of the potentially hierarchical list is another list, then we need to flatten the sublists first.
            pools = []
            for pool in hierarchical_list: #Join each sublist with the level 1 delimiter
                pools.append(level_1_delimiter.join(str(c) for c in pool))
            flattened_list = level_2_delimiter.join(pools) #Join the list of sublists with the level 2 delimiter
        else: #Just a straight list, join it.
            flattened_list = level_1_delimiter.join(str(c) for c in hierarchical_list)
    else:
        flattened_list = ""


    return flattened_list
    
#In the database, lists are encoded as strings and need to be split back into lists.
#The default delimiters are the same as in inventoryManager.py
#This function will always return a list of lists, even for an empty string ([['']]) so functions down the line can have simpler logic.
def splitDatabaseField(field : str, level_1_delimiter : str = "^", level_2_delimiter : str = "{}"):
    full_list = []
    stage_1_list = field.split(level_2_delimiter) #I probably didn't name these well but this breaks the string into the list of items that will themselves become sublists
    
    for l in stage_1_list:
        full_list.append(l.split(level_1_delimiter))
    return full_list

#Function to load the old product.json into a database.
def uploadProductJson(file_to_upload,cur):
    
    with open(file_to_upload, "r") as jsonfile:
        products = json.load(jsonfile)
    
        #Iterate over each product, parse its fields, and upload them to the database.
        for key in products.keys():
            product = products[key]
            
            #Flatten the promos into a single string of card pools
            #Pools are seperated by "{}"
            #Cards are seperated by "^"
            #example: "Beast-Eyes Pendulum Dragon"^"Number 23: Lancelot, Dark Knight of the Underworld"{}"Beacon of White"^"Forge of the True Dracos"
            
            #Flatten the promos list
            flat_promos = flattenListHierarchy(product["promos"])
            
            #Flatten the cardlist
            flat_cardlist = flattenListHierarchy(product["card_list"])
                  
            #Flatten the list of packs into just a list of 
            flat_packlist = flattenListHierarchy(product["packs"])
            
            #Add product and each field to database
            try:
                #For some reason, the set name and the value used as a key in the parent dictionary don't always match so just use the key.
                cur.execute("INSERT INTO inventory VALUES (?,?,?,?,?,?,?,?,?)", (key,product["set_code"],product["num_of_cards"],product["tcg_date"],product["category"],flat_promos,flat_cardlist,flat_packlist,product["import"]))
            except sqlite3.IntegrityError:
                print(f"Set {product} was not unique.")
                con.close()
                exit()
            except KeyError:
                print(f"Set {product} had a key error.")

def bulkUploadJson(cur,json_directory):
    for pack_json_file in glob.glob(f"{json_directory}/*.json"):
        legacyUpload(cur,pack_json_file)

#Function to load a pack json that follows the old pack style into the inventory database
def legacyUpload(cur,pack_json_file):
    print(f"Processing {pack_json_file}")
    #1. Load pack json
    with open(pack_json_file, "r") as file:
        pack_info = json.load(file)
    
        #2. process rarity pools into a flat list of lists formatted as [probability,rarity,quantity]
        #Iterate through the list of pack quantities and assign them to their associated pools
        pools = []
        pool_sizes = pack_info["pool_sizes"]
        slots = pack_info["rarities"]
        rarities = []
        for i in range(len(pool_sizes)):
            #If the corresponding slot in slots is a list, then we need to apply the quantity to all of the entries in the list. Else, just add the quantity to the pool.
            if(isinstance(slots[i][0],list)):
                #Variable slots are formatted as [[rarity,rarity,rarity],[probability,probability,probability]]
                for j in range(len(slots[i][0])):
                    pools.append([slots[i][1][j],slots[i][0][j],pool_sizes[i]])
                    rarities.append(slots[i][0][j])
            else:
                #Fixed slots are formatted as [rarity,probability]
                pools.append([slots[i][1],slots[i][0],pool_sizes[i]])
                rarities.append(slots[i][0])
        #3. Use flattenListHierarchy to compress pools
        pool_string = flattenListHierarchy(pools)
        
        #4. Get a list of cards using a set of the rarities pulled from the pools
        rarities = list(set(rarities))
        card_list = []
        
        for rarity in rarities:
            #Generate a list of the rarity name of equivalent size to the list of cards using list comprehension
            r = [rarity for x in range(len(pack_info[rarity]))]
            card_list.extend(tuple(zip(pack_info[rarity],r)))
            
    #I have repurposed the import field as the pools field.
    #In the newpack function, we will be finding things by full name, but here we need to automate based on setcode.
    #When querying the database for a setcode, the first result will be the pack and following results will be things like special editions
    #So we just grab the first result, update it with the pools, then update the database using the name of our retrieved entry
    cur.execute("SELECT * FROM inventory WHERE set_code = (?)",(pack_info["setcode"],))
    set_entry = cur.fetchone()
    
    cur.execute("UPDATE inventory SET pools = (?) WHERE set_name = (?)", (pool_string,set_entry[0]))
    
    #Finally, create a new table and populate it with the card_list
    #Only the database manager should ever run this so it is hopefully fine to just use standard string substitution.
    query = f'CREATE TABLE {pack_info["setcode"]}(card_name TEXT NOT NULL, rarity TEST NOT NULL)'
    cur.execute(query)
    query = f'INSERT INTO {pack_info["setcode"]} VALUES (?,?)'
    cur.executemany(query,card_list)
    
#Function to download a pack from the online database, process it, apply a specified pool pattern, and upload it to the database.
def addNewPack(cur, pack_name, pool_type):
    requires_attention = False

    #1. Pull the pack name entry from the database to get the setcode   
    cur.execute("SELECT set_code FROM inventory WHERE set_name = (?)",(pack_name,))
    set_code = cur.fetchone()[0]
    #2. Use dbinterface to pull down the pack data based on the setcode.
    setinfo = dbi.getSetFromWeb(set_code)
    #3. Look up the pool type from a constant (database, json, dictionary?) to populate the pool field
    setinfo["pools"] = getPools(tcg,pool_type)
    #4. Attempt to correct for unsupported rarities
    #First, assemble a list of rarities in the pools
    pool_rarities = []
    for p,r,q in setinfo["pools"]:
        pool_rarities.append(r)
        
    pool_rarities = list(set(pool_rarities))
    
    for rarity in setinfo["all_pack_rarities"]:
        if rarity in pool_rarities:
            pass
        else:
            #Check if we have a guess what to do with this rarity.
            #When a starlight rare list is generated from the ygopro database, generally it will be cards that are also in the set as secret rares, with the final card being exclusively starlight so it should be dropped.
            if(rarity == "Starlight Rare"):
                #If we don't have secret rares in this set, it might be safe to dump to Ultra Rares instead, but I haven't seen enough sets to be sure.
                if("Secret Rare" in pool_rarities):
                    setinfo[rarity].pop() #Pop the last card in the starlight set, this has so far always been a starlight exclusive reprint
                    setinfo["Secret Rare"].extend(setinfo[rarity])
                    #Remove the starlights so they don't get added twice to the database
                    del setinfo[rarity]
                else:
                    requires_attention = True
            else:
                requires_attention = True
    
    #5. Attempt to guess what category should be used
    setinfo["category"] = tcg.guessCategory(pool_type)
    
    #No matter what, if we skipped cards, then we need to dump to json and fix it.
    if("skipped_cards" in setinfo):
        requires_attention = True
                
    #6a. If correction is unsucessful, or if there are skipped cards, write pack to a json named after setcode for human correction.
    if(requires_attention):
        print("\n\nThere were problems encountered when pulling the set. Please inspect the JSON.\n\n")
        f = open("./" + set_code + ".json", "w")
        print("Dumping setinfo to " + set_code + ".json")
        json.dump(setinfo,f,sort_keys=True,indent=2)
        f.close()
    #6b. If correction is successful, push pack to database as new table.
    else:
        #Update inventory entry with pools and category
        pool_string = flattenListHierarchy(setinfo["pools"])
        cur.execute("UPDATE inventory SET pools = (?), category = (?) WHERE set_name = (?)", (pool_string,setinfo["category"],pack_name))
        
        #Create a total card list.
        card_list = []
        for rarity in pool_rarities:
            #Generate a list of the rarity name of equivalent size to the list of cards using list comprehension
            r = [rarity for x in range(len(setinfo[rarity]))]
            card_list.extend(tuple(zip(setinfo[rarity],r)))
        
        #Create a new table and populate it with the card_list
        #Only the database manager should ever run this so it is hopefully fine to just use standard string substitution.
        query = f'CREATE TABLE {setinfo["setcode"]}(card_name TEXT NOT NULL, rarity TEST NOT NULL)'
        cur.execute(query)
        query = f'INSERT INTO {setinfo["setcode"]} VALUES (?,?)'
        cur.executemany(query,card_list)
        
def uploadPackJson(cur,json_path):
        with json_path.open("r") as pj:
            setinfo = json.load(pj)
            
            #Update inventory entry with pools
            pool_string = flattenListHierarchy(setinfo["pools"])
            #Technically, this query will update things like sneak peak promos, special editions, and other stuff, but those things should both be deleted from the inventory and not use this field so it is fine.
            cur.execute("UPDATE inventory SET pools = (?), category = (?) WHERE set_code = (?)", (pool_string,setinfo["category"],setinfo["setcode"]))
            
            #First, assemble a list of rarities in the pools
            pool_rarities = []
            for p,r,q in setinfo["pools"]:
                pool_rarities.append(r)
                
            pool_rarities = list(set(pool_rarities))
                
            #Create a total card list.
            card_list = []
            for rarity in pool_rarities:
                #Generate a list of the rarity name of equivalent size to the list of cards using list comprehension
                r = [rarity for x in range(len(setinfo[rarity]))]
                card_list.extend(tuple(zip(setinfo[rarity],r)))
            
            #Create a new table and populate it with the card_list
            #Only the database manager should ever run this so it is hopefully fine to just use standard string substitution.
            query = f'CREATE TABLE {setinfo["setcode"]}(card_name TEXT NOT NULL, rarity TEST NOT NULL)'
            cur.execute(query)
            query = f'INSERT INTO {setinfo["setcode"]} VALUES (?,?)'
            cur.executemany(query,card_list)
        
#Code for running this as a command line tool
#I'm going to set constants assuming this is called from the root of the repo.
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Tool for managing the inventory.db file included as part of the cardShop repo. Defaults paths for this tool are set assuming it will be run from the root of the repository.")
    parser.add_argument('-db','--database',action='store',default='./database/inventory.db',help='Path, including filename, to the database that we are managing.')
    parser.add_argument('-i','--import_json',action='store',dest='products_json',default='DNE',help='Path, including filename, an existing products.json to be added to the database.')
    parser.add_argument('-g','--generate', action='store_true', help='Generates a product.json file in the current directory populated by making educated guesses based on the product name. Resulting file is not suitable for an instance of shop.')
    parser.add_argument('-d','--date', action='store',type=str,dest='earliest_product_date',default='2002-03-29',help='Set a filter date prior to which products will be excluded from the list')
    parser.add_argument('-lj','--legacy_json',action='store',default='DNE',help='Add a legacy pack json to the database')
    parser.add_argument('-b','--bulk_upload',action='store',dest='json_directory',default='DNE',help='Process all json files in the specified directory and upload them to the database.')
    parser.add_argument('-np','--new_pack',action='store',default='DNE',help='Using a full set name, add a pack to inventory by pulling it from the online database. Requires --pool_type option.')
    parser.add_argument('-pt', '--pool_type',action='store',default='DNE',help='Pool type to use for new inventory packs from list of pool types. Required if --new_pack is specified.')
    parser.add_argument('-l', '--list_pool_types',action='store_true',help='Print out a list of possible pool types.')
    parser.add_argument('-up','--upload_pack',action='store',type=pathlib.Path,default='DNE',help='Path to a dumped pack json to be uploaded to the database.')
    args = parser.parse_args()
    
    #For the sake of useability, these arguments will be made mutually exclusive with ones that require a target database so that we can skip that argument when we don't need it.
    if(args.list_pool_types or args.generate):
        if(args.list_pool_types):
            listPoolTypes(tcg)
            
        if(args.generate):
            dbi.makeNewProductList(args.earliest_product_date)
    else:
        #Open a connection to the database
        con = sqlite3.connect(args.database)
        cur = con.cursor()
        
        if(args.products_json != 'DNE'):
            uploadProductJson(args.products_json,cur)
                
        if(args.legacy_json != 'DNE'):
            legacyUpload(cur,args.legacy_json)
            
        if(args.json_directory != 'DNE'):
            bulkUploadJson(cur,args.json_directory)
            
        if(args.new_pack != 'DNE'):
            addNewPack(cur,args.new_pack,args.pool_type)
            
        if(args.upload_pack.name != 'DNE'):
            uploadPackJson(cur,args.upload_pack)
            
        con.commit()
        con.close()