# This example requires the 'message_content' intent.

import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiosqlite
from aiosqlite import DatabaseError
import traceback
from dotenv import load_dotenv
import os
from datetime import datetime
import calendar
import logging



intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix=commands.when_mentioned_or("."), intents=intents)

logger = logging.getLogger('birthdaylogger')


os.makedirs("logs", exist_ok=True)

discord_log_handler = logging.FileHandler('logs/discord.log', encoding="utf-8", mode="w")
birthday_log_handler = logging.FileHandler('logs/birthdays.log', encoding="utf-8", mode = "w")
birthday_log_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] %(funcName)s %(name)s: %(message)s"
)

birthday_log_handler.setFormatter(formatter)
logger.addHandler(birthday_log_handler)


load_dotenv()

bot.bdcon: aiosqlite.Connection = None  #bdcon = birthday connection. db and con are cringe

async def setup_hook():
    bot.bdcon = await aiosqlite.connect("database/birthdays.db")
    await bot.load_extension("set_announcement_time")
    await bot.load_extension("message_scheduler")
    await bot.load_extension("configure_birthdays")
    await bot.load_extension("birthdays")
    bot.add_view(bot.BirthdayView())

@bot.event
async def on_ready():
    
    try:
        await bot.bdcon.executescript("""
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS birthdays (
                guild_id int NOT NULL,
                member_id int NOT NULL,
                month int NOT NULL,
                day int NOT NULL,
                year int,
                PRIMARY KEY (guild_id, member_id)
            );
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id int NOT NULL,
                birthday_channel_id,
                button_pin_id int,
                list_pin_id int,
                announcement_hour int,
                announcement_minute int,
                timezone TEXT,
                pm boolean,
                PRIMARY KEY (guild_id)
            );
        """)
        await bot.bdcon.commit()
        for g in bot.guilds:
            bot.tree.copy_global_to(guild=g)
            await bot.tree.sync(guild=g)
            print("Should have configured on: ", g.id)
        await guilds_update()
        (f'We have logged in as {bot.user}')
    except aiosqlite.DatabaseError as e:
        logger.exception("DB init failed: ")
    except Exception as e:
        logger.exception("On Ready failed: ")
        
async def get_guild_ids():
    try:
        async with bot.bdcon.execute("SELECT guild_id FROM guilds") as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}
    except DatabaseError as e:
        logger.exception("DB Failure:")
        await bot.bdcon.rollback()
    except Exception as e:
        logger.exception("get_guild_id failure:")
        await bot.bdcon.rollback()


async def guilds_update():
    db_guild_ids = await get_guild_ids()
    bot_guild_ids = {guild.id for guild in bot.guilds}
    removed_guilds = db_guild_ids - bot_guild_ids
    added_guilds = bot_guild_ids - db_guild_ids
    try:
        await bot.bdcon.execute("BEGIN")
        await bot.bdcon.executemany("DELETE FROM guilds WHERE guild_id = ?;",((gid,) for gid in removed_guilds))
        await bot.bdcon.executemany("DELETE FROM birthdays WHERE guild_id = ?;", ((gid,) for gid in removed_guilds))
        await bot.bdcon.executemany("INSERT OR IGNORE INTO guilds (guild_id) VALUES (?)", ((gid,) for gid in added_guilds))
        await bot.bdcon.commit()
    except DatabaseError as e:
        logger.exception("DB failure in guilds_update")
        await bot.bdcon.rollback()
    except Exception as e: 
        logger.exception("guilds_update failure")
        await bot.bdcon.rollback()
    

async def members_update():
    try:
        await bot.bdcon.executemany("BEGIN")
        for guild in bot.guilds:
            guild_members = {mem.id async for mem in guild.fetch_members(limit = None)}
            async with bot.bdcon.execute("SELECT member_id FROM birthdays WHERE guild_id = ?", (guild.id,)) as cursor:
                db_members = {row[0] for row in (await cursor.fetchall())}
                removed_members = db_members - guild_members
                await bot.bdcon.executemany("DELETE FROM birthdays WHERE member_id = ? AND guild_id = ?", ((mid, guild.id) for mid in removed_members))
        await bot.bdcon.commit()
    except DatabaseError as e:
        logger.exception("DB failure in members_update")
        await bot.bdcon.rollback()
    except Exception as e:
        logger.exception("members_update failure")
        await bot.bdcon.rollback()

    
async def schedule_on_startup():
    try:
        rows = await (await bot.bdcon.execute("SELECT guild_id, channel_id, hour, minute, pm, timezone FROM guilds")).fetchall()
        for guild_id, channel_id, hour, minute, pm, timezone in rows:
            if channel_id and hour and minute and timezone:
                bot.schedule_guild_message(guild_id = guild_id, channel_id = channel_id, hour = hour, minute = minute, pm = pm, timezone = timezone)
        logger.log("Scheduler supposedly successful on startup")
    except DatabaseError as e:
        logger.exception("failed to read db in schedule_on_startup")
    except Exception as e:
        logger.exception("schedule_on_startup failed")
        

async def fetchval(db, query, params=()):
    try:
        cursor = await db.execute(query, params if isinstance(params, (tuple, list)) else (params,))
        row = await cursor.fetchone()
        await cursor.close()
    except DatabaseError as e:
        logger.exception("DB Error in fetchval")
    return row[0] if row else None


async def UpdatePin(interaction: discord.Interaction):
    try:
        newmessage = f""
        cursor = await bot.bdcon.execute("SELECT * FROM birthdays WHERE guild_id = ?", (interaction.guild_id,))
        for row in await cursor.fetchall():
            newmessage += f"<@{row[1]}>: {calendar.month_name[row[2]]} {row[3]} {row[4] if row[4] is not None else ""}\n"
        pinid = await fetchval(bot.bdcon, "SELECT list_pin_id FROM guilds WHERE guild_id = ?", (interaction.guild_id))
        if pinid:
            print("Pin found, updating pin")
            pin = await interaction.channel.fetch_message(pinid)
            await pin.edit(content=newmessage)
        else:
            print("No pin found, creating new pin")
            newPin = await interaction.channel.send(content = newmessage)
            await newPin.pin()
            await bot.bdcon.execute("UPDATE guilds SET list_pin_id = ? WHERE guild_id = ?", (newPin.id, interaction.guild.id))
            await bot.bdcon.commit()
    except DatabaseError as e:
        logger.exception("DB Error in UpdatePin")
        await bot.bdcon.rollback()
        await interaction.followup.send("Something went wrong")
    except Exception as e:
        await interaction.followup.send("Something went wrong")
        




@bot.event
async def on_guild_join(guild):
    logger.info(f"Joined new guild: {guild.name}")
    await bot.tree.sync(guild = guild)
    try:
        await bot.bdcon.execute("INSERT INTO guilds (guild_id) VALUES (?)", (guild.id,))
        await bot.bdcon.commit()
    except DatabaseError as e:
        logger.exception(f"Failure to add {guild.name} into DB")
        await bot.bdcon.rollback()

    

@bot.event
async def on_guild_remove(guild):
    logger.info(f"Removed from guild: {guild.name}")
    try:
        await bot.bdcon.execute("DELETE FROM guilds WHERE guild_id = ?", (guild.id,))
        await bot.bdcon.execute("DELETE FROM birthdays WHERE guild_id = ?", (guild.id,))
        await bot.bdcon.commit()
    except DatabaseError as e:
        logger.exception(f"Failure to remove {guild.name} from DB")

@bot.event
async def on_guild_channel_delete(channel):
    try:
        async with bot.bdcon.execute("SELECT birthday_channel_id FROM guilds WHERE guild_id = ?", (channel.guild.id,)) as cursor:
            row = await cursor.fetchone()
            birthday_channel_id = 1
            if row:
                birthday_channel_id = row[0]
        if birthday_channel_id == channel.id:
            await bot.bdcon.execute("UPDATE guilds SET birthday_channel_id = NULL, button_pin_id = NULL, list_pin_id = NULL WHERE guild_id = ?", (channel.guild.id,))
    except DatabaseError as e:
        logger.exception("failure to remove channel from DB")
        await bot.bdcon.rollback()
    except Exception as e:
        logger.exception("on_guild_channel_delete has failed")
        await bot.bdcon.rollback()

@bot.tree.command(name="updatepin", description="Update the Pin")
async def updatepin(interaction: discord.Interaction):
    await interaction.response.defer()
    await UpdatePin(interaction)
    await interaction.followup.send("Pin Updated!")

@bot.tree.command(name = "createbdaypin", description="Creates a new birthday submission pin!")
async def createbdaypin(interaction: discord.Interaction):
    await create_input_pin(interaction.channel, interaction.client)

async def create_input_pin(birthdays_channel, bot):
    print("create_input_pin triggered")
    pin = await birthdays_channel.send(content = "Add or edit your birthday!", view = bot.BirthdayView())
    await pin.pin()
    try:
        await bot.bdcon.execute("UPDATE guilds SET birthday_channel_id = ?, button_pin_id = ? WHERE guild_id = ?", (birthdays_channel.id, pin.id, birthdays_channel.guild.id))
        await bot.bdcon.commit()
    except DatabaseError as e:
        logger.exception("Failure to update db with input pin")
        await bot.bdcon.rollback()

bot.setup_hook = setup_hook
bot.UpdatePin = UpdatePin
bot.create_input_pin = create_input_pin 

bot.run(os.getenv('DISCORD_TOKEN'), log_handler = discord_log_handler, log_formatter = formatter)
