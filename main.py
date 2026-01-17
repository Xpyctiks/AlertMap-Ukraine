#!/usr/local/bin/python3

import requests,logging,time,asyncio,httpx,os,json
from pathlib import Path
from dotenv import load_dotenv

HA_URL = HA_TOKEN = TELEGRAM_CHATID = TELEGRAM_TOKEN = ""
GREEN = [0, 255, 0]
RED = [255, 0, 0]
YELLOW = [255, 255, 0]
MEMORY_UPDATED = False
logging.basicConfig(filename=os.path.join(Path(__file__).resolve().parent,"log.txt"),level=logging.ERROR,format='%(asctime)s - Alertmap-Ukraine - %(levelname)s - %(message)s',datefmt='%d-%m-%Y %H:%M:%S')

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
}

memory_example = {
  region: {
    "district": False
  }
  for region in regions
}

#loading some secrets
load_dotenv()

async def send_to_telegram(message: str, subject: str = "__name__", ) -> None:
  """Sends messages via Telegram if TELEGRAM_CHATID and TELEGRAM_TOKEN are both set. Requires "message" parameters and can accept "subject" """
  if TELEGRAM_CHATID and TELEGRAM_TOKEN:
    headers = {
      'Content-Type': 'application/json'
    }
    data = {
      "chat_id": f"{TELEGRAM_CHATID}",
      "text": f"{subject}\n{message}"
    }
    try:
      async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
          f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
          headers=headers,
          json=data
        )
      print(response.status_code)
      if response.status_code != 200:
        logging.error("error", f"Telegram bot error! Status: {response.status_code} Body: {response.text}")
    except Exception as err:
      logging.error(f"Error while sending message to Telegram: {err}")

def set_state(led_id: str, color: list = [0,0,255]):
  """Makes API requests to HomeAssistant and sets a state of every LED"""
  try:
    url_ha = os.getenv('HA_URL')
    headers = {
      "Authorization": f"Bearer {os.getenv('HA_TOKEN')}",
      "Content-Type": "application/json"
    }
    data = {
      "entity_id": f"light.alertmap_esp8266_{led_id}",
      "rgb_color": color,
      "brightness": 255
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
    global MEMORY_UPDATED
    #initializing memory array. If it is not exists - we are getting from example one
    if not os.path.exists(os.path.join(Path(__file__).resolve().parent,"memory.json")):
      memory = memory_example
      logging.info(f"Config file with memory.array CREATED from the example.")
    else:
      with open(os.path.join(Path(__file__).resolve().parent,"memory.json"), "r", encoding="utf-8") as f:
        memory = json.load(f)
        MEMORY_UPDATED = True
    logging.info(f"Config file with memory.array loaded successfully from {os.path.join(Path(__file__).resolve().parent,'memory.json')}")
    url_api = "https://jaam.net.ua/alerts_statuses_v1.json"
    headers = {
      "User-Agent": "Hand_written_python_script",
      "Content-Type": "application/json"
    }
    data = requests.get(url_api, headers=headers).json()
    #logging what we've got for debug purpose if DEBUG is enabled in logger
    logging.info(data)
    if data["version"]:
      #start parsing data from API
      for id, name in enumerate(regions,1):
        #if memory table is actual and updated
        if MEMORY_UPDATED and memory[name]["enabled"] == data["states"][name]["enabled"] and data["states"][name]["district"] == memory[name]["district"]:
          logging.info(f"Skipping changing state of {name}")
          continue
        #if there is alarm and not District
        if data["states"][name]["enabled"]: #$and not data["states"][name]["district"]:
          logging.info(f"{regions.get(name)}=True and District=False has set to Red")
          memory[name]["enabled"] = True
          memory[name]["district"] = False
          set_state(regions.get(name),RED)
        #if Partitial alarm(disabled, waiting for the new API access)
        # elif data["states"][name]["enabled"] and data["states"][name]["district"]:
        #     memory[name]["enabled"] = True
        #     memory[name]["district"] = True
        #     logging.info(f"{regions.get(name)}=True and District=True has set to Yellow")
        #     set_state(regions.get(name),YELLOW)
        #if no alarm
        else:
          memory[name]["enabled"] = False
          memory[name]["district"] = False
          logging.info(f"{regions.get(name)}=False and set to Green")
          set_state(regions.get(name),GREEN)
        logging.error(f"Data changed for: {name}")
        time.sleep(0.5)
      logging.info("Data updated")
      with open(os.path.join(Path(__file__).resolve().parent,"memory.json"), "w", encoding="utf-8") as f:
          json.dump(memory, f, ensure_ascii=False, indent=2)
          logging.info(f"Config file with memory.array saved successfully to {os.path.join(Path(__file__).resolve().parent,'memory.json')}")
    else:
        logging.error("Some error during getting JSON from API and parsing")
        asyncio.run(send_to_telegram("Some error during getting JSON from API and parsing",f"🚒AlarmMap-Ukraine update script:"))
  except Exception as err:
    logging.error(f"main() global error: {err}")
    asyncio.run(send_to_telegram(f"main() global error: {err}",f"🚒AlarmMap-Ukraine update script:"))

if __name__ == "__main__":
  main()
