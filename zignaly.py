from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from random import uniform, randint
from time import sleep, time
import requests
from collections import Counter
from selenium.webdriver.common.keys import Keys
from pyvirtualdisplay import Display
import telebot
import json
import configparser

# Randomization Related
MIN_RAND        = 0.64
MAX_RAND        = 1.27

LONG_MIN_RAND   = 4.78
LONG_MAX_RAND = 11.1

# Config path
CONFIG_PATH = "config.ini"

# MCP if no more than any 2 DCA are active
MCP_NUMBER = 15

## MCP if 2 any DCA or one DCA 3 is active
MCP_FIRST_RESTRICTION_NUMBER = 7

# MCP if two 2 DCA or at least one 2 DCA & 3 DCA are active
MCP_SECOND_RESTRICTION_NUMBER = 5

# MCP if two or more 3 DCA are active
MCP_EMERGENCY_RESTRICTION_NUMBER = 3

# URLS
DASHBOARD_URL = "https://zignaly.com/app/dashboard"
DASHBOARD_URL_2 = "https://zignaly.com/app/dashboard/"

PRVIDER_SETTINGS_URL = "https://zignaly.com/app/signalProviders/5fb20a7163709920cb346fc5/settings"

def wait_between(a, b):
    rand=uniform(a, b)
    sleep(rand)

class ZignalyDriver:


  def __init__(self):
    self.config = configparser.ConfigParser()
    self.config.read(CONFIG_PATH)

    options = webdriver.ChromeOptions() 
    options.add_argument('--no-sandbox')
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument('--remote-debugging-port=45447')

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    user_data_dir = self.config.get("selenium", "user_data_dir")
    profile_directory = self.config.get("selenium", "profile_directory")
    chrome_driver_path = self.config.get("selenium", "chrome_driver_path")

    options.add_argument('--user-data-dir='+user_data_dir)
    options.add_argument('--profile-directory='+profile_directory)
    self.driver = webdriver.Chrome(executable_path=chrome_driver_path, options=options)

    self.currect_mcp = 0
    self.currect_dca = {}

    chrome_driver_path = self.config.get("selenium", "chrome_driver_path")

    ## Telebot
    token = self.config.get("telebot", "token")
    self.bot = telebot.TeleBot(token) 
    self.user_id = self.config.get("telebot", "user_id")

  def login(self):
    try:
      wait_between(LONG_MIN_RAND, LONG_MAX_RAND)

      email_input = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH ,'/html/body/div[1]/div[1]/div/div[1]/div[4]/div[2]/form/div/div[1]/div/div/input')))

      pass_input = self.driver.find_element_by_xpath('/html/body/div[1]/div[1]/div/div[1]/div[4]/div[2]/form/div/div[2]/div/div/input')

      # Clear the input
      email_input.send_keys(Keys.CONTROL + "a")
      email_input.send_keys(Keys.DELETE)
      pass_input.send_keys(Keys.CONTROL + "a")
      pass_input.send_keys(Keys.DELETE)

      email = self.config.get("zignaly", "email")
      password = self.config.get("zignaly", "password")

      email_input.send_keys(email)
      pass_input.send_keys(password)

      # 2Captcha service
      service_key = self.config.get("2captcha", "service_key") # 2captcha service key 
      google_site_key = '6LdORtMUAAAAAGLmbf3TM8plIRorVCEc9pVChix8' 
      pageurl = 'https://zignaly.com/app/login/'
      url = "http://2captcha.com/in.php?key=" + service_key + "&method=userrecaptcha&googlekey=" + google_site_key + "&pageurl=" + pageurl 
      resp = requests.get(url)

      if resp.text[0:2] != 'OK': 
          quit('Service error. Error code:' + resp.text) 
      captcha_id = resp.text[3:]

      fetch_url = "http://2captcha.com/res.php?key="+ service_key + "&action=get&id=" + captcha_id

      for _ in range(1, 10):  
          resp = requests.get(fetch_url)
          sleep(60) # wait 60 sec.
          if resp.text[0:2] == 'OK':
              break 
      token = resp.text[3:]
      print(token)

      self.driver.execute_script('var element=document.getElementById("g-recaptcha-response"); element.style.display="";')
      self.driver.execute_script("""
        document.getElementById("g-recaptcha-response").innerHTML = arguments[0]
      """, token)

      wait_between(MIN_RAND, MAX_RAND)

      self.driver.execute_script('___grecaptcha_cfg.clients[0].$.$.callback(\'{}\');'.format(token))

      print("Executed")

      confirm_btn = self.driver.find_element_by_xpath('/html/body/div[1]/div[1]/div/div[1]/div[4]/div[2]/form/div/div[4]/button')
      confirm_btn.click()
      wait_between(LONG_MIN_RAND, LONG_MAX_RAND)
    except:
      self.driver.get('https://zignaly.com/app/login/')
      return self.login()
  
  # Used on dashboard positions page
  def locate_positions(self):

    ## return if page was not loaded correctly
    try:
      # TODO Switch to the  proper update interval
      wait_between(LONG_MIN_RAND, LONG_MAX_RAND)

      self.driver.get(DASHBOARD_URL)

      positions_table = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH ,'/html/body/div[1]/div[1]/div[2]/div[2]/div[2]/div/div[2]/div/div/div[2]/div[2]/div/div/div[3]/table/tbody')))
      positions = positions_table.find_elements_by_xpath(".//tr")
      
      return positions
    except:
      if (self.driver.current_url != DASHBOARD_URL) and (self.driver.current_url != DASHBOARD_URL_2):
        self.login()
      return self.locate_positions()


  # Used on dashboard positions page
  # Counts DCA levels and their respective number only for positions without active tsl
  def parse_activated_dca(self, positions):

    dca = []

    for position in positions:

      for position_raw in position.find_elements_by_xpath(".//td"):

        if position_raw.get_attribute("data-colindex") == "21":
          try:
            tsl = position_raw.find_element_by_xpath(".//div[2]").find_element_by_css_selector("svg")

            # TSL activated, skip counting
            stroke = tsl.get_attribute("stroke")
            if stroke == "#08a441":
              print("Skipped dca with tsl")
              break
          except:
            pass

        if position_raw.get_attribute("data-colindex") == "23":
          dca_targets = position_raw.find_element_by_xpath(".//div[2]").find_elements_by_xpath(".//span")

          for dca_target in dca_targets:
            if dca_target.get_attribute("class") == "targetGreen":
              dca.append(dca_target.text)
    return dict(Counter(dca))
  
  # Used on dashboard positions page
  def get_active_tsl_number(self, positions):

    active_tsl_number = 0

    for position in positions:

      for position_raw in position.find_elements_by_xpath(".//td"):

        if position_raw.get_attribute("data-colindex") == "21":
          try:
            tsl = position_raw.find_element_by_xpath(".//div[2]").find_element_by_css_selector("svg")

            # TSL activated
            stroke = tsl.get_attribute("stroke")
            if stroke == "#08a441":
              print("TSL found")
              active_tsl_number += 1
          except:
            continue

    return active_tsl_number

  def calculate_new_mcp_number(self, new_active_tsl_number, active_dca):

    if active_dca != self.currect_dca:
      print("DCA data changed ", active_dca)
      self.currect_dca = active_dca

    ## 2 DCA 3
    if active_dca.get('3', 0) >= 2:
      new_mcp = MCP_EMERGENCY_RESTRICTION_NUMBER + new_active_tsl_number

    ## 2 DCA 2 or 1 DCA 2 & 1 DCA 3
    elif (active_dca.get('3', 0) >= 1 and active_dca.get('2', 0) >= 1) or (active_dca.get('2', 0) >= 2):
      new_mcp = MCP_SECOND_RESTRICTION_NUMBER + new_active_tsl_number

    ## 2 any DCA or one DCA 3
    elif sum(active_dca.values()) >= 2 or (active_dca.get('3', 0) >= 1):
      new_mcp = MCP_FIRST_RESTRICTION_NUMBER + new_active_tsl_number

    else:
      new_mcp = MCP_NUMBER + new_active_tsl_number

    return new_mcp
    
  # Used on provider settings profile page
  def upgrade_mcp(self, new_mcp):

    self.driver.get(PRVIDER_SETTINGS_URL)

    wait_between(LONG_MIN_RAND, LONG_MAX_RAND)

    if self.driver.current_url.strip() != PRVIDER_SETTINGS_URL:
      print(self.driver.current_url)
      self.login()
      return self.upgrade_mcp(new_mcp)

    try:
      mcp_input = WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.NAME ,'maxPositions')))

      # clear the mcp_input text box
      mcp_input.send_keys(Keys.CONTROL + "a")
      mcp_input.send_keys(Keys.DELETE)

      mcp_input.send_keys(new_mcp)

      confirm_button = self.driver.find_element_by_xpath('/html/body/div[1]/div[1]/div[2]/div[2]/div[2]/div/div[2]/div/div/div/form/div[2]/button')
      confirm_button.click()
      wait_between(LONG_MIN_RAND, LONG_MAX_RAND)

      print("MCP changed to {}", new_mcp)
      self.bot.send_message(self.user_id, 'MCP changed to {}'.format(new_mcp))
      self.bot.send_message(self.user_id, 'DCA data changed: '+json.dumps(self.currect_dca))

    except:
      return self.upgrade_mcp(new_mcp)

def main():

  # Enable this to be able to run on ssh 
  
  # display = Display(visible=0, size=(1280, 1024))
  # display.start()

  zig_driver = ZignalyDriver()

  zig_driver.driver.get(DASHBOARD_URL)

  wait_between(LONG_MIN_RAND, LONG_MAX_RAND)

  if (zig_driver.driver.current_url != DASHBOARD_URL) and (zig_driver.driver.current_url != DASHBOARD_URL_2):
    print(zig_driver.driver.current_url)
    zig_driver.login()
    wait_between(LONG_MIN_RAND, LONG_MAX_RAND)

  while True:
    if (zig_driver.driver.current_url != DASHBOARD_URL) and (zig_driver.driver.current_url != DASHBOARD_URL_2):
      print(zig_driver.driver.current_url)
      zig_driver.login()
      wait_between(LONG_MIN_RAND, LONG_MAX_RAND)

    positions = zig_driver.locate_positions()
    
    new_active_dca_number = zig_driver.parse_activated_dca(positions)
    new_active_tsl_number = zig_driver.get_active_tsl_number(positions)

    new_mcp = zig_driver.calculate_new_mcp_number(new_active_tsl_number, new_active_dca_number)
    
    if new_mcp == 3:
      zig_driver.bot.send_message(zig_driver.user_id, 'Emergency MCP restriction activated, have a look, please.')

    if (new_mcp != zig_driver.currect_mcp):
      zig_driver.upgrade_mcp(new_mcp)

      # Upgrade active mcp number
      zig_driver.currect_mcp = new_mcp

      zig_driver.driver.get(DASHBOARD_URL)

if __name__ == "__main__":
    main()