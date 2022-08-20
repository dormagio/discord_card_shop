#!/usr/bin/env python3

#This is a simple command line tool to translate back and forth between a .ydk file used by EdoPro and plaintext yugioh card names

import argparse
import sqlite3
import pathlib

#Function that takes a string path to a YDK file, a valid database cursor to an EdoPro card database, and an optional outfile name
#Uses the database cursor to rewrite the ydk with plaintext card names.
def ydk_to_text(ydk_file_path,cur,delta_cur,plaintext_file=None):
    ydk_path = pathlib.PurePath(ydk_file_path)
    with open(ydk_path,"r") as ydk:
        if plaintext_file is not None:
            outfile_name = plaintext_file
        else:
            outfile_name = f"{ydk_path.stem}.txt"
        
        outpath = ydk_path.with_name(outfile_name)
        with open(outpath,"w") as out:
            for line in ydk.readlines():
                #No processing required for comment/special characters and empty lines
                if(line[0]=="!" or line[0]=="#" or line == ""):
                    out.write(line)
                elif(line.strip().isnumeric()):
                    #Look up the idcode in the database
                    cur.execute("SELECT name FROM texts WHERE id = (?)",(line.strip(),))
                    name = cur.fetchone()
                    if(name is not None):
                        out.write(f"{line.strip()} - {name[0]}\n")
                    else:
                        #Check the delta database
                        delta_cur.execute("SELECT name FROM texts WHERE id = (?)",(line.strip(),))
                        name = delta_cur.fetchone()
                        if(name is not None):
                            out.write(f"{line.strip()} - {name[0]}\n")
                        else:
                            print(line.strip())
                            out.write(line)



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Tool to enable manual editing of .ydk files without looking up card idcodes all the time")
    parser.add_argument('-ydk','--ydk_file_path',action='store',default=None,help='Path to the ydk file you wish to convert')
    parser.add_argument('-out','--outfile',action='store',default=None,help='Optional full path to the output file you wish to create. Defaults to renaming the infile with the appropriate extension (.ydk or .txt)')
    parser.add_argument('-db','--database_path',action='store',default=None,help='Optional full path to the card database to use. If no specified, the script will try to guess the location based on the default install path of edopro(on Windows)')
    args = parser.parse_args()
    
    
    if(args.database_path is None):
        #Attempt to find the database based on assumed windows install location of edopro. I am using windows because I assume most players will be using windows and not want to install wsl
        database = pathlib.Path("C:/ProjectIgnis/repositories/delta-utopia/cards.cdb")
        #Apparently new stuff lives in a "delta" database until some unknown point...
        delta_database = pathlib.Path("C:/ProjectIgnis/repositories/delta-utopia/cards.delta.cdb")
    else:
        database = pathlib.Path(args.database_path)
        
    if(database.is_file()):
        con = sqlite3.connect(database)
        delta_con = sqlite3.connect(delta_database)
    else:
        sys.exit("Cannot find card database")
    
    if(args.ydk_file_path is not None):
        ydk_to_text(args.ydk_file_path,con.cursor(),delta_con.cursor(),args.outfile)