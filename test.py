# This example requires the 'message_content' intent.

import discord
import json 
import aiosqlite
import traceback
from dotenv import load_dotenv
import os


intents = discord.Intents.default()
intents.message_content = True


client = discord.Client(intents=intents)

load_dotenv()


bdcon: aiosqlite.Connection = None  #bdcon = birthday connection. db and con are cringe

@client.event
async def on_ready():
    
    global bdcon 
    bdcon = await aiosqlite.connect("database/birthdays.db")
    try:
        await bdcon.executescript("""
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
            CREATE TABLE IF NOT EXISTS pins (
                guild_id int NOT NULL,
                pin_id int NOT NULL,
                PRIMARY KEY (guild_id)
            );
        """)
        await bdcon.commit()
        print(f'We have logged in as {client.user}')
    except Exception as e:
        print("DB init failed:", repr(e))
        print("TRACEBACK:\n", "".join(traceback.format_exception(type(e), e, e.__traceback__)))
        

    

@client.event
async def on_message(message):
    global bdcon
    if message.author == client.user:
        return

    
    if message.content.startswith('My Birthday Is: '):
        print(message.content)
        try:

            blist = message.content.split()
            month = int(blist[3])
            day = int(blist[4])
            year = int(blist[5])
            print("Month: " + str(month) + "\nDay: " + str(day) + "\nYear: " + str(year))
            await bdcon.execute("""
                INSERT INTO birthdays (guild_id, member_id, month, day, year) VALUES (?, ?, ?, ?, ?)
            """, (message.guild.id, message.author.id, month, day, year))
            await bdcon.commit()
            await message.channel.send("It should have worked fine")
            print("It should have worked fine")
        except Exception as e:
            await message.channel.send("Something went wrong")
            print("Insert failed: ", repr(e))
            print("TRACEBACK:\n", "".join(traceback.format_exception(type(e), e, e.__traceback__)))
    
    if message.content.startswith('reply'):
        try:
            pin = await message.reply('tested')
            await pin.pin()
        except Exception as e:
            print("Creating a pinned message failed: ", repr(e))
            await message.channel.send('pin failed')


    if message.content.startswith('WMD'):
        try: 
            cursor = await bdcon.execute("SELECT * FROM birthdays WHERE guild_id = ? AND member_id = ?", (message.guild.id, message.author.id))
            row = await cursor.fetchone()
            print(row)
        except Exception as e:
            print("Idk what happened: ", repr(e))
            print("TRACEBACK:\n", "".join(traceback.format_exception(type(e), e, e.__traceback__)))
    
    if message.content.startswith('Update Pin'):
        try:
            newmessage = f""
            cursor = await bdcon.execute("SELECT * FROM birthdays WHERE guild_id = ?", (message.guild.id,))
            for row in await cursor.fetchall():
                newmessage += f"<@{row[1]}>: {row[2]} {row[3]} {row[4]}\n"
            pinid = await fetchval(bdcon, "SELECT pin_id FROM pins WHERE guild_id = ?", (message.guild.id))
            if pinid:
                pin = await message.channel.fetch_message(pinid)
                await pin.edit(content=newmessage)
            else:
                newPin = await message.channel.send(newmessage)
                await newPin.pin()
                await bdcon.execute("INSERT INTO pins (guild_id, pin_id) VALUES (?, ?)", (message.guild.id, newPin.id))
                await bdcon.commit()
        except Exception as e:
            await message.channel.send("Something went wront")
            print("pin update error: ", repr(e))
            print("TRACEBACK:\n", "".join(traceback.format_exception(type(e), e, e.__traceback__)))

    


async def fetchval(db, query, params=()):
    cursor = await db.execute(query, params if isinstance(params, (tuple, list)) else (params,))
    row = await cursor.fetchone()
    await cursor.close()
    return row[0] if row else None
      

client.run(os.getenv('DISCORD_TOKEN'))
