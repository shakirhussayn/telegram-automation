import os
import asyncio
import random
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- CONFIGURATION - Loaded from Railway Environment Variables ---
# These act as the default startup values
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("TELETHON_SESSION")

# New variables for the template
DATE = os.environ.get("DATE", "Not Set")
STAFF_NAME = os.environ.get("STAFF_NAME", "Not Set")
PHOTO_LOCATION = os.environ.get("PHOTO_LOCATION", "Not Set")
START_DAILY_NUM = int(os.environ.get("START_DAILY_NUM", 1))
START_HISTORY_NUM = int(os.environ.get("START_HISTORY_NUM", 1))

# Telegram Channel/Group IDs
SOURCE_CHAT_ID = int(os.environ.get("SOURCE_CHAT_ID"))
DESTINATION_CHAT_ID = int(os.environ.get("DESTINATION_CHAT_ID"))

# --- STATEFUL COUNTERS ---
# These are initialized from the Railway variables
daily_counter = START_DAILY_NUM
history_counter = START_HISTORY_NUM

# --- TELEGRAM CLIENT ---
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def get_template(date, staff_name, daily_num, history_num, location):
    """Creates the new formatted text template."""
    return f"""DATE : {date}
工作员工姓名 STAFF NAME : {staff_name}
当日编号 NUMBER OF THE DAY: {daily_num}
历史编号 HISTORY NUMBER : {history_num}
照片所在地区 PHOTO LOCATION: {location}
"""

@client.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def handler(event):
    global daily_counter, history_counter
    global DATE, STAFF_NAME, PHOTO_LOCATION

    # --- NEW: Command Handling Logic ---
    if event.message.text and event.message.text.startswith('/set'):
        command_text = event.message.text.strip()
        parts = command_text.split('=', 1)
        if len(parts) == 2:
            key_part, new_value = parts
            key = key_part.split(' ', 1)[1].upper() # Get the variable name like "STAFF_NAME"
            
            updated = False
            if key == "STAFF_NAME":
                STAFF_NAME = new_value.strip()
                updated = True
            elif key == "DATE":
                DATE = new_value.strip()
                updated = True
            elif key == "PHOTO_LOCATION":
                PHOTO_LOCATION = new_value.strip()
                updated = True
            elif key == "START_DAILY_NUM":
                daily_counter = int(new_value.strip())
                updated = True
            elif key == "START_HISTORY_NUM":
                history_counter = int(new_value.strip())
                updated = True
            
            if updated:
                await event.reply(f'✅ Setting updated: {key} is now "{new_value.strip()}"')
            else:
                await event.reply(f'❌ Unknown setting: {key}')
        return

    # --- Existing Photo Handling Logic ---
    if event.message.photo:
        print(f"Image received. Preparing post #{daily_counter}...")
        
        template_text = get_template(
            DATE,
            STAFF_NAME,
            daily_counter,
            history_counter,
            PHOTO_LOCATION
        )
        
        await client.send_file(
            DESTINATION_CHAT_ID,
            event.message.photo,
            caption=template_text
        )
        
        print(f"  -> ✅ Successfully posted History #{history_counter}.")
        
        daily_counter += 1
        history_counter += 1
        
        delay = random.randint(5, 10)
        print(f"  -> Waiting for {delay} seconds...")
        await asyncio.sleep(delay)

async def main():
    required_vars = ["API_ID", "API_HASH", "TELETHON_SESSION", "SOURCE_CHAT_ID", "DESTINATION_CHAT_ID"]
    if not all(os.environ.get(var) for var in required_vars):
        print("🛑 ERROR: One or more critical environment variables are missing.")
        return
        
    print("Service starting with the following default data:")
    print(f"  -> Date: {DATE}")
    print(f"  -> Staff: {STAFF_NAME}")
    print(f"  -> Location: {PHOTO_LOCATION}")
    print(f"  -> Starting Numbers: Daily={daily_counter}, History={history_counter}")
    
    await client.start()
    print(f"✅ Service started. Listening for messages in Chat ID: {SOURCE_CHAT_ID}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
