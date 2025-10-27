import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
import traceback
from apscheduler.schedulers.background import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

class message_scheduler(commands.Cog):
    def __init__(self, client, bdcon):
        self.client = client
        self.bdcon = bdcon
        self.scheduler = AsyncIOScheduler()
        self.scheduler.start()
        self.guild_scheduler.start()

    def cog_unload(self):
        self.guild_scheduler.cancel()
        self.scheduler.shutdown(wait = False)

    @tasks.loop(hours = 24)
    async def guild_scheduler(self):
        guild_times = await (await self.bdcon.execute("SELECT guild_id, birthday_channel_id, announcement_time, timezone FROM guilds")).fetchall()
        for guild_id, birthday_channel_id, announcement_time, timezone in guild_times:
            hour, minute = map(int, announcement_time.split(":"))
            tz = ZoneInfo(timezone)
            run_on = datetime.now(tz).replace(hour = hour, minute = minute, second = 0, microsecond = 0)
            if run_on < datetime.now(tz):
                run_on += timedelta(days = 1)
            trigger = DateTrigger(run_date = run_on.astimezone.utc)
            job_id = f"announce_{guild_id}"
            self.scheduler.add_job(func = self.guild_messages, trigger = trigger, args = [guild_id, birthday_channel_id, tz], misfire_grace_time= 3600, id=job_id, replace_existing=True, coalesce=True)
            

    async def guild_messages(self, guild_id, birthday_channel_id, tz):
        now = datetime.now(tz)
        day = now.day
        month = now.month
        birthdays = await (await self.bdcon.execute("SELECT member_id, year FROM birthdays WHERE guild_id = ? AND day = ? AND month = ?", (guild_id, day, month))).fetchall()
        for member_id, year in birthdays:
            age_text = f" They are turning {now.year - year} years old!" if year else ""
            message = f"Today is <@{member_id}>'s birthday!{age_text} 🎉 Happy Birthday!"
            await (await self.client.fetch_channel(birthday_channel_id)).send(content = message)