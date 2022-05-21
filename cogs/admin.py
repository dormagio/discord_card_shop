import discord
from discord.ext import commands, tasks

class Admin(commands.Cog):

    def __init__(self,bot):
        self.bot = bot
        
    @commands.command(name='reload', hidden=True)
    @commands.is_owner()
    async def _reload(self, ctx, module):
        try:
            self.bot.reload_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')
    
    @commands.command(name='load', hidden=True)
    @commands.is_owner()
    async def _load(self, ctx, module):
        try:
            self.bot.load_extension(module)
        except commands.ExtensionError as e:
            await ctx.send(f'{e.__class__.__name__}: {e}')
        else:
            await ctx.send('\N{OK HAND SIGN}')
            
    @commands.command(name='execute_order_66',aliases=['order'])
    @commands.is_owner()
    async def confirm(self,ctx):
        await ctx.send(f'Affirmative')
        

def setup(bot):
    bot.add_cog(Admin(bot))