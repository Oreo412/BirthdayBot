import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
from aiosqlite import DatabaseError
import traceback

class configure_birthdays(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bdcon = bot.bdcon
    
    @app_commands.command(name = "configurebirthdays", description = "Configure the birthday bot and channel")
    async def configurebirthdays(self, interaction):
        birthdays_channel = next((channel for channel in interaction.guild.channels if channel.name.casefold() == "birthdays".casefold()), None)
        if birthdays_channel:
            await interaction.response.send_message(view = ConfigureInBirthdaysView(birthdays_channel), content = "Birthdays channel found! Would you like to configure the bot there?")
        else: 
            await interaction.response.send_message(view = ConfigureView(), content = "No birthdays channel found. Would you like to create one or configure in a separate channel?")

    
    
class ConfigureInBirthdaysView(discord.ui.View):
    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel

    @discord.ui.button(style = discord.ButtonStyle.primary, label = "Configure Birthdays In Birthdays Channel")
    async def in_channel_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        time_configure_message = await self.channel.send(content = "loading...")
        await interaction.response.send_message(content = "Birthdays Channel Configured!")
    @discord.ui.button(style = discord.ButtonStyle.secondary, label = "Configure Another Channel as Birthdays Channel")
    async def another_channel_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SelectBirthdayChannelModal())

class SelectBirthdayChannelModal(discord.ui.Modal, title = "Select Channel"):
    channel = discord.ui.Label(
        text = 'Select Channel For Birthdays',
        component = discord.ui.ChannelSelect(channel_types = [discord.ChannelType.text])
    )
    async def on_submit(self, interaction: discord.Interaction):
        channel = await interaction.client.fetch_channel(self.channel.component.values[0])
        await interaction.client.send_time_configure(channel = channel, interaction = interaction)
        await interaction.response.send_message(content = f"Configured birthdays in {channel.name}")
        await interaction.message.delete()

class ConfigureView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout = 180)
    @discord.ui.button(style = discord.ButtonStyle.primary, label = "Create a Birthday Channel", custom_id = "CreateChannelButton")
    async def create_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if(interaction.permissions.administrator == True):
            birthday_channel = await interaction.guild.create_text_channel("Birthdays")
            await interaction.client.send_time_configure(channel = birthday_channel, interaction = interaction)
            await interaction.channel.send("Channel created and configured!")
            await interaction.message.delete()
            await interaction.response.defer()
        else:
            await interaction.response.send_message(content = "You must have admin permission", ephemeral = True)
    
    @discord.ui.button(style = discord.ButtonStyle.secondary, label = "Select a Different Channel", custom_id = "SelectDifferentChannel")
    async def select_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if(interaction.permissions.administrator == True):
            await interaction.response.send_modal(SelectBirthdayChannelModal())
        else:
            interaction.response.send_message(content = "You must have admin permission", ephemeral = True)


async def setup(bot):
    await bot.add_cog(configure_birthdays(bot))