# 🎂 Birthday Bot!

This project was built as both a **portfolio piece** to demonstrate my programming abilities and as a **functional Discord bot** to help track and manage birthdays within a Discord server among friends.

If not already, I plan to deploy this bot soon as a functioning public bot:  
👉 [Invite Link](https://discord.com/oauth2/authorize?client_id=1418694450024284286)

---

## 🧠 About the Project

This bot showcases my understanding of:
- **Asynchronous programming** (`async/await`)
- **Database integration** (SQLite)
- **Task scheduling** (`apscheduler`)
- **Logging and error handling** (`logging`, `traceback`)
- **API and library usage** (`discord.py`)

It was developed on **Linux via WSL**, inside a **Python virtual environment**.

---

## 🧩 Libraries and Tools Used

- `discord.py`
- `asyncio`
- `sqlite3`
- `apscheduler`
- `logging`
- `traceback`

---

## ⚙️ Installation Instructions (Linux)

1. **Clone the repository**
   ```bash
   git clone https://github.com/Oreo412/BirthdayBot.git
   cd BirthdayBot
   ```
2. **Create a virtual environment**
   ```bash
    python3 -m venv bot-env
    source bot-env/bin/activate
   ```
3. **Create the database folder**
    ```bash 
    mkdir database
    ```
 4. **Set up your environment variables**
    ```bash
    cp .env.example .env
    ```
    Open the file and add your bot token
    
    DISCORD_TOKEN = 'your_bot_token_here'

    Alternatively, create the file manually with
    ```bash
    echo "DISCORD_TOKEN=your_bot_token_here" > .env
    ```
  5. **Install dependencies**
     ```bash
     pip install -r requirements.txt
     ```
  6. **Run the bot**
     ```bash
     python3 main.py
     ```

