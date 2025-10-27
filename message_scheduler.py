import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
from aiosqlite import DatabaseError
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger("birthday_logger")

class message_scheduler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bdcon = self.bot.bdcon
        self.scheduler = AsyncIOScheduler()
        bot.schedule_guild_message = self.schedule_guild_message

    async def cog_load(self):
        self.scheduler.start()

    def cog_unload(self):
        self.scheduler.shutdown(wait = False)

    def schedule_guild_message(self, guild_id: int, channel_id: int, hour: int, minute: int, pm: bool, timezone: str):
        try:
            tz = ZoneInfo(timezone)
            if pm:
                hour += 12
            trigger = CronTrigger(hour = hour, minute = minute, timezone = tz)
            self.scheduler.add_job(func = self.guild_messages, trigger = trigger, args = [guild_id, channel_id, tz], misfire_grace_time = 3600, id = f"schedule_for_{guild_id}", replace_existing=True, coalesce = True)
            print(f"Guild: {guild_id} successfully scheduled!")
        except ZoneInfoNotFoundError as e:
            logger.exception("Non conforming timezone key passed to scheduler")
        except Exception as e:
            logger.exception(f"Guild {guild_id} scheduling has failed")

    async def guild_messages(self, guild_id, birthday_channel_id, tz):
        try:
            now = datetime.now(tz)
            day = now.day
            month = now.month
            birthday_channel = await self.bot.fetch_channel(birthday_channel_id)
            birthdays = await (await self.bdcon.execute("SELECT member_id, year FROM birthdays WHERE guild_id = ? AND day = ? AND month = ?", (guild_id, day, month))).fetchall()
            for member_id, year in birthdays:
                age_text = f" They are turning {now.year - int(year)} years old!" if year is not None else ""
                message = f"Today is <@{member_id}>'s birthday!{age_text} 🎉 Happy Birthday!"
                await birthday_channel.send(content = message)
        except DatabaseError as e:
            logger.exception("Failed to read DB when sending happy birthday messages")
        except Exception as e:
            logger.exception(f"Guild {guild_id} messaging has failed")



async def setup(bot):
    await bot.add_cog(message_scheduler(bot))