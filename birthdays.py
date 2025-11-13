import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
from aiosqlite import DatabaseError
import traceback
from datetime import datetime
import calendar
import logging

months = [
            discord.SelectOption(
                label="January",
                value=1
            ),
            discord.SelectOption(
                label="Febuary",
                value=2
            ),
            discord.SelectOption(
                label="March",
                value=3
            ),
            discord.SelectOption(
                label="April",
                value=4
            ),
            discord.SelectOption(
                label="May",
                value=5
            ),
            discord.SelectOption(
                label="June",
                value=6
            ),
            discord.SelectOption(
                label="July",
                value=7
            ),
            discord.SelectOption(
                label="August",
                value=8
            ),
            discord.SelectOption(
                label="September",
                value=9
            ),
            discord.SelectOption(
                label="October",
                value=10
            ),
            discord.SelectOption(
                label="November",
                value=11
            ),
            discord.SelectOption(
                label="December",
                value=12
            )
        ]
DAYS_IN_MONTH = (31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

logger = logging.getLogger('birthdaylogger')

class birthdays(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bdcon = bot.bdcon
        self.bot.BirthdayView = BirthdayView
    

class BdayModal(discord.ui.Modal, title = "Input Birthday"):
    month = discord.ui.Label(
        text = 'Month',
        component = discord.ui.Select(
            placeholder = "Select Birth Month",
            min_values = 1,
            max_values = 1,
            required = True,
            options = months
        )
    )
    day = discord.ui.TextInput(label = "Input Birth Day", style = discord.TextStyle.short, placeholder = "Day", required = True, max_length=2)
    year = discord.ui.TextInput(label = "(Optional) Input Birth Year", style = discord.TextStyle.short, placeholder = "Year", required = False, max_length = 4)
    async def on_submit(self, interaction: discord.Interaction):
        month = int(self.month.component.values[0])
        day = None
        year = ""
        try:
            day = int(self.day.value)
        except ValueError:
            await interaction.response.send_message(f"Please input day as a valid number", view=ErrorView(), ephemeral=True)
            return
        
        if self.year.value != "":
            try:
                year = int(self.year.value)
            except ValueError:
                await interaction.response.send_message("Please input year as a valid number", view=ErrorView(), ephemeral=True)
                return
        
        if not (1 <= day <= DAYS_IN_MONTH[month-1]):
            await interaction.response.send_message(f"Please input a day between 1 and {DAYS_IN_MONTH[month-1]}", view=ErrorView(), ephemeral=True)
            return
        
        if year  != "" and not (datetime.now().year - 100 < year < datetime.now().year):
            await interaction.response.send_message("Please input a valid year", view=ErrorView(), ephemeral=True)
            return
        if year != "" and year % 4 != 0 and day == 29:
            await interaction.response.send_message("You think you're funny don't you", view=ErrorView(), ephemeral=True)
            return
        
        await interaction.response.send_message(f"Your birthday has been set to {calendar.month_name[month]} {day} {year}!", ephemeral=True)
        try:
            await interaction.client.bdcon.execute("INSERT OR REPLACE INTO birthdays (guild_id, member_id, month, day, year) VALUES (?, ?, ?, ?, ?)", (interaction.guild_id, interaction.user.id, month, day, None if not year or str(year).strip() in ('0', '') else year))
            await interaction.client.bdcon.commit()
        except DatabaseError as e:
            logger.exception("Failed to insert birthday into birthdays table")
            await interaction.client.bdcon.rollback()
        await interaction.client.UpdatePin(interaction)

class ErrorView(discord.ui.View):
    @discord.ui.button(style = discord.ButtonStyle.danger, label = "Try Again")
    async def callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BdayModal())

class BirthdayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout = None)
    @discord.ui.button(style = discord.ButtonStyle.primary, label = "Input or Update your Birthday!", custom_id = "BirthdayButton")
    async def callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BdayModal())



async def setup(bot):
    await bot.add_cog(birthdays(bot))