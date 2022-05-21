#!/usr/bin/env python3

import sys
import argparse
import requests
import time
from datetime import datetime
import json

#Function that takes a setcode and calls incrementing set numbers until we get an error and add the sets to cardlist by rarity.
def getSetFromWeb(raw_setcode,language_code='EN'):
    lc_length = len(language_code)
    #Everything needs setcode to be uppercase, so ensure this is the case.
    setcode = raw_setcode.upper()
    print("Retrieving Data for set " + setcode)

    #Flag to deal with missing database entries
    tried_skipping = False
    
    #List of Skipped cards that need attention
    skipped_cards = []
    
    cardnumber  = 0

    
    #Create a dictionary holding all of our collected set information
    setinfo = {}
    #Start an empty list containing all rarities that are found in the pack, regardless of whether they are part of pools.
    setinfo["all_pack_rarities"] = []
    
    #Start calling increasing card numbers until we have pulled the whole set.
    #There is a special exception for EN000 because some sets have that, but most don't.
    while(True):
        #create a request object with the response to the online database call for the current cardnumber.
        #It seems like the language+number is always 5 digits so we can make some assumptions based on the length of language_code
        if(lc_length == 4):
            card = requests.get('https://db.ygoprodeck.com/api/v7/cardsetsinfo.php?setcode=%s-%s%01d' % (setcode,language_code,cardnumber),timeout=5.0)
        elif(lc_length == 3):
            card = requests.get('https://db.ygoprodeck.com/api/v7/cardsetsinfo.php?setcode=%s-%s%02d' % (setcode,language_code,cardnumber),timeout=5.0)
        elif(lc_length == 2):
            card = requests.get('https://db.ygoprodeck.com/api/v7/cardsetsinfo.php?setcode=%s-%s%03d' % (setcode,language_code,cardnumber),timeout=5.0)
        else:
            printf("Unexpected Language Code Length")
            raise ValueError
        
        print("Retrieved data on card " + str(cardnumber))
        #Check if there is a name entry
        try:
            name = card.json()['name']
        except:
            #Just increment right here at the start of the excepted state so I don't accidentally loop in an expected fail state.
            cardnumber +=1
            if(cardnumber-1 == 0):
                #It is fine if card 0 doesn't exist
                print("There is no card 0 for this set.")
                continue
            #While pulling DUOV, I ran into an issue where DUOV-EN052 did not have an entry, even though it was supposed to be card of Fate. Because of this, I'm introducing a fuzzy skip to try to move past that error.
            elif(not tried_skipping):
                print("SKIPPING CARD: " + str(cardnumber-1))
                skipped_cards.append(str(cardnumber-1))
                tried_skipping = True
                continue
            else:
                #We think we have reached the end, stop the loop
                
                #If tried_skipping is set, then we have seen two invalid calls and are probably past the end of the set and should pop the last entry since it was genuinely not there.
                if(tried_skipping):
                    print("Popping skipped card: " + str(cardnumber-2))
                    skipped_cards.pop()
                break
            
        #Reset the tried_skipping flag because I bet this will happen again.
        tried_skipping = False
        

        #If rarity exists in setinfo, add it to the list, else create the list.
        rarity = card.json()['set_rarity']
        if(rarity in setinfo):
            setinfo[rarity].append(name)
        else:
            setinfo[rarity] = [name]
            setinfo["all_pack_rarities"].append(rarity)
        
        #According to documentation, if you poll the database 20 times/second, they will blacklist you. We delay just enough to ensure that won't happen
        print("Sleeping on card:" + str(cardnumber))
        cardnumber += 1

    setinfo['setcode'] = setcode
    #Transform through set to remove duplicate values
    setinfo['all_pack_rarities'] = list(set(setinfo['all_pack_rarities']))
    

    #If any cards got skipped, add a list of them to the json
    if(len(skipped_cards) > 0):
        setinfo['skipped_cards'] = skipped_cards
        
    return setinfo

def saveOrderedSetlist(raw_setcode, path, override, languagecode):
    setcode = raw_setcode.upper()
    setlist = getSetListFromWeb(setcode,override,languagecode)
    
    file = open(f"{path}{setcode}-{languagecode}_setlist.txt", "w")
    
    for c in setlist:
        file.write(c + ",\n")
        
    file.close()
    
#Future: Go find where I call this and use language_code instead of se.
def getSetListFromWeb(setcode, override = False, languagecode = "EN"):
    #Construct the request using parameters
    
    #If this is a search for special edition promos, the search string is different
    if(override):
        request_str = f'https://db.ygoprodeck.com/api/v7/cardsetsinfo.php?setcode={setcode}%03d'
    else:
        request_str = f'https://db.ygoprodeck.com/api/v7/cardsetsinfo.php?setcode={setcode}-{languagecode}%0{5-len(languagecode)}d'


    #Ordered list of cards
    setlist = []
    
    print("Generating setlist for set: " + setcode)
    
     #Start calling increasing card numbers until we have pulled the whole set.
    #There is a special exception for EN000 because some sets have that, but most don't.
    cardnumber  = 0
    tried_skipping = False
    while(True):
        
        #create a request object with the response to the online database call for the current cardnumber.
        card = requests.get(request_str % (cardnumber),timeout=5.0) 
        print("Retrieved data on card " + str(cardnumber))
        #Check if there is a name entry
        try:
            name = card.json()['name']
        except:
            #Just increment right here at the start of the excepted state so I don't accidentally loop in an expected fail state.
            cardnumber +=1
            if(cardnumber-1 == 0):
                #It is fine if card 0 doesn't exist
                print("There is no card 0 for this set.")
                continue
            #While pulling DUOV, I ran into an issue where DUOV-EN052 did not have an entry, even though it was supposed to be card of Fate. Because of this, I'm introducing a fuzzy skip to try to move past that error.
            elif(not tried_skipping):
                print("SKIPPING CARD: " + str(cardnumber-1))
                setlist.append(str(cardnumber-1))
                tried_skipping = True
                continue
            else:
                #We think we have reached the end, stop the loop
                
                #If tried_skipping is set, then we have seen two invalid calls and are probably past the end of the set and should pop the last entry since it was genuinely not there.
                if(tried_skipping):
                    print("Popping skipped card: " + str(cardnumber-2))
                    setlist.pop()
                break
            
        #Reset the tried_skipping flag because I bet this will happen again.
        tried_skipping = False
        setlist.append(name)
            
        #According to documentation, if you poll the database 20 times/second, they will blacklist you. We delay just enough to ensure that won't happen
        print("Sleeping on card:" + str(cardnumber))
        # time.sleep(5.0)
        cardnumber += 1
        
    return setlist
    

#We will add more functions later as we define the interface with our own databases more. Eventually will probably want to have seperate functions for saving to json or database.

#Function to query the database for a total product listing and make some guesses about some of the fields
def makeNewProductList(earliest_product_date,path='./'):
    #We assume the filter date uses the same format as the database dates.
    filter_date = datetime.strptime(earliest_product_date,"%Y-%m-%d")

    with open(path + "products.json", "x") as productfile:
        cardsets = requests.get('https://db.ygoprodeck.com/api/v7/cardsets.php',timeout=5.0)
        
        print("Retrieved list of all cardsets from web")
        list_of_product_dicts = cardsets.json()
        
        
        products = {}
        for product in list_of_product_dicts:
            #I was going to be clever about this, but since I already am looping through everything and this doesn't run often, I'll just do this here.
            #Compare dates using datetime
            
            try: #Not all entries in the remote database have tcg_date entries, annoyingly.
                release_date = product['tcg_date']
                release_date = datetime.strptime(release_date,"%Y-%m-%d")
                if(release_date>=filter_date):
                    products[product["set_name"]] = processPulledProduct(product,release_date)
                else:
                    pass
            except:
                print("No tcg_date for " + product["set_name"])
            
            
        overhead = {}
        overhead["category"] = "overhead"
        overhead["import"] = False
        products["System Overhead"] = overhead
        json.dump(products,productfile,indent=2)
        
def processPulledProduct(product,release_date):
    #Scan contents of each field and make some guesses about the fields we need.
    name = product['set_name']
    try:
        setcode = product['set_code']
    except:
        print("No setcode for " + name)
       
    
    #Keep every entry identical and just set some default values...
    product['category'] = "Unassigned"
    product['promos'] = ""
    product['card_list'] = ""
    product['packs'] = ""
    product['import'] = False
    
    #Check name for some easy words
    
    #Decks are just fixed sets (Except I think the Starter Deck V for Victory? I think it had some kind of booster pack? Don't know if that is included...)
    if(name.find("Deck") != -1):
        product['category'] = "Deck"
        product['card_list'] = getSetListFromWeb(setcode)
    #Check if this is a repackage with promos
    elif(name.find("Special Edition") != -1 or name.find("Advance Edition") != -1 or name.find("Deluxe Edition") != -1 or name.find("Secret Edition") != -1 or name.find("Gold Edition") != -1):
        product['category'] = "Special Edition"
        #This won't universally make a usable promo list, but it will at least get all the data there. Pretty sure I need to go back and make promos smarter anyway...
        product['promos'] = getSetListFromWeb(setcode,True)
        product['packs'] = [setcode, 3]
    #Pretty self explanatory...
    elif(name.find(" Tin") != -1):
        product['category'] = "Tin"
        product['promos'] = getSetListFromWeb(setcode,False)
    #Now for some easy name patterns (Battles of Legend:, Dragons of Legend, Hidden Arsenal, etc...)
    elif(name.find("Battles of Legend:") != -1 or name.find("Battle Pack") != -1 or name.find("Dragons of Legend") != -1 or name.find("Hidden Arsenal") != -1):
        if(release_date.year<2016):
            product['category'] = "Legacy Pack"
        else:
            product['category'] = "Current Pack"
    elif(name.find("Legendary Duelists") != -1):
        product['category'] = "Legendary Duelist Pack"
    
    return product

#Code for running this as a command line tool
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('setcode', help='setcode of the pack you wish to pull from the database')
    parser.add_argument('-l', '--list', action='store_true', help='Pull given set from database and save an ordered, csv setlist')
    parser.add_argument('-j', '--json', action='store_true', help='Pull given set from database and save a json file for use by pack.py')
    parser.add_argument('-p', '--path',action='store',default='./', help ='Optional Argument to pass directory to write to (does not include file name as that is hardcoded in many places). Defaults to current directory')
    parser.add_argument('-r', '--report',action='store_true',help='Reports all parsed args')
    parser.add_argument('-o', '--override',action='store_true',default=False,help='Flag to cause the setcode to override the language code and be passed for both as. Ex: "SYE-"')
    parser.add_argument('-c', '--language_code', action='store',default='EN',help='Optionally specify a language code for the set. Default is \'EN\'')

    args = parser.parse_args()
    
    #Check flags for what to do.
    if(args.report):
        for arg in vars(args):
            print(arg, getattr(args, arg))
    
    
    if(args.list):
        saveOrderedSetlist(args.setcode,args.path,args.override,args.language_code)
    if(args.json):
        getSetFromWeb(args.setcode,args.language_code)