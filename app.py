import os
import asyncio
import random
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- A dictionary to hold the state (like counters) for each account ---
# The key will be the account number (e.g., 1, 2, 3...)
bot_states = {}

def get_template(date, staff_name, current_number, location):
    """Creates the formatted text template."""
    return f"""DATE : {date}
工作员工姓名 STAFF NAME : {staff_name}
当日编号 NUMBER OF THE DAY: {current_number:02}
历史编号 HISTORY NUMBER : {current_number:02}
照片所在地区 PHOTO LOCATION: {location}
"""

def create_handler(account_id):
    """
    This function creates a unique event handler for each account.
    This is important so that each handler knows which account's data to use.
    """
    lock = asyncio.Lock()
    
    @events.register(events.NewMessage(chats=bot_states[account_id]['source_id']))
    async def handler(event):
        # Use the lock to process images one at a time for this specific account
        async with lock:
            state = bot_states[account_id]
            
            # Use this account's specific counter
            current_history_num = state['history_counter']
            
            print(f"--- ACCOUNT {account_id}: Processing History #{current_history_num} ---")
            
            template_text = get_template(
                state['date'],
                state['staff_name'],
                current_history_num, # Both numbers are the same
                state['photo_location']
            )
            
            await event.client.send_file(
                state['destination_id'],
                event.message.photo,
                caption=template_text
            )
            
            print(f"  -> ✅ ACCOUNT {account_id}: Successfully posted History #{current_history_num}.")
            
            # Increment this account's specific counter
            bot_states[account_id]['history_counter'] += 1
            
            delay = random.randint(15, 20)
            print(f"  -> ACCOUNT {account_id}: Waiting for {delay} seconds...")
            await asyncio.sleep(delay)
            print(f"--- ACCOUNT {account_id}: Handler complete. ---")

    return handler


async def main():
    clients = []
    
    # Loop to find all accounts defined in environment variables (ACCOUNT_1, ACCOUNT_2, etc.)
    account_num = 1
    while True:
        # Check if the essential variables for this account number exist
        session_str = os.environ.get(f"TELETHON_SESSION_{account_num}")
        api_id = os.environ.get(f"API_ID_{account_num}")
        api_hash = os.environ.get(f"API_HASH_{account_num}")
        
        if not all([session_str, api_id, api_hash]):
            # If we can't find variables for this number, we assume there are no more accounts
            break
            
        print(f"Found configuration for Account #{account_num}")
        
        # Create the client for this account
        client = TelegramClient(StringSession(session_str), int(api_id), api_hash)
        clients.append(client)
        
        # Load all the settings and counters for this account into our state dictionary
        bot_states[account_num] = {
            'source_id': int(os.environ.get(f"SOURCE_CHAT_ID_{account_num}")),
            'destination_id': int(os.environ.get(f"DESTINATION_CHAT_ID_{account_num}")),
            'date': os.environ.get(f"DATE_{account_num}"),
            'staff_name': os.environ.get(f"STAFF_NAME_{account_num}"),
            'photo_location': os.environ.get(f"PHOTO_LOCATION_{account_num}"),
            'history_counter': int(os.environ.get(f"START_HISTORY_NUM_{account_num}", 1))
        }
        
        # Create and add the unique event handler for this client
        client.add_event_handler(create_handler(account_num))
        
        account_num += 1

    if not clients:
        print("🛑 ERROR: No account configurations found. Please set environment variables like TELETHON_SESSION_1, API_ID_1, etc.")
        return

    print(f"\nStarting {len(clients)} bot instance(s)...")
    await asyncio.gather(*(client.start() for client in clients))
    print("✅ All services started.")
    await asyncio.gather(*(client.run_until_disconnected() for client in clients))


if __name__ == "__main__":
    asyncio.run(main())
