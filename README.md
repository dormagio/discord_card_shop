# Overview
This is a collection of python modules intended to open arbitrary trading card packs (but mostly Yu-Gi-Oh!) based on a populated local database. While the discord bot API allows a single bot instance to service multiple servers at once, the way this bot was written precludes that capability due to the way it registers the instance owner, channels to print in, and the fact that it is maintaining a database on the machine it is run on for all players. It is likely possible to make all of this work across multiple servers, but I frankly don't want to. I wrote this bot to enable me to play a sealed format as conveniently as possible with my friends and am making this repo public to allow others with a bit of python know-how to do the same. I will review PR's if anyone wants to add major features to this bot, but by-and-large I intend to maintain the database with new card sets, polish the usability as I continue to use the bot, and add occasional custom product as is appropriate for the server I run.

# Setup
This section details how to setup your instance of the bot on your machine. It is unfortunately somewhat technical, but shouldn't be too hard for anyone with an interest in Python. Step 0 is of course to clone this repo onto the machine you want to run the bot from.

## Requirements
### Software
- [Discord](https://discordpy.readthedocs.io/en/stable/intro.html) Python module installed
- [Discord Bot Account](https://discord.com/developers/docs/getting-started) made
- [gspread](https://docs.gspread.org/en/latest/oauth2.html) Python module installed and google service account made

### Discord Server
I believe the spelling/capitalization is important for all roles and channels
- "Player" role
- "Mod" role
- "announcements" channel
- "pulls" channel
- Channel for each product type in `prices_template.json` (discord channels are all lower case and spaces are replaced with "-" so the channel for "Legacy Special Edition" would be "legacy-special-edition"
### Discord Bot Permissions
 The bot requires the following permissions (I could be missing some, I was pretty permissive with my instance while developing)
- Manage Roles
- Read Message History
- Read Messages
- Send Messages
- Mention @everyone, @here, and All Roles

Aside from the "Player" role, you are free to use any channel names you like, but the bot will not automatically find them and you will have to manually populate the config.json with channel ids (channel/user id's are not visible till you turn on developer mode for discord). If you want to, you can just make one inventory channel and copy the channel ID to that for every product type, this is just how my server wanted things to look.

### General Knowledge
The following topics aren't strictly necessary to understand for running this bot but would be helpful to brush up on if you want to dig into the source code more:
- JSON
- SQLite
- Google Sheets API
- Discord Server Moderation
- Discord Developer API's

##Steps

### 1. Populate Templates
For each of the json files in the /templates folder you will need to copy it over to the /configs folder and remove the "_template" part of the name. While editing, it is important not to remove or change any of the key values (the part in quotes for those unfamiliar with JSON) as all of them are required for the bot to function.
 
#### config.json
As long as you follow the requirements listed for your discord server, most of config.json should be auto-populated. This file is loaded when the bot starts and is used to determine which channel to print things to. It also contains important keys that you MUST populate and keep private. The ones you need to populate are as follows:
- "token": The token that the discord bot guide gives you.
- "owner": Some functionality is locked to just the owner of the bot so fill this in with the Discord ID of your mod account.

The following are optional fields you can change if you want
- "allowance": The amount of server currency to be distributed every week. You don't need to change it from 40 but you can.
- "Starting Budget": The amount that a newly registered player will recieve upon joining the server. Generally the same as allowance but you may want to give people a head start

The "shop_database" and "inventory_database" fields are probably best left alone. By default they point to the database folder assuming the bot is run from the root of the repo. They are only in config to help with development. If you do change this it is likely going to be to make copies of the databases with different names for special events.

#### prices.jon
The prices.json file can likely be left alone unless you want to change the pricing of any of the products. This is loaded when the bot is started and sets the price for each category of product that is saleable in the bot. It is also used to determine which categories of inventory will be printed to your discord server. OTS packs are set to 999 as they cannot actually be bought with normal currency and have their own private currency.

#### service_account.json
This file comes directly from the gspread api and the template file is only there to remind you to handle this. The guide in requirements should walk you through how to get it, but essentially this is a generated json file that has your confidential account information for your google sheets account. Don't share it with anyone, but this is required for the discord bot to nicely print out people's card lists.

#### shop.db
This is just a blank database with all the necessary tables created and empty. Copy-paste this to /database and rename it.

### 2. Running the Bot
After installing/setting up the required accounts and python modules, you will need to add the discord_card_shop/src/ folder to your PYTHONPATH environment variable (define it if it is not already defined.) This will enable python3 to find the custom modules in this repo and traverse the hierarchy correctly. There is probably a way to package this correctly but I don't know it. Once you have done this, navigate to the root repo and run `vendorbot.py`. This will probably look something like `python3 ./vendorbot.py` or `py3 vendorbot.py`.

### 3. Setting up on the server.
Assuming you have populated the provided config files correctly, you should be able to follow the developer guides to add your bot to your server with the appropriate permissions and use the `setup` command. I didn't make any clever command for changing the command prefix so if you don't want it to be `?` you'll have to change it in `vendorbot.py`. Type `?help` to get a list of a available commands. Setup should let you know which channels it has found and populated and if it found any errors. Once you are sure that all channel ID's have been populated, type `?inventory` to print the inventory of the bot, alongside prices to your setup channels. After that, you more or less have free reign. The next section will cover some basics on how the bot is expecting to be used, but I'm almost certainly leaving out details.

# Running A Sealed Server.
You can run a sealed server any way you like, I'm not your parent, but I'll give you a few tips from experience. If you have watched a YouTuber do a weekly sealed challenge you should be broadly familiar with how this works. Play is split into "seasons" where you build up decks from scratch, and reset your cardlist at the end. So far 12 weeks has been a pretty good length for a season as it gives everyone plenty of time to build most strategies, even with bad pulls, but doesn't last long enough for the lucky to run out of cards to pull. You can extend it a few more weeks if you like, but we tried up to 24 weeks and that saw participation dropoff as decks plateaued and locals stagnated. At the start of every week, people get their weekly budget to pull cards and build decks, then at the end of the week we host a locals tournament on one of the simulators for everyone to play in. I give everyone who participates one OTS token that they can use to purchase any OTS pack that has been released then give additional packs to each of the top 3 finalists (3 for 1st, 2 for 2nd, 1 for 3rd). It is nice to have a little motiviation to show up and play. At the end of locals I use the `?allowance` command to give the server their weekly budget. This command starts a 1 week timer but it is nice for everyone to get their money while everyone is still actively hanging around and subsequent calls to the command reset the timer. How you organize the tournament is up to you but I generally require everyone to post a screenshot of their decklist before joining and use discord events to handle signup and scheduling.

AS AN FYI, WHEN A PLAYER REGISTERS, THE BOT WILL TRUNCATE THEIR NICKNAME AND SAVE IT IN THE DATABASE. IT WILL ALWAYS USE THEIR UNCHANGING DISCORD ID TO AFFECT THEIR ACCOUNT, BUT A LOT OF COMMANDS USE THE STORED NICKNAME FOR CONVENIENCE SO MAKE SURE NOBODY CHANGES THEIR NICKNAME PAST RECOGNIZABILITY.

## Mod Commands
This section will go over a few of the most important mod commands. There are plenty more, but hopefully the rest are clear from their name + description or won't be needed. Most of these commands have multiple aliases and I may end up flip-flopping between their given name and alias according to whatever I usually type. All of these also are restricted to a "Coder", "Mod", or "Vendor" role. You can probably just use the "Mod" role, but you may wish to assign yourself the "Vendor" role. The "Coder" role is unecessary but it was used during development and is only mentioned so you don't accidentally give anyone permissions.

- `allowance`: This command updates every registered player's account with the allowance amount from config.json. It also starts a 1 week timer that gets reset if you call this command again
- `save`: This command makes sure all customer data is saved back to the database. It is best to run this before taking down the bot for any reason. It also starts a 1 week timer.
- `print_inventory`: This command prints inventory to all the channels registered with config.json. You'll want to use this if/when you pull in inventory updates from the repo.
- `deregister_player`: This command uses a person's discord ID to remove them from the server and remove their "Player" role from the server. 
- `get_registered_players`: This command will print out a list of all the nicknames the bot has registered. Some commands take a nickname and looks up the associated player's Discord ID and this is how you can find out what nicknames it knows.
- `award_ots`: Adds OTS Tokens to the given player. When called without a number it just adds 1.
- `set_server_budget`: Sets every registered player's budget to the same value and clears every player's OTS budget. Generally intended to be used to reset the season
- `clear_cardlists`: Empties every player's cardlist in preparation for a new season
- `admin_pack`: This command is used to open any type of pack in the bot and add the contents to a player's list. Can be used to award free packs if you want. Hopefully nobody but me will need to use it to give packs when product breaks. Importantly, this command can be used to open packs that are normally only available as part of other product, like Mega Packs. Use with care, I do not provide any warranty on this.

## Player commands
There's also a lot of player commands and hopefully the vast majority are clear by name + description. They almost all have shorter aliases you can use instead of my very_clear_function_names. The only ones I'll mention here are `?register`, `?cards`, and `?search`. 
- `register` adds an entry in `shop.db` for the player that types it, truncates their nickname, and gives them the starting budget and "Player" role on your server.
- `cards` will query `shop.db` and add a tab to a google spreadsheet using the player's nickname for the tab name. The generated spreadsheet is deleted daily so as not to use up google drive space. If players want to edit the sheet, they will have to copy the tab to their own sheet. The link to this spreadsheet will be DM'd to the calling player.
- `search` allows players to query their card list for card names. It uses sqlite3 searching to approximately match whatever they type and return all the cards they have in a DM.

#GA Release Notes
1. Currently, Hidden Arsenal Chapter 1 does not work and the set isn't good enough that I feel like fixing it right now.
2. There are some rate limiting problems on the google sheets api implementation as it was implemented in a hurry. Suitable for small scale (10 or so) servers, unsure about broader implications
3. The pack class converts elements of the pool from string to int every time an object is made. Need to look into storing them in the database as ints in the first place somehow.
4. Currently, customers are loaded from the database and managed separately then saved back when the save() method is called. There is a lot of latent translation stuff lingering from before the database api was added that could be cleaned up using the database.
5. Currently, discord_card_shop/src/ needs to be added to PYTHONPATH for this bot to work. Need to investigate installing modules for future releases.
6. The bot does not have enough countermeasures to spam, especially for things like the gspread api. This has so far not been a problem in a personal server but the bot needs to be hardened for a widescale deployment.
7. Decks in database don't register correct quantities since they are only lists of unique setcodes. This limitation can be manually worked around, but it is labor intensive for minimal value since all deck quantities are easily found elsewhere.
8. When a player is deregistered, the active google sheet will still have them. And if they reregister and request a list with fewer cards, the old cards won't be fully deleted. Maybe deregister should have a sheets API call? This is a pretty niche edge case so it isn't scheduled to be addressed anytime soon.
9. Dragons of Legend: The Complete Series, Legendary Duelists Season 1, and Legendary Duelists Season 2 report their promos as Super Rare when they should be secret rare because they use the same code as special editions. This is easily identifiable as incorrect and not currently slated for fixing.
10. I saw some issue with live updates to the shop inventory not being reflected without fully rebooting the bot, but I don't honestly want to take the time to figure it out since this whole bot only functionally connects to one server at a time anyway.
11. The setup command will handle channel ids for the inventory, announcement, and pulls channels, but other aspects of the config will have to be edited manually. The requirement for a discord bot token and discord owner id somewhat necessitates a comfort with JSON sadly.
12. The Dinosmasher's Fury structure deck is in the database but has been made unavailable as it was deemed that it just wasn't fun for people to be able to buy early in a season and all the core cards are available in Maximum Gold: El Dorado now. If you want to re-enable it for your own server, just change the database entry in inventory.db to mark the product type as Deck again.

# Planned Improvements
1. Implement JSON Schemas for config jsons.
2. Update README with a generic how-to-play section to paste into a discord channel for your players.