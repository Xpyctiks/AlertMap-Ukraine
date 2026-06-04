#!/usr/local/bin/python3

import requests
import logging
import time as delay
import asyncio
import httpx
import os
from datetime import datetime, time
from pathlib import Path
from dotenv import load_dotenv

VERSION="1.1.0"
HA_URL = HA_TOKEN = API_TOKEN = TELEGRAM_CHATID = TELEGRAM_TOKEN = LED_GROUP_NAME = LED_ENTITY = API_URL = ""
GREEN = [0, 255, 0]
RED = [255, 0, 0]
YELLOW = [255, 255, 0]
MEMORY_UPDATED = False
DAY_NIGHT_ENABLED = True
DAY_NIGHT_FROM = ""
DAY_NIGHT_TO = ""
DAY_NIGHT_DAYBRIGHTNESS = 255
DAY_NIGHT_NIGHTBRIGHTNESS = 90

logging.basicConfig(filename=os.path.join(Path(__file__).resolve().parent,"log.txt"),level=logging.ERROR,format='%(asctime)s - Alertmap-Ukraine - %(levelname)s - %(message)s',datefmt='%d-%m-%Y %H:%M:%S')
memory_file = os.path.join(Path(__file__).resolve().parent,"memory.json")

regions = {
  "м. Київ": "led_27_kyiv",
  "Кіровоградська область": "led_17_kyrovogradska",
  "Полтавська область": "led_15_poltavska",
  "Автономна Республіка Крим": "led_24_krym",
  "Закарпатська область": "led_03_zakarpatskya",
  "Донецька область": "led_21_donetska",
  "Черкаська область": "led_16_cherkasska",
  "Миколаївська область": "led_25_mykolaivska",
  "Сумська область": "led_14_sumska",
  "Волинська область": "led_05_volynska",
  "Херсонська область": "led_23_khersonska",
  "Івано-Франківська область": "led_08_ivanofrank",
  "Одеська область": "led_26_odesska",
  "Хмельницька область": "led_09_khmelnytska",
  "Вінницька область": "led_01_vinnytska",
  "Чернігівська область": "led_13_chernigivska",
  "Київська область": "led_11_kyivska",
  "Рівненська область": "led_06_ryvnenska",
  "Тернопільська область": "led_07_ternopilska",
  "Чернівецька область": "led_02_chernivetskya",
  "Луганська область": "led_20_luganska",
  "Львівська область": "led_04_lvivskya",
  "Житомирська область": "led_10_zhytomyrska",
  "Запорізька область": "led_22_zaporizska",
  "Харківська область": "led_19_kharkivska",
  "Дніпропетровська область": "led_18_dnipropertovska",
  "м. Севастополь": "empty"
}

regions_api_map = [
  "Автономна Республіка Крим",
  "Волинська область",
  "Вінницька область",
  "Дніпропетровська область",
  "Донецька область",
  "Житомирська область",
  "Закарпатська область",
  "Запорізька область",
  "Івано-Франківська область",
  "м. Київ",
  "Київська область",
  "Кіровоградська область",
  "Луганська область",
  "Львівська область",
  "Миколаївська область",
  "Одеська область",
  "Полтавська область",
  "Рівненська область",
  "м. Севастополь",
  "Сумська область",
  "Тернопільська область",
  "Харківська область",
  "Херсонська область",
  "Хмельницька область",
  "Черкаська область",
  "Чернівецька область",
  "Чернігівська область",
]

async def send_to_telegram(message: str, subject: str = "__name__", ) -> None:
  """Sends messages via Telegram if TELEGRAM_CHATID and TELEGRAM_TOKEN are both set. Requires "message" parameters and can accept "subject" """
  global TELEGRAM_CHATID, TELEGRAM_TOKEN
  if TELEGRAM_CHATID and TELEGRAM_TOKEN:
    data = {
      "chat_id": f"{TELEGRAM_CHATID}",
      "text": f"{subject}\n{message}"
    }
    try:
      async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",json=data)
      if response.status_code != 200:
        logging.error(f"Telegram bot error! Status: {response.status_code} Body: {response.text}")
    except Exception as err:
      logging.error(f"Error while sending message to Telegram: {err}")

def load_config():
  global HA_URL, HA_TOKEN, API_TOKEN, TELEGRAM_CHATID, TELEGRAM_TOKEN, LED_GROUP_NAME, LED_ENTITY, API_URL
  load_dotenv(verbose=True)
  LED_GROUP_NAME = os.getenv('LED_GROUP_NAME','')
  TELEGRAM_TOKEN = os.getenv('TELEGRAM_CHATID','')
  TELEGRAM_CHATID = os.getenv('TELEGRAM_TOKEN','')
  API_TOKEN = os.getenv('API_TOKEN','')
  API_URL = os.getenv('API_URL','')
  HA_TOKEN = os.getenv('HA_TOKEN','')
  HA_URL = os.getenv('HA_URL','')
  LED_ENTITY = os.getenv('LED_ENTITY','')
  if not API_TOKEN or not HA_TOKEN or not HA_URL or not API_URL or not LED_ENTITY:
    print("ERROR! Some important value like API_TOKEN,HA_TOKEN,HA_URL,API_URL,LED_ENTITY is not configiured in .env file! Can't proceed...")
    logging.error("ERROR! Some important value like API_TOKEN,HA_TOKEN,HA_URL,API_URL,LED_ENTITY is not configiured in .env file! Can't proceed...")
    print("""
Check (create if necessary) .env file with the following parameters, fill in the values with yours:
HA_URL = "http://homeassistant.local"
HA_TOKEN = "adfadsfasfadsfasdfasdfasdfasdfasdf"
TELEGRAM_CHATID = "123123123"
TELEGRAM_TOKEN = "adsfgasfasfasdfasfasdfasdf"
API_TOKEN = "dsfgdsfgdsfgdsfg"
API_URL = "https://api.alerts.in.ua/v1/iot/active_air_raid_alerts_by_oblast.json"
LED_GROUP_NAME = "alertmap_ukraine_all_lights"
LED_ENTITY = "alertmap_esp8266"
    """)
    quit(1)
    if TELEGRAM_TOKEN and TELEGRAM_CHATID:
      asyncio.run(send_to_telegram("ERROR! Some important value like API_TOKEN,HA_TOKEN,HA_URL is not configiured in .env file! Can't proceed...",f"🚒AlarmMap-Ukraine update script:"))

def check_state() -> bool:
  try:
    global LED_GROUP_NAME
    if LED_GROUP_NAME:
      url = os.path.join(HA_URL,'api/states/light.'+LED_GROUP_NAME)
      headers = {
        "Authorization": f"Bearer {os.getenv('HA_TOKEN')}",
        "Content-Type": "application/json"
      }
      response = requests.get(url, headers=headers).json()
      if response["entity_id"] and response.get("entity_id") == "light.alertmap_ukraine_all_lights":
        if response.get("state") == "off":
          return False
        else:
          return True
      else:
        logging.error("Get LED GROUP state response error! real state of the leds may be different from the current alerts state!")
        return True
    else:
      logging.error("LED GROUP is not defined! real state of the leds may be different from the current alerts state!")
      return True
  except Exception as err:
    logging.error(f"check_state() general error: {err}")
    asyncio.run(send_to_telegram(f"check_state() general error: {err}",f"🚒AlarmMap-Ukraine update script:"))  
    return False

def get_day_night() -> int:
  #if not enabled, just return brightness value of the day
  if not DAY_NIGHT_ENABLED:
    return DAY_NIGHT_DAYBRIGHTNESS
  #if enabled
  now = datetime.now().time()
  #if there is night
  if (now >= time(23, 0) or now < time(7, 0)):
    return DAY_NIGHT_NIGHTBRIGHTNESS
  else:
    return DAY_NIGHT_DAYBRIGHTNESS

def set_state(led_id: str, color: list = [0,0,255]):
  """Makes API requests to HomeAssistant and sets a state of every LED"""
  try:
    url_ha = os.path.join(HA_URL,'api/services/light/turn_on')
    headers = {
      "Authorization": f"Bearer {HA_TOKEN}",
      "Content-Type": "application/json"
    }
    data = {
      "entity_id": f"light.{LED_ENTITY}_{led_id}",
      "rgb_color": color,
      "brightness": get_day_night()
    }
    response = requests.post(url_ha, headers=headers, json=data)
    #logging what we've got for debug purpose if DEBUG is enabled in logger
    logging.info(f"set_state() response from HA: {response.text}")
  except Exception as err:
    logging.error(f"set_state() general error: {err}")
    asyncio.run(send_to_telegram(f"set_state() general error: {err}",f"🚒AlarmMap-Ukraine update script:"))

def main():
  """Main function"""
  try:
    load_config()
    global MEMORY_UPDATED
    LEDS_ARE_OK = check_state()
    #initializing memory array
    if os.path.exists(memory_file):
      with open(memory_file, "r", encoding="utf-8") as f:
        memory = f.read()
        MEMORY_UPDATED = True
    logging.info(f"Stored data loaded successfully from {os.path.join(Path(__file__).resolve().parent,'memory.json')}")
    url_api = f"{API_URL}?token={API_TOKEN}"
    headers = {
      "User-Agent": "Hand_written_python_script",
      "Content-Type": "application/json"
    }
    response = requests.get(url_api, headers=headers).json()
    #check response
    if len(response) != len(regions_api_map):
      print(f"Неверная длина ответа: {len(response)} != {len(regions)}")
      raise ValueError(f"Неверная длина ответа: {len(response)} != {len(regions)}")
    #saving new data to future save to file
    new_region_status = ""
    #logging what we've got for debug purpose if DEBUG is enabled in logger
    logging.info(response)
    for region_id,status in enumerate(response,0):
      #if memory table is actual and updated  
      if MEMORY_UPDATED and status == memory[region_id] and LEDS_ARE_OK:
        logging.info(f"Skipping region {regions_api_map[region_id]} and status={memory[region_id]}={status}")
        #saving current status for future save to file.
        new_region_status += status
        continue
      #if memory table is avaliable and some data changed
      elif MEMORY_UPDATED and status != memory[region_id] and LEDS_ARE_OK:
        if status == "A":
          set_state(regions.get(regions_api_map[region_id]),RED)
        elif status == "P":
          set_state(regions.get(regions_api_map[region_id]),YELLOW)
        else:
          set_state(regions.get(regions_api_map[region_id]),GREEN)
        logging.info(f"{regions_api_map[region_id]} status changed to {status}")
        new_region_status += status
      #if memory not available - setting all zones to actual status
      elif not MEMORY_UPDATED or not LEDS_ARE_OK:
        if status == "A":
          set_state(regions.get(regions_api_map[region_id]),RED)
        elif status == "P":
          set_state(regions.get(regions_api_map[region_id]),YELLOW)
        else:
          set_state(regions.get(regions_api_map[region_id]),GREEN)
        logging.info(f"{regions_api_map[region_id]} status changed to {status}")
        new_region_status += status
        delay.sleep(0.5)
    with open(memory_file, "w", encoding="utf-8") as f:
      f.write(new_region_status)
    logging.info(f"Actual data saved successfully to {os.path.join(Path(__file__).resolve().parent,'memory.json')}")
  except Exception as err:
    logging.error(f"main() global error: {err}")
    asyncio.run(send_to_telegram(f"main() global error: {err}",f"🚒AlarmMap-Ukraine update script:"))

if __name__ == "__main__":
  main()
