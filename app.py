import os
import re
import requests
import asyncio
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- CONFIGURATION - Loaded from Railway Environment Variables ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("TELETHON_SESSION")
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY")
EMPLOYEE_NAME = os.environ.get("EMPLOYEE_NAME", "shakir") # <-- New variable
SOURCE_CHAT_ID = int(os.environ.get("SOURCE_CHAT_ID"))
DESTINATION_CHAT_ID = int(os.environ.get("DESTINATION_CHAT_ID"))

# --- STATEFUL COUNTER for Wall Stamps ---
stamp_counter = 0

# --- Client Initialization ---
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


# --- NEW HELPER FUNCTION for Coordinate Formatting ---
def dd_to_dms(deg_str, is_lat):
    """Converts Decimal Degrees to Degrees, Minutes, Seconds format."""
    deg = float(deg_str)
    d = int(deg)
    m_float = abs(deg - d) * 60
    m = int(m_float)
    s = (m_float - m) * 60
    
    if is_lat:
        direction = 'N' if deg >= 0 else 'S'
    else:
        direction = 'E' if deg >= 0 else 'W'
        
    return f'{abs(d)}°{m}\'{s:.1f}"{direction}'


def get_template(lat_dd, lon_dd, date_str, stamp_num, employee_name):
    """Creates the formatted text template with all new requirements."""
    # Convert decimal degrees to DMS format
    lat_dms = dd_to_dms(lat_dd, is_lat=True)
    lon_dms = dd_to_dms(lon_dd, is_lat=False)
    
    # Reformat date from MM/DD/YYYY to YYYY 年 MM 月 DD日
    try:
        # Assumes date is in MM/DD/YYYY format from OCR
        m, d, y = date_str.split('/')
        formatted_date = f"{y} 年 {m} 月 {d}日"
    except:
        # Fallback if date format is unexpected
        formatted_date = date_str

    return f"""{formatted_date}
序号 sort no：1
员工姓名 Employee Name；{employee_name}
墙上印章数量 Number of wall stamps ; {stamp_num}
城市 City :Larkana
经度Longitude :{lat_dms} {lon_dms}
"""

def extract_data(filepath):
    """Extracts Lat, Long, and Date by sending the image to the ocr.space API."""
    try:
        with open(filepath, 'rb') as f:
            response = requests.post(
                'https://api.ocr.space/parse/image',
                headers={'apikey': OCR_SPACE_API_KEY},
                files={'file': f}
            )
        response.raise_for_status()
        result = response.json()

        if result.get('IsErroredOnProcessing'):
            print(f"  -> OCR API Error: {result.get('ErrorMessage')}")
            return None, None, None

        ocr_text = result['ParsedResults'][0]['ParsedText']
        
        # Define all the search patterns first
        lat_match = re.search(r"Lat\s+([\d\.]+)", ocr_text, re.IGNORECASE)
        lon_match = re.search(r"Long\s+([\d\.]+)", ocr_text, re.IGNORECASE)
        date_match = re.search(r"(\d{2}/\d{2}/\d{4})", ocr_text)

        # Then, use them to get the values
        lat = lat_match.group(1).removesuffix('0') if lat_match else None
        lon = lon_match.group(1).removesuffix('0') if lon_match else None
        date = date_match.group(1) if date_match else "Unknown Date"
        
        return lat, lon, date
            
    except Exception as e:
        print(f"  -> Error calling OCR API or processing result: {e}")
        return None, None, None
        
@client.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def handler(event):
    global stamp_counter
    if event.message.photo:
        print(f"New image received from message ID: {event.message.id}")
        temp_path = None
        try:
            temp_path = await event.message.download_media()
            latitude, longitude, date = extract_data(temp_path)
            
            if not all([latitude, longitude, date]):
                print("  -> Could not extract all required data. Skipping.")
                return

            # Increment the counter for this image
            stamp_counter += 1
            
            template_text = get_template(latitude, longitude, date, stamp_counter, EMPLOYEE_NAME)
            await client.send_file(DESTINATION_CHAT_ID, temp_path, caption=template_text)
            print(f"  -> ✅ Successfully posted. (Stamp #{stamp_counter})")
        except Exception as e:
            print(f"  -> Top-level error in handler: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

async def main():
    if not all([SESSION_STRING, API_ID, API_HASH, OCR_SPACE_API_KEY, SOURCE_CHAT_ID, DESTINATION_CHAT_ID, EMPLOYEE_NAME]):
        print("🛑 ERROR: One or more required environment variables are missing.")
        return
        
    print("Service starting...")
    await client.start()
    print(f"✅ Service started. Listening for new images in Chat ID: {SOURCE_CHAT_ID}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
