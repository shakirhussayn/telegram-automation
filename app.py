import os
import re
import cv2
import easyocr
import asyncio
import time
from telethon import TelegramClient, events

# --- CONFIGURATION - Loaded from Railway Environment Variables ---
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_PATH = "/app/sessions/shakir.session"

# The numeric IDs of the source and destination channels/groups
SOURCE_CHAT_ID = int(os.environ.get("SOURCE_CHAT_ID"))
DESTINATION_CHAT_ID = int(os.environ.get("DESTINATION_CHAT_ID"))

# --- OCR & CROP SETTINGS ---
Y_START = 800
X_START = 200

# --- Initialize Tools ---
print("Initializing OCR Reader...")
reader = easyocr.Reader(['en'])
print("OCR Ready.")

client = TelegramClient(SESSION_PATH, API_ID, API_HASH)

def get_template(lat, lon):
    """Creates the formatted text template."""
    current_date = time.strftime("%Y 年 %m 月 %d日")
    return f"""{current_date}
员工姓名 Employee Name: shakir
城市 City: Larkana
经度Longitude: {lat}° N {lon}° E"""

def extract_coordinates(filepath):
    """Extracts Lat/Long from a single image file."""
    try:
        img = cv2.imread(filepath)
        if img is None:
            print("  -> Error: Could not read image file")
            return "Error", "Error"
            
        height, width, _ = img.shape
        cropped_img = img[Y_START:height, X_START:width]
        
        full_text = ' '.join(reader.readtext(cropped_img, detail=0, paragraph=True))
        print(f"  -> OCR Text: {full_text}")
        
        lat_match = re.search(r"Lat\s+([\d\.]+)", full_text, re.IGNORECASE)
        long_match = re.search(r"Long\s+([\d\.]+)", full_text, re.IGNORECASE)
        
        lat = lat_match.group(1) if lat_match else "Not Found"
        lon = long_match.group(1) if long_match else "Not Found"
        
        print(f"  -> Extracted coordinates: Lat={lat}, Long={lon}")
        return lat, lon
        
    except Exception as e:
        print(f"  -> Error extracting coordinates: {e}")
        return "Error", "Error"

@client.on(events.NewMessage(chats=SOURCE_CHAT_ID))
async def handler(event):
    """This function runs whenever a new message with a photo is sent to the source chat."""
    if event.message.photo:
        print(f"New image received from message ID: {event.message.id}")
        
        try:
            temp_path = await event.message.download_media()
            print(f"  -> Downloaded to: {temp_path}")
            
            latitude, longitude = extract_coordinates(temp_path)
            
            if latitude in ["Not Found", "Error"] or longitude in ["Not Found", "Error"]:
                print("  -> Could not find valid coordinates. Skipping.")
                return
            
            template_text = get_template(latitude, longitude)
            print(f"  -> Generated template: {template_text}")
            
            print("  -> Uploading to destination group...")
            await client.send_file(DESTINATION_CHAT_ID, temp_path, caption=template_text)
            print("  -> ✅ Successfully posted.")
            
        except Exception as e:
            print(f"  -> Error processing message: {e}")
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)

async def main():
    print("Service starting...")
    await client.start()
    print(f"✅ Service started. Listening for new images in Chat ID: {SOURCE_CHAT_ID}")
    print("Service is running. Press Ctrl+C to stop.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
