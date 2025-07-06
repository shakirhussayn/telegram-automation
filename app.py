import os
import re
import requests
import asyncio
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# --- CONFIGURATION ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("TELETHON_SESSION")
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY")
EMPLOYEE_NAME = os.environ.get("EMPLOYEE_NAME", "shakir")
SOURCE_CHAT_ID = int(os.environ.get("SOURCE_CHAT_ID"))
DESTINATION_CHAT_ID = int(os.environ.get("DESTINATION_CHAT_ID"))

stamp_counter = 0
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

def dd_to_dms(deg_str, is_lat):
    """Converts Decimal Degrees to Degrees, Minutes, Seconds format."""
    try:
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
    except (ValueError, TypeError):
        return "Invalid Coordinate"

def get_template(lat_dd, lon_dd, stamp_num, employee_name):
    """Creates the formatted text template (using a static date)."""
    lat_dms = dd_to_dms(lat_dd, is_lat=True)
    lon_dms = dd_to_dms(lon_dd, is_lat=False)
    
    # Using a static date for now to isolate the coordinate issue
    static_date = "2025 年 07 月 06日"

    return f"""{static_date}
序号 sort no：1
员工姓名 Employee Name；{employee_name}
墙上印章数量 Number of wall stamps ; {stamp_num}
城市 City :Larkana
经度Longitude :{lat_dms} {lon_dms}
"""

def extract_data(filepath):
    """Extracts only Lat and Long from the image via ocr.space API."""
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
            return None, None

        ocr_text = result['ParsedResults'][0]['ParsedText']
        print(f"  -> Raw OCR Text: {ocr_text}")
        
        ## --- THIS IS THE CRITICAL SECTION THAT FIXES THE ERROR --- ##
        # The next two lines DEFINE the variables. They must come first.
        lat_match = re.search(r"Lat\s+([+-]?\d{1,3}\.\d+)", ocr_text, re.IGNORECASE)
        lon_match = re.search(r"Long\s+([+-]?\d{1,3}\.\d+)", ocr_text, re.IGNORECASE)

        # The next two lines USE the variables. They must come after.
        # This structure prevents the 'not defined' error.
        lat = lat_match.group(1).removesuffix('0') if lat_match and lat_match.group(1) else None
        lon = lon_match.group(1).removesuffix('0') if lon_match and lon_match.group(1) else None
        ## -------------------------------------------------------- ##
        
        print(f"  -> Extracted Raw Lat: {lat}, Long: {lon}")
        return lat, lon

    except Exception as e:
        print(f"  -> Error calling OCR API or processing result: {e}")
        return None, None

@client.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def handler(event):
    global stamp_counter
    if event.message.photo:
        print(f"New image received from message ID: {event.message.id}")
        temp_path = None
        try:
            temp_path = await event.message.download_media()
            latitude, longitude = extract_data(temp_path)
            
            if not all([latitude, longitude]):
                print("  -> Could not extract valid coordinates. Skipping.")
                return

            stamp_counter += 1
            template_text = get_template(latitude, longitude, stamp_counter, EMPLOYEE_NAME)
            await client.send_file(DESTINATION_CHAT_ID, temp_path, caption=template_text)
            print(f"  -> ✅ Successfully posted. (Stamp #{stamp_counter})")
        except Exception as e:
            print(f"  -> Top-level error in handler: {e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

async def main():
    required_vars = ["API_ID", "API_HASH", "TELETHON_SESSION", "OCR_SPACE_API_KEY", "EMPLOYEE_NAME", "SOURCE_CHAT_ID", "DESTINATION_CHAT_ID"]
    if not all(os.environ.get(var) for var in required_vars):
        print("🛑 ERROR: One or more required environment variables are missing.")
        return
        
    print("Service starting...")
    await client.start()
    print(f"✅ Service started. Listening for new images in Chat ID: {SOURCE_CHAT_ID}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
