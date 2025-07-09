import os
import asyncio
import random
import re
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- CONFIGURATION ---
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID"))

# --- STATE & CLIENTS ---
bot_states = {}
clients = []
lock = asyncio.Lock()

def get_template(date, staff_name, daily_num, history_num, location):
    """Creates the final formatted text template."""
    return f"""日期 DATE : {date}
工作员工姓名STAFF NAME: {staff_name}
当日编号 NUMBER OF THE DAY : {daily_num:02}
历史编号 HISTORY NUMBER : {history_num:02}
照片所在地区 PHOTO LOCATION:{location}
"""

def create_photo_handler(account_id):
    """Creates a unique event handler for processing photos for each account."""
    @events.register(events.NewMessage(chats=bot_states[account_id]['source_id']))
    async def photo_handler(event):
        if event.message.photo:
            async with lock:
                state = bot_states[account_id]
                
                # --- NEW: Check if the bot is active ---
                if not state['is_active']:
                    print(f"--- ACCOUNT {account_id}: Paused. Ignoring photo. ---")
                    return # Stop processing if paused
                
                # --- Automatic Daily Counter Reset Logic ---
                today_str = datetime.now().strftime("%Y-%m-%d")
                if today_str != state['last_processed_date']:
                    print(f"--- ACCOUNT {account_id}: New day! Resetting daily counter. ---")
                    state['daily_counter'] = 1
                    state['last_processed_date'] = today_str

                print(f"--- ACCOUNT {account_id}: Processing Daily #{state['daily_counter']}, History #{state['history_counter']} ---")
                
                template_text = get_template(
                    state['date'],
                    state['staff_name'],
                    state['daily_counter'],
                    state['history_counter'],
                    state['photo_location']
                )
                
                await event.client.send_file(
                    state['destination_id'],
                    event.message.photo,
                    caption=template_text
                )
                
                print(f"  -> ✅ ACCOUNT {account_id}: Successfully posted History #{state['history_counter']}.")
                
                state['daily_counter'] += 1
                state['history_counter'] += 1
                
                delay = random.randint(15, 20)
                print(f"  -> ACCOUNT {account_id}: Waiting for {delay} seconds...")
                await asyncio.sleep(delay)
                print(f"--- ACCOUNT {account_id}: Handler complete. ---")

    return photo_handler

@events.register(events.NewMessage(chats=ADMIN_CHAT_ID))
async def command_handler(event):
    """Handles all commands sent to the admin chat."""
    try:
        command_text = event.message.text.strip()
        
        # --- NEW: Handler for /start and /stop commands ---
        if command_text.startswith(('/start', '/stop')):
            parts = command_text.split()
            if len(parts) != 2 or not parts[1].isdigit():
                await event.reply("Invalid format. Use `/start <account_number>` or `/stop <account_number>`.")
                return
            
            account_id_to_change = int(parts[1])
            if account_id_to_change not in bot_states:
                await event.reply(f"❌ Account ID {account_id_to_change} not found.")
                return

            if parts[0] == '/start':
                bot_states[account_id_to_change]['is_active'] = True
                await event.reply(f"✅ Account {account_id_to_change} has been **started**.")
            elif parts[0] == '/stop':
                bot_states[account_id_to_change]['is_active'] = False
                await event.reply(f"🛑 Account {account_id_to_change} has been **stopped**.")
            return

        # --- Handler for /set command ---
        if command_text.startswith('/set'):
            match = re.match(r"/set (\d+) (.+)=(.+)", command_text)
            if not match:
                await event.reply("Invalid format. Use `/set <account_number> VARIABLE=Value`.")
                return

            account_id_to_change = int(match.group(1))
            key = match.group(2).strip().upper()
            new_value = match.group(3).strip()

            if account_id_to_change not in bot_states:
                await event.reply(f"❌ Account ID {account_id_to_change} not found.")
                return

            state = bot_states[account_id_to_change]
            updated = False
            
            if key == "STAFF_NAME":
                state['staff_name'] = new_value; updated = True
            elif key == "DATE":
                state['date'] = new_value; updated = True
            elif key == "PHOTO_LOCATION":
                state['photo_location'] = new_value; updated = True
            elif key == "START_DAILY_NUM":
                state['daily_counter'] = int(new_value); updated = True
            elif key == "START_HISTORY_NUM":
                state['history_counter'] = int(new_value); updated = True
            
            if updated:
                await event.reply(f"✅ Account {account_id_to_change}: {key} updated to '{new_value}'")
            else:
                await event.reply(f'❌ Unknown setting: {key}')
            
    except Exception as e:
        await event.reply(f"🛑 Error processing command: {e}")

async def main():
    account_num = 1
    while True:
        session_str = os.environ.get(f"TELETHON_SESSION_{account_num}")
        api_id = os.environ.get(f"API_ID_{account_num}")
        api_hash = os.environ.get(f"API_HASH_{account_num}")
        if not all([session_str, api_id, api_hash]):
            break
            
        print(f"Found configuration for Account #{account_num}")
        client = TelegramClient(StringSession(session_str), int(api_id), api_hash)
        
        # Initialize the state for this account
        bot_states[account_num] = {
            'source_id': int(os.environ.get(f"SOURCE_CHAT_ID_{account_num}")),
            'destination_id': int(os.environ.get(f"DESTINATION_CHAT_ID_{account_num}")),
            'date': os.environ.get(f"DATE_{account_num}"),
            'staff_name': os.environ.get(f"STAFF_NAME_{account_num}"),
            'photo_location': os.environ.get(f"PHOTO_LOCATION_{account_num}"),
            'history_counter': int(os.environ.get(f"START_HISTORY_NUM_{account_num}", 1)),
            'daily_counter': int(os.environ.get(f"START_DAILY_NUM_{account_num}", 1)),
            'last_processed_date': datetime.now().strftime("%Y-%m-%d"),
            'is_active': True # Bots start in an active state by default
        }
        
        client.add_event_handler(create_photo_handler(account_num))
        client.add_event_handler(command_handler)
        clients.append(client)
        account_num += 1

    if not clients:
        print("🛑 ERROR: No account configurations found.")
        return

    print(f"\nStarting {len(clients)} bot instance(s)...")
    await asyncio.gather(*(c.start() for c in clients))
    print("✅ All services started.")
    await asyncio.gather(*(c.run_until_disconnected() for c in clients))

if __name__ == "__main__":
    asyncio.run(main())
