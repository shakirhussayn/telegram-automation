import os
import re
import requests # <-- New import for making API calls
import asyncio
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- CONFIGURATION - Loaded from Railway Environment Variables ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("TELETHON_SESSION")
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY") # <-- Your new API key

# The numeric IDs of the source and destination channels/groups
SOURCE_CHAT_ID = int(os.environ.get("SOURCE_CHAT_ID"))
DESTINATION_CHAT_ID = int(os.environ.get("DESTINATION_CHAT_ID"))

# --- Client Initialization ---
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def get_template(lat, lon):
    """Creates the formatted text template."""
    current_date = time.strftime("%Y 年 %m 月 %d日")
    return f"""
{current_date}
员工姓名 Employee Name；shakir
城市 City :Larkana
经度Longitude :{lat}° N {lon}° E
"""

def extract_coordinates(filepath):
    """
    Extracts Lat/Long by sending the image to the ocr.space API.
    This is much faster than running a local model.
    """
    if not OCR_SPACE_API_KEY:
        print("  -> ERROR: OCR_SPACE_API_KEY environment variable is not set.")
        return "Error", "Error"
        
    try:
        with open(filepath, 'rb') as f:
            # Send the image file to the API
            response = requests.post(
                'https://api.ocr.space/parse/image',
                headers={'apikey': OCR_SPACE_API_KEY},
                files={'file': f}
            )
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        result = response.json()
        print(f"  -> API Response: {result}")
        
        if result.get('IsErroredOnProcessing'):
            print(f"  -> OCR API Error: {result.get('ErrorMessage')}")
            return "Error", "Error"

        # 1. Get the full block of text from the API response
        ocr_text = result['ParsedResults'][0]['ParsedText']
        
        # 2. Find the numbers associated with Lat and Long
        lat_match = re.search(r"Lat\s+([\d\.]+)", ocr_text, re.IGNORECASE)
        long_match = re.search(r"Long\s+([\d\.]+)", ocr_text, re.IGNORECASE)
        
        if lat_match and long_match:
            raw_lat = lat_match.group(1)
            raw_lon = long_match.group(1)

            # 3. Clean the data by removing the trailing '0' from the misread degree symbol
            clean_lat = raw_lat.removesuffix('0')
            clean_lon = raw_lon.removesuffix('0')
            
            print(f"  -> Extracted coordinates: Lat={clean_lat}, Long={clean_lon}")
            return clean_lat, clean_lon
        else:
            print("  -> Could not find Lat/Long in OCR text.")
            return "Not Found", "Not Found"
            
    except Exception as e:
        print(f"  -> Error calling OCR API or processing result: {e}")
        return "Error", "Error"

@client.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def handler(event):
    if event.message.photo:
        print(f"New image received from message ID: {event.message.id}")
        temp_path = None
        try:
            temp_path = await event.message.download_media()
            latitude, longitude = extract_coordinates(temp_path)
            if latitude in ["Not Found", "Error"]:
                return
            template_text = get_template(latitude, longitude)
            await client.send_file(DESTINATION_CHAT_ID, temp_path, caption=template_text)
            print("  -> ✅ Successfully posted.")
        except Exception as e:
            print(f"  -> Top-level error in handler: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

async def main():
    if not all([SESSION_STRING, API_ID, API_HASH, OCR_SPACE_API_KEY, SOURCE_CHAT_ID, DESTINATION_CHAT_ID]):
        print("🛑 ERROR: One or more required environment variables are missing.")
        return
        
    print("Service starting...")
    await client.start()
    print(f"✅ Service started. Listening for new images in Chat ID: {SOURCE_CHAT_ID}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
