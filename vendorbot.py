#!/usr/bin/env python3

import discord
from discord.ext import commands
import json #Used to read the config file for the token.

#Real bearbones bot for now. Hopefully should suffice while this is a personal project.

#Basing a lot of this on: EvieePy's example

description = 'A bot designed to open Yu-Gi-Oh! packs for dweebs'
bot = commands.Bot(command_prefix='?', description=description)

#Load our Extensions(cogs)
initial_extensions = ['cogs.cardshopcog', 'cogs.admin']

if __name__ == '__main__':
    for extension in initial_extensions:
        bot.load_extension(extension)

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('----------')
    
bot.owner_id = bot.get_cog('CardShopCog').server_shop.config["owner"]
bot.run(bot.get_cog('CardShopCog').server_shop.config["token"], bot=True, reconnect=True)