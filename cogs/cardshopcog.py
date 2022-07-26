import discord
from discord.ext import commands, tasks
from discord.utils import get
import pack
import shop
import customer
import time
from datetime import datetime
import gspread #Google sheets API. Requires user to have set up authentication with google sheets for a services account (https://docs.gspread.org/en/latest/oauth2.html)

class CardShopCog(commands.Cog):
    #Discord Cog to handle the opening of Trading Card Packs and Sets.
    
    def __init__(self, bot):
        self.bot = bot
        self.server_shop = shop.shop(config_file_path="./configs/config.json")
        
        self.gc = gspread.service_account(filename = 'configs/service_account.json') #Authenticated account handle to interact with google sheets.
        #Attempt to open a handle to "Customer Inventories". If it fails, the sheet doesn't exist and just set the handle to None.
        try:
            self.customer_workbook = self.gc.open("Customer Inventory")
        except gspread.exceptions.SpreadsheetNotFound:
            self.customer_workbook = None #If the sheet doesn't exist, set this to None and we will make it next time get_my_cards is called.
        
        self.clean_sheets.start()
    #Cleanup function that gets called when the cog gets unloaded.
    def cog_unload(self):
        self.server_shop.closeUpShop()
        self.weekly_allowance.cancel()
        self.weekly_save.cancel()
        self.clean_sheets.cancel()
        
    #Function that takes a list of strings to print and concatenates them to a bit below the discord character limit and sends them so that messages are less spammy
    def packPrintList(self, list_of_strings,pack_limit = 1200):
        packed_list = []
        packed_string = ""
        for i in range(len(list_of_strings)):
            if(len(packed_string) < pack_limit):
                packed_string = packed_string + list_of_strings[i]
            else:
                packed_list.append(packed_string)
                packed_string = list_of_strings[i]
                
        #Get the last string (either a packed string or the last entry of list_of_strings)
        packed_list.append(packed_string)
        
        return packed_list
        
    #Commands that only the owner of the bot can run, but also that need the server_shop.
    @commands.command(name='save', hidden=True)
    @commands.is_owner()
    async def save(self,ctx):
        if(self.weekly_save.is_running()):
            self.weekly_save.restart()
            await ctx.send(f'Data Saved, timer restarted')
        else:
            self.weekly_save.start()
            await ctx.send(f'Data Saved, timer started')
            
    @commands.command(name='announce', aliases=['a'], hidden=True)
    @commands.is_owner()
    async def announce(self, ctx, msg : str):
        announcement_channel = self.bot.get_channel(self.server_shop.config['announcements'])
        await announcement_channel.send(f'{msg}')
        
    #Function to retrieve the querying customer's entire inventory and send it to them as a DM.
    #FUTURE: This is a pretty intensive command so it should be a high priority to put some kind of spam limits on the bot and maybe try to stop people calling this command more than once per hour.
    @commands.command(name='get_my_cards',aliases=['cards','mycards','cardlist'],brief='DMs customer their inventory',description='Checks the ID of the caller and returns the full inventory from the database matching that ID.')
    async def get_my_cards(self,ctx):
        customer_id = str(ctx.author.id)    
        
        #If the "Customer Inventory" sheet does not currently exist, make it
        if(self.customer_workbook is None):
            self.customer_workbook = self.gc.create("Customer Inventory")
            self.gc.insert_permission(self.customer_workbook.id,None,perm_type='anyone',role='reader') #Set the newly created spreadsheet to be readable by anyone so that we can just send the link to the sheet.
            
        #Attempt to open a sheet for the customer nickname, and if it fails, then make one.
        try:
            customer_sheet = self.customer_workbook.worksheet(self.server_shop.customers[customer_id].nickname)
        except gspread.exceptions.WorksheetNotFound:
            customer_sheet = self.customer_workbook.add_worksheet(title=self.server_shop.customers[customer_id].nickname,rows=1500,cols=3) #The row number is kind of arbitrary. I'm just gonna set it high enough it probably won't matter. If it comes up with any regularity, I'll add a function to add more rows. I assume seasons will reset before 1499 different cards.
            
        
        customer_inventory = [('Card Name','Setcode','Rarity','Quantity Owned')] #Start the list with a header row.
        customer_inventory.extend(self.server_shop.getCustomerInventory(customer_id)) #extend list with contents of player database.
        
        update_range = f"A1:D{len(customer_inventory)}"
        
        customer_sheet.update(update_range,customer_inventory)
        
        await ctx.author.send(f'Your card list can be found at the following link on the {self.server_shop.customers[customer_id].nickname} sheet.\n{self.customer_workbook.url}')
        
    #Function that queries a customer's inventory for cards with a specific name and sends it to them as a DM
    @commands.command(name='search_my_cards',aliases=['search_cards','search'],brief='Searches customer\'s inventory for the specific card name',description='Checks the ID of the caller and searches the matching database table for the requested card.')
    async def search_my_cards(self,ctx,*, arg):
        # *, arg is a special construct called "keyword-only argument" that collects everything following the command as a single argument. It also strips whitespace, but that doesn't seem to include spaces.
        customer_inventory = self.server_shop.searchCustomerInventory(str(ctx.author.id),arg)
        packed_inventory = self.packPrintList(customer_inventory)
        await ctx.author.send(f'`SET  | RARE  | #   | NAME`')
        for s in packed_inventory:
            await ctx.author.send(f'`{s}`')
            
    #FUTURE: This should probably ping the customer, not the one who calls it.
    @commands.command(name='admin_pack',aliases=['admin_open'],brief='Open a pack without checking budget',description='Allows anyone registered as an admin to bypass currency restrictions and have a pack opened in the pulls channel')
    @commands.has_any_role('Mod','Vendor')
    async def admin_pack(self, ctx, nickname : str, setcode : str, number_to_open : int = 1):
        customer_id = self.server_shop.mapNicknameToID(nickname)
        purchase = self.server_shop.makePurchase(customer_id,setcode,number_to_open,shop.Wallet.nocoin)
        #The first field of purchase indicates whether the purchase was successful
        if(purchase[0]):
            await ctx.send(f'{ctx.author.mention} Purchase successful.\n{nickname} has been given:\n')
            packed_inventory = self.packPrintList(purchase[2])
            for s in packed_inventory:
                await ctx.send(f'{ctx.author.mention}\n`{s}`')
        else:
            await ctx.send(f'{ctx.author.mention} Purchase failed because:\n{purchase[2]}')
        
    @commands.command(name='buy_product',aliases=['buy','open'],brief='Buys a specified number of a product (default 1) according to the provided inventory key.',description='Customer provides either the inventory number of a product or the setcode of a saleable pack and the shop will check whether the customer has sufficient funds, returning the list of cards if so.')
    async def buy_product(self,ctx,product_key, number_to_open : int = 1):
        pulls_channel = self.bot.get_channel(self.server_shop.config['pulls'])
        customer_id = str(ctx.author.id)
        
        purchase = self.server_shop.makePurchase(customer_id,product_key,number_to_open)
        
        #The first field of purchase indicates whether the purchase was successful
        if(purchase[0]):
            await ctx.send(f'{ctx.author.mention} Purchase successful.\nRemaining Budget: {purchase[1]}\nSee the pulls channel for your cards: \n')
            #Pack the purchase into a smaller list for less spamming.
            print_list = self.packPrintList(purchase[2])
            for s in print_list:
                await pulls_channel.send(f'{ctx.author.mention}\n`{s}`')
        else:
            await ctx.send(f'{ctx.author.mention} Purchase of {purchase[1]}$ failed because:\n{purchase[2]}')
        
    @commands.command(name='setup',brief='Setup bot in new server',description='Tells the bot to find channels by names in config and set their id\'s in the config for printing. Will only find channels whose names exactly match those in config (not case sensistive and all spaces in config are automatically replaced with "-")')
    @commands.has_any_role('Owner','Mod')
    async def setup(self, ctx):
        channels_to_find = list(self.server_shop.prices.keys())
        channels_to_find.append("announcements")
        channels_to_find.append("pulls")
        for key in channels_to_find:
            channel_name = key.replace(' ', '-').lower()
            channel = get(ctx.guild.channels, name=channel_name)
            if(channel is None):
                print(f"No channel found with name {channel_name}")
            else:
                await ctx.send(f"Found `{channel_name}` with ID: {channel.id}")
                self.server_shop.config[key] = channel.id
                
            
                
        self.server_shop.saveConfig()
                
    #Command to print inventory
    @commands.command(name='print_inventory', aliases=['inventory', 'i'],brief='Prints current inventory to the bot-inventory channel',description='Command usable only by Coders, Mods, and Vendors. Prints all product and pack entries in the database to the #bot-inventory channel' )
    @commands.has_any_role('Coder','Mod','Vendor')
    async def print_inventory(self, ctx):
        for c in self.server_shop.getAllCategories():
            inventory_channel = self.bot.get_channel(self.server_shop.config[c])
            inventory = self.server_shop.getInventoryByCategory(c)
            await inventory_channel.send(f'Product Type {c} is priced at {self.server_shop.getPriceByCategory(c)} Birdbuckz\nInventory as of {time.ctime()} is:\n\n`ID    | Product Name`\n')
        
            #Prepend ID #'s
            formatted_inventory = []
            for i in inventory:
                formatted_inventory.append(f"{str(i[0]).ljust(5)} | {i[1]}\n")
            
            #Pack inventory into fewer messages.
            formatted_inventory = self.packPrintList(formatted_inventory)
            
            for s in formatted_inventory:
                await inventory_channel.send(f"`{s}`")
        
    @commands.command(name='set_current_date', aliases=['set_date','timetravel'],brief='Sets the shop\'s current date to the provided date value.',description='Command usable only by Coders, Mods, and Vendors. Updates the current_date value and the listing of available products. Date format is yyyy-mm-dd')
    @commands.has_any_role('Coder','Mod',Vendor')
    async def set_current_date(self, ctx, target_date : str):
        try:
            new_current_date = datetime.strptime(target_date,"%Y-%m-%d")
        except ValueError:
            await ctx.send(f'Provided date: {target_date} was not understood as a valid date. The expected format is yyyy-mm-dd')
        else:
            self.server_shop.setShopDate(new_current_date)
            await ctx.send(f'[SUCCESS]: Current date now set to {self.server_shop.getCurrentDateString()}')

    @commands.command(name='deregister_player', aliases=['delete','delete_player','deregister'],brief='Deletes player entry from registry.',description='Command usable only by Coders, Mods, and Vendors. Takes the Discord ID of a registered player and permanently deletes their data.')
    @commands.has_any_role('Coder','Mod','Vendor')
    async def deregister_player(self, ctx, user_id : str):
        result = self.server_shop.deleteCustomer(user_id)
        
        #Remove player role
        role = get(ctx.guild.roles, name="Player")
        #Get the target player
        member = await ctx.guild.fetch_member(int(user_id))
        await member.remove_roles(role)
        
        await ctx.send(f'{ctx.author.mention} {result}')
        
    @commands.command(name='clear_cardlists', aliases=['clear_all'],brief='Deletes all entries from player card lists.')
    @commands.has_any_role('Mod','Vendor')
    async def clear_cardlists(self,ctx):
        if(self.server_shop.clearAllCustomerInventory()):
            await ctx.send(f'Cleared customer inventory')
        else:
            await ctx.send(f'There was an error while trying to clear customer inventory.')
    
    @commands.command(name='register_me', aliases=['register'],brief='Add yourself to the player registry.',description='Registers the caller in the player registry and sets their nickname as the first word of their name')
    async def register_me(self, ctx):
        nickname = ''.join(c for c in ctx.author.name.split(' ')[0] if c.isalnum())
        result = self.server_shop.newCustomer(str(ctx.author.id),nickname)
        
        #Add player role
        role = get(ctx.guild.roles, name="Player")
        await ctx.author.add_roles(role)
        
        await ctx.send(f'{ctx.author.mention} {result}')

    @commands.command(name='get_registered_players', aliases=['players', 'get_all_players'],brief='Gets a list of players.',description='Returns a list of nicknames for all registered players')
    @commands.has_any_role('Coder','Mod','Vendor')
    async def get_registered_players(self, ctx):
        player_list = self.server_shop.getCustomersAsList()
        
        await ctx.send(f'Currently registered players:\n')
        for p in player_list:
            await ctx.send(f'{p}')

    @commands.command(name='give_allowance', aliases=['give_budget','allowance'],brief='Gives set allowance',description='Callable only by Coders, Mods, and Vendors. Updates each player\'s budget entry with the allowance set in config.json')
    @commands.has_any_role('Coder','Mod','Vendor')
    async def give_allowance(self,ctx):
        if(self.weekly_allowance.is_running()):
            self.weekly_allowance.restart()
        else:
            self.weekly_allowance.start()
            
    
    @commands.command(name='update')
    @commands.is_owner()
    async def update(self,ctx):
        self.server_shop.updateShop()
        await ctx.send(f'{ctx.author.mention} shop update successful')
        
    @commands.command(name='set_budget',brief='Sets a customer\'s budget to the provided value',description='Callable only by Coders, Mods, and Vendors. Sets the provided player\'s budget to the provided value')
    @commands.has_any_role('Coder','Mod','Vendor')
    async def set_budget(self,ctx,nickname : str, value : float):
        id = self.server_shop.mapNicknameToID(nickname)
        self.server_shop.customers[id].setBudget(value)
        budget = str(self.server_shop.customers[id].getBudget())
        await ctx.send(f'Budget set to {budget}')
        
    @commands.command(name='add_budget',aliases=['add'], brief='Adds given amount to specified player\'s budget',description='Callable only by Coders, Mods, and Vendors. Takes two arguments, player name and amount to add. Adds amount to player\'s budget.')
    @commands.has_any_role('Coder','Mod','Vendor')
    async def add_budget(self,ctx,nickname : str, value : float):
        id = self.server_shop.mapNicknameToID(nickname)
        self.server_shop.customers[id].addMoney(value)
        budget = str(self.server_shop.customers[id].getBudget())
        await ctx.send(f'Budget now {budget}')
        
    @commands.command(name='subtract_budget',aliases=['sub','remove'], brief='Removes given amount from specified player\'s budget',description='Callable only by Coders, Mods, and Vendors. Takes two arguments, player name and amount to add. Removes amount from player\'s budget.')
    # @commands.has_any_role('Coder','Mod','Vendor')
    @commands.is_owner()
    async def subtract_budget(self,ctx,nickname : str, value : float):
        id = self.server_shop.mapNicknameToID(nickname)
        self.server_shop.customers[id].removeMoney(value)
        budget = str(self.server_shop.customers[id].getBudget())
        await ctx.send(f'Budget now {budget}')
        
    @commands.command(name='set_server_budget',brief='Sets the budget of every registered player to the provided value',description='Callable only by Coders, Mods, and Vendors. Sets every player to the given budget value and resets OTS packs to 0.')
    @commands.has_any_role('Coder','Mod','Vendor')
    async def set_server_budget(self,ctx,value : float):
        self.server_shop.setBudgetToGroup(self.server_shop.getCustomerIDs(),value)
        self.server_shop.setOTSForGroup(self.server_shop.getCustomerIDs(),0)
        await ctx.send(f'Budget for server set to {value}')
        
    @commands.command(name='get_player_budget')
    @commands.has_any_role('Coder','Mod','Vendor')
    async def get_player_budget(self,ctx,nickname : str):
        id = self.server_shop.mapNicknameToID(nickname)
        budget = str(self.server_shop.customers[id].getBudget())
        await ctx.send(f'{nickname}\'s budget is {budget}')

    @commands.command(name='get_my_budget',aliases=['budget'])
    async def get_my_budget(self,ctx):
        budget = str(self.server_shop.customers[str(ctx.author.id)].getBudget())
        await ctx.send(f'{ctx.author.mention} your budget is {budget}')
        
    @commands.command(name='award_ots',aliases=['award'],brief='Give X player Y OTS packs')
    @commands.has_any_role('Coder','Mod','Vendor')
    async def award_ots(self,ctx,nickname : str, value : int = 1):
        id = self.server_shop.mapNicknameToID(nickname)
        self.server_shop.customers[id].addOts(value)
        ots = str(self.server_shop.customers[id].getOts())
        await ctx.send(f'{nickname} now has {ots} OTS packs')
        
    @commands.command(name='set_ots',brief='Set X player\'s number of OTS packs to Y')
    @commands.has_any_role('Coder','Mod','Vendor')
    async def set_ots(self,ctx,nickname : str, value : int):
        id = self.server_shop.mapNicknameToID(nickname)
        self.server_shop.customers[id].setOts(value)
        ots = str(self.server_shop.customers[id].getOts())
        await ctx.send(f'{nickname} now has {ots} OTS packs')
        
    @commands.command(name='check_my_ots_packs',aliases=['my_ots','ots_packs'],brief='Check your own OTS pack balance')
    async def check_my_ots_packs(self,ctx):
        ots = str(self.server_shop.customers[str(ctx.author.id)].getOts())
        await ctx.send(f'{ctx.author.mention} you have {ots} OTS Packs')
        
    @commands.command(name='check_player_ots_packs',aliases=['check_ots','player_ots'],brief='Check the specified player\'s OTS pack balance')
    @commands.has_any_role('Coder','Mod','Vendor')
    async def check_player_ots_packs(self,ctx,nickname : str):
        id = self.server_shop.mapNicknameToID(nickname)
        ots = str(self.server_shop.customers[id].getOts())
        await ctx.send(f'{nickname} has {ots} OTS packs')
        
    @commands.command(name='buy_ots',aliases=['ots'],brief='Buy Y of provided OTS Setcode X')
    async def buy_ots(self,ctx,setcode : str, number_to_open : int = 1):
        pulls_channel = self.bot.get_channel(self.server_shop.config['pulls'])
        customer_id = str(ctx.author.id)
        purchase = self.server_shop.makePurchase(customer_id,setcode,number_to_open,shop.Wallet.otscoin)
        
        #The first field of purchase indicates whether the purchase was successful
        if(purchase[0]):
            await ctx.send(f'{ctx.author.mention} Purchase successful.\nRemaining OTS Packs: {purchase[1]}\nSee the pulls channel for your cards: \n')
            packed_inventory = self.packPrintList(purchase[2])
            for s in packed_inventory:
                await pulls_channel.send(f'{ctx.author.mention}\n`{s}`')
        else:
            await ctx.send(f'{ctx.author.mention} Purchase of {purchase[1]} OTS Packs failed because:\n{purchase[2]}')
        



    #TASKS
    
    
    # Repeating task to give weekly (or daily for now) allowance.
    @tasks.loop(hours=168)
    async def weekly_allowance(self):
        announcement_channel = self.bot.get_channel(self.server_shop.config['announcements'])
        self.server_shop.giveAllowance(self.server_shop.getCustomerIDs())
        await announcement_channel.send(f'Your allowance is here!')
    
    @weekly_allowance.before_loop
    async def before(self):
        await self.bot.wait_until_ready()
        print("Finished waiting to weekly_allowance")
        
    @tasks.loop(hours = 168)
    async def weekly_save(self):
        self.server_shop.saveAllCustomers()
    @weekly_save.before_loop
    async def before(self):
        await self.bot.wait_until_ready()
        print("Finished waiting to weekly_save")
        
    #After the bot is started, and every day therafter, if the "Customer Inventory" spreadsheet exists, delete it.
    #This is done to save google drive space and make sure people are getting a recent copy of their inventory.
    @tasks.loop(hours=24)
    async def clean_sheets(self):
        if(self.customer_workbook is None): #No sheet, do nothing
            pass
        else:
            #Delete the spreadsheet and set it to none
            print(f"Attempting to delete spreadsheet with ID: {self.customer_workbook.id}")
            self.gc.del_spreadsheet(self.customer_workbook.id)
            self.customer_workbook = None
    
    @clean_sheets.before_loop
    async def before(self):
        await self.bot.wait_until_ready()
        print("Finished waiting to clean_sheets")
        
#This is the entrypoint when we try to add this cog. When we load the cog, we use the name of this file, and this function gets added

def setup(bot):
    bot.add_cog(CardShopCog(bot))
    
