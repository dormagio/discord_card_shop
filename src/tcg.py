
#Maybe use abstract class to make it clear that this needs to be subtyped?
#Helper classes and functions for getting tcg specific information. tcg class is meant to be subclassed per game and all helper functions are written assuming all information in the template tcg class is populated.
#tcg class is not intended to be instantiated as it is primarily used as a fancy dictionary and we don't want to waste resources creating and destroying the object over and over.

class tcg:
    #Create a dictionary of abbreviated rarities to use for printing.
    abreviations = {}
    pools = {}
    
    def guessCategory(category):
        return "idunno"

#Define a yugioh subclass of tcg to use for packs and inventory management.
class yugioh(tcg):
    #Create a dictionary of abbreviated rarities to use for printing.
    abreviations = {'World Premiere': 'PSCR',\
                    'Art': 'PSCR',\
                    'Reprint': 'PSCR',\
                    'Common': 'C',\
                    'Common 1': 'C',\
                    'Common 2': 'C',\
                    'Common 3': 'C',\
                    'Rare': 'R',\
                    'Mosaic Rare': 'MR',\
                    'Starfoil Rare': 'STRF',\
                    'Shatterfoil Rare': 'SHTR',\
                    'Super Rare': 'SR',\
                    'Ultra Rare': 'UR',\
                    'Secret Rare': 'SCR',\
                    'Prismatic Secret Rare': 'PSCR',\
                    'Ultimate Rare': 'ULT',\
                    'Starlight Rare': 'STAR',\
                    'Gold Rare': 'G',\
                    'Gold Rare 1': 'G',\
                    'Gold Rare 2': 'G',\
                    'Gold Secret Rare': 'GS',\
                    'Premium Gold Rare': 'PGR',\
                    'Ghost Rare': 'GHOST', \
                    'Unknown Rarity': 'NOPE',\
                    'Short Print': 'NOT'\
                    }
                    
    pools = {   
                'ots_pool' : [[100,"Common",2],[94,"Super Rare",1],[100,"Ultimate Rare",1]],
                'legacy_pool' : [[100,"Common",7],[100,"Rare",1],[63,"Common",1],[84,"Super Rare",1],[94,"Ultra Rare",1],[100,"Secret Rare",1]],
                'modern_pool_type1' : [[100,"Common",7],[100,"Rare",1],[75,"Super Rare",1],[92,"Ultra Rare",1],[100,"Secret Rare",1]],
                'modern_pool_type2' : [[100,"Common",8],[75,"Super Rare",1],[92,"Ultra Rare",1],[100,"Secret Rare",1]],
                'modern_pool_type3' : [[100,"Rare",6],[83,"Super Rare",1],[100,"Ultra Rare",1]],
                'legendary_duelists_pool' : [[100,"Common",3],[100,"Rare",1],[75,"Super Rare",1],[100,"Ultra Rare",1]],
                'deckbuilder_pool' : [[100,"Super Rare",4],[100,"Secret Rare",1]],
                'legends_pool' : [[100,"Ultra Rare",4],[100,"Secret Rare",1]],
                'season_box' : [[100,"Common",10],[100,"Ultra Rare",3]],
                'duov' : [[100,"Ultra Rare",5]]
            }
            
    def guessCategory(pool_type):
        if(pool_type == "ots_pool"):
            return "ots"
        elif(pool_type == "legacy_pool"):
            return "Legacy Pack"
        elif(pool_type == "modern_pool_type1" or pool_type == "modern_pool_type2" or pool_type == "modern_pool_type3" or pool_type == "deckbuilder_pool" or pool_type == "legends_pool"):
            return "Current Pack"
        elif(pool_type == "legendary_duelists_pool"):
            return "Legendary Duelist Pack"
        elif(pool_type == "season_box"):
            return "Legendary Duelist Box"
        else:
            return "overhead"
#Function that takes a reference to a tcg class and prints out the abreviations dictionary
def listAbreviations(class_reference):
    for key in class_reference.abreviations.keys():
        print(f"\t{key} : {class_reference.abreviations[key]}")
            
def listPoolTypes(class_reference):
    for key in class_reference.pools.keys():
        print(f"\t{key} : ",end='')
        print(class_reference.pools[key])
        
def getPools(class_reference,pool_type):
    return class_reference.pools[pool_type]