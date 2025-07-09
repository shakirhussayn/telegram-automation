import os
import asyncio
import random
import re
from datetime import datetime
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- CONFIGURATION ---
# A helper function to safely read and clean integer variables
def get_int_env(key, default=None):
    val = os.environ.get(key)
    if val is None:
        return default
    # This removes any character that is NOT a digit or a minus sign
    cleaned_val = re.sub(r'[^\d-]', '', val)
    return int(cleaned_val)

ADMIN_CHAT_ID = get_int_env("ADMIN_CHAT_ID")

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
                
                if not state['is_active']:
                    print(f"--- ACCOUNT {account_id}: Paused. Ignoring photo. ---")
                    return
                
                today_str = datetime.now().strftime("%Y-%m-%d")
                if today_str != state['last_processed_date']:
                    print(f"--- ACCOUNT {account_id}: New day detected! Resetting daily counter. ---")
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

@events.register(events.NewMessage(chats=ADMIN_CHAT_ID, pattern=r"/set (\d+) (.+)=(.+)"))
async def command_handler(event):
    try:
        # This handler remains the same
        account_id_to_change = int(event.pattern_match.group(1))
        key = event.pattern_match.group(2).strip().upper()
        new_value = event.pattern_match.group(3).strip()

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
        api_id_str = os.environ.get(f"API_ID_{account_num}")
        api_hash = os.environ.get(f"API_HASH_{account_num}")
        
        if not all([session_str, api_id_str, api_hash]):
            break
            
        print(f"Found configuration for Account #{account_num}")
        
        client = TelegramClient(StringSession(session_str), get_int_env(f"API_ID_{account_num}"), api_hash)
        
        bot_states[account_num] = {
            'source_id': get_int_env(f"SOURCE_CHAT_ID_{account_num}"),
            'destination_id': get_int_env(f"DESTINATION_CHAT_ID_{account_num}"),
            'date': os.environ.get(f"DATE_{account_num}"),
            'staff_name': os.environ.get(f"STAFF_NAME_{account_num}"),
            'photo_location': os.environ.get(f"PHOTO_LOCATION_{account_num}"),
            'history_counter': get_int_env(f"START_HISTORY_NUM_{account_num}", 1),
            'daily_counter': get_int_env(f"START_DAILY_NUM_{account_num}", 1),
            'last_processed_date': datetime.now().strftime("%Y-%m-%d"),
            'is_active': True
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
