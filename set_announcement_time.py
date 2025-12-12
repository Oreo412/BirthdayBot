import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
from aiosqlite import DatabaseError
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import asyncio
import logging

logger = logging.getLogger('birthday_logger')

class set_announcement_time(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bdcon = bot.bdcon
        self.bot.time_configure_view = time_configure_view
        self.bot.send_time_configure = send_time_configure
        self.bot.send_tconfig_in_birthdays = send_tconfig_in_birthdays

    @app_commands.command(name="configtime", description = "Test the Time View")
    async def timeviewtest(self, interaction):
        await send_time_configure(channel = interaction.channel, interaction = interaction)

    async def db_update(self, hour: int, minute: int, pm: bool, tz: str, guild_id: int):
        try:
            await self.bdcon.execute("UPDATE guilds SET announcement_time = ?, timezone = ? WHERE gui ?", f"{hour}:{minute}", tz, guild_id)
            await self.bdcon.commit()
        except DatabaseError as e:
            logger.exception("Failed to update announcement time in DB")
            await self.bdcon.rollback()

        
class tzModal(discord.ui.Modal, title = "Input Timezone"):

    def __init__(self, hour: int, minute: int, pm: bool):
        super().__init__()
        self.hour = hour
        self.minute = minute
        self.pm = pm

    tz = discord.ui.TextInput(label = "Timezone: ", placeholder = "paste timezone here", style = discord.TextStyle.short, required = True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ZoneInfo(self.tz.value)
            await interaction.client.bdcon.execute("UPDATE guilds SET announcement_hour = ?, announcement_minute = ?, timezone = ?, pm = ? WHERE guild_id = ?", (self.hour, self.minute, self.tz.value, self.pm, interaction.guild_id))
            await interaction.client.bdcon.commit()
            message_scheduler = interaction.client.get_cog("message_scheduler")
            message_scheduler.schedule_guild_message(guild_id = interaction.guild_id, channel_id = interaction.channel_id, hour = self.hour, minute = self.minute, pm = self.pm, timezone = self.tz.value)
            await interaction.response.defer()
            await interaction.channel.send(content = f"Set announcement time to {str(self.hour).zfill(2)}:{str(self.minute).zfill(2)} {"PM" if self.pm else "AM"} in the {self.tz.value} timezone!")
            button_pin_id = await (await interaction.client.bdcon.execute("SELECT button_pin_id FROM guilds WHERE guild_id = ?", (interaction.guild_id,))).fetchone()
            if not button_pin_id[0]:
                await interaction.client.create_input_pin(interaction.channel, interaction.client)
        except ZoneInfoNotFoundError: 
            await interaction.message.edit(embed = discord.Embed(color = discord.Color.red(), title = "Try Again", description = "Please paste a valid timezone"))
            await interaction.response.defer()
        except DatabaseError:
            logger.exception("DB failure in on_submit")
            await interaction.client.bdcon.rollback()
        except Exception as e:
            await interaction.channel.send("Something went wrong")
            await interaction.response.defer()
            await interaction.client.bdcon.rollback()
            logger.exception("on_submit failure")
    
        
class hourView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout = None)
        for i in range(1, 13):
            btn = discord.ui.Button(label = str(i), style = discord.ButtonStyle.secondary, row = ((i-1)//4))
            btn.callback = make_hour_callback(i)
            self.add_item(btn)

def make_hour_callback(hour):
    async def hour_callback(interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.edit(content = f"Set Minute\nSet Time: {str(hour).zfill(2)}:MM", view = minuteView(hour = hour))
    return hour_callback

class minuteView(discord.ui.View):
    def __init__(self, hour: int):
        super().__init__(timeout = None)
        self.hour = hour
        for i in range(0, 60, 5):
            btn = discord.ui.Button(label = str(i).zfill(2), style = discord.ButtonStyle.secondary, row = i//20)
            btn.callback = make_minute_callback(i, hour)
            self.add_item(btn)
        back_button = discord.ui.Button(style = discord.ButtonStyle.danger, label = "Go back", row = 4)        
        back_button.callback = self.goBack
        self.add_item(back_button)

    async def goBack(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.edit(content = "Select Hour:", view = hourView())


def make_minute_callback(minute, hour):
    async def minute_callback(interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.edit(content = f"PM\nSet Time: {str(hour).zfill(2)}:{str(minute).zfill(2)}", view = (amOrPm(hour = hour, minute = minute)))
    return minute_callback

class amOrPm(discord.ui.View):
    def __init__(self, minute, hour):
        super().__init__(timeout = None)
        self.hour = hour
        self.minute = minute
        AM = discord.ui.Button(style = discord.ButtonStyle.primary, label = "AM", row = 0)
        AM.callback = self.am_callback
        PM = discord.ui.Button(style = discord.ButtonStyle.primary, label = "PM", row = 0)
        PM.callback = self.pm_callback
        self.add_item(AM)
        self.add_item(PM)
        back_button = discord.ui.Button(style = discord.ButtonStyle.danger, label = "Go back", row = 2)        
        back_button.callback = self.goBack
        self.add_item(back_button)

    async def am_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.edit(content = f"Select Timezone\n Set Time: {str(self.hour).zfill(2)}:{str(self.minute).zfill(2)} AM", view = tzLinkView(hour = self.hour, minute = self.minute, pm = False))

    async def pm_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.edit(content = f"Select Timezone\n Set Time: {str(self.hour).zfill(2)}:{str(self.minute).zfill(2)} PM", view = tzLinkView(hour = self.hour, minute = self.minute, pm = True))

    async def goBack(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.edit(content = f"Set Minute\nSet Time: {str(self.hour).zfill(2)}:MM", view = minuteView(hour = self.hour))

        

class tzLinkView(discord.ui.View):
    def __init__(self, hour: int, minute: int, pm: bool):
        super().__init__(timeout = None)
        self.hour = hour
        self.minute = minute
        self.pm = pm
        open_tz_button = discord.ui.Button(style = discord.ButtonStyle.primary, label = "Paste Timezone", row = 1, custom_id = "TZ Modal Select")
        open_tz_button.callback = self.openTzModal
        self.add_item(discord.ui.Button(style = discord.ButtonStyle.link, url = "https://zones.arilyn.cc", label = "Timezone Link", row = 1))
        self.add_item(open_tz_button)
        back_button = discord.ui.Button(style = discord.ButtonStyle.danger, label = "Go back", row = 2)        
        back_button.callback = self.goBack
        self.add_item(back_button)

    async def openTzModal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(tzModal(hour = self.hour, minute = self.minute, pm = self.pm))
    
    async def goBack(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.edit(content = f"PM\nSet Time: {str(self.hour).zfill(2)}:{str(self.minute).zfill(2)}", view = amOrPm(hour = self.hour, minute = self.minute))
    
class time_configure_view(discord.ui.View):
    def __init__(self, bdcon: aiosqlite.Connection, guild_id: int, message: discord.Message):
        super().__init__(timeout = None)
        self.container = discord.ui.Container()
        self.message = message
        self.bdcon = bdcon
        self.guild_id = guild_id
        configure_btn = discord.ui.Button(style = discord.ButtonStyle.primary, label = "Configure", row = 1)
        cancel_btn = discord.ui.Button(style = discord.ButtonStyle.danger, label = "Cancel", row = 1)
        configure_btn.callback = self.configure_callback
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)
        self.add_item(configure_btn)
        

    
    async def change_message(self):
        try:
            row = await (await self.bdcon.execute(
                "SELECT announcement_hour, announcement_minute, timezone, pm FROM guilds WHERE guild_id = ?",
                (self.guild_id,)
            )).fetchone()

            if not row:
                await self.message.edit(content="No announcement time or timezone configured. Would you like to configure it?")
                return

            hour, minute, timezone, pm = row
            if hour is not None and minute is not None and timezone:
                display_hour = (int(hour) - 12) if pm and int(hour) > 12 else int(hour)
                await self.message.edit(content=f"Announcement Time and Timezone set to {display_hour:02d}:{int(minute):02d} {'PM' if pm else 'AM'}, {timezone} time. Would you like to edit it?")
            else:
                await self.message.edit(content="No announcement time or timezone configured. Would you like to configure it?")
        except DatabaseError as e:
            logger.exception("Failed to read DB in change_message")
            await self.message.edit("Error: ")
        except Exception as e:
            logger.exception("change_message task failed")
            await self.message.edit("Error: ")

        
    

    async def configure_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(content = "Current set Time: HH:MM\nInput hour:", view = hourView())
    
    async def cancel_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.message.delete()

async def send_time_configure(channel: discord.TextChannel, interaction: discord.Interaction):
    try:
        await interaction.response.send_message(content = "loading...")
        time_configure_message = await interaction.original_response()
        tconfig_view = time_configure_view(bdcon = interaction.client.bdcon, guild_id = interaction.guild_id, message = time_configure_message)
        await time_configure_message.edit(content = "loading...", view = tconfig_view)
        await tconfig_view.change_message()
        return time_configure_message
    except Exception as e:
        logger.exception("send_time_configure failure")

async def send_tconfig_in_birthdays(channel: discord.TextChannel, interaction: discord.Interaction):
    try:
        tconfig_message = await channel.send(content = "loading...")
        tconfig_view = time_configure_view(bdcon = interaction.client.bdcon, guild_id = interaction.guild_id, message = tconfig_message)
        await tconfig_message.edit(content = "loading...", view = tconfig_view)
        await tconfig_view.change_message()
        return tconfig_message
    except Exception as e:
        logger.exception("send_time_configure failure")

async def setup(bot):
    await bot.add_cog(set_announcement_time(bot))