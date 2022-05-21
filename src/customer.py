#!/usr/bin/env python3

import json
import os

class customer:
    #Instantiation
    
    #Open and load the named json and save the file handle while it is open.
    def __init__(self, customer_id : str, customer_nickname : str, customer_budget : int, ots : int):
        self.id = customer_id
        self.nickname = customer_nickname
        self.budget = customer_budget
        self.ots = ots
            
    def printCustomer(self):
        print('%s\t%.2f\t%d\t%s' % (self.id,self.budget,self.ots,self.nickname)) 

    def getList(self):
        return [self.id,self.nickname,self.budget]

    def getBudget(self):
        return self.budget
        
    def setBudget(self, value):
        self.budget = value
        
    def addMoney(self,value):
        self.budget += value
    
    def removeMoney(self,value):
        #Check if the amount subtracted would go below zero
        if(self.budget >= value):
            self.budget -= value
            result = self.budget
        else:
            result = "Insufficient Funds. Balance: " + str(self.budget)
        return result
        
    def getOts(self):
        return self.ots
        
    def setOts(self, value):
        self.ots = value;
        
    def addOts(self, value):
        self.ots += value
        
    def removeOts(self,value):
        #Check if the amount subtracted would go below zero
        if(self.ots >= value):
            self.ots -= value
            result = self.ots
        else:
            result = "Insufficient OTS Fun Coins. Balance: " + str(self.ots)
        return result

    def getId(self):
        return self.id
    #ID is the Primary Key of the database so while I am writing a function to overwrite it, it should never actually get called in practice.
    def setId(self,customer_id : str):
        self.id = customer_id
    def getNickname(self):
        return self.nickname
    def setNickname(self, customer_nickname : str):
        self.nickname = customer_nickname