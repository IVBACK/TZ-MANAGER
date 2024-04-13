import asyncio
import logging
import os
import time
from httpcore import TimeoutException
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service

class ZabbixClient:
    def __init__(self, api_url, user, password, telegram_client, max_login_retries, login_retry_delay, cleanup_interval, use_trigger_filters, 
                 main_loop_sleep_duration, trigger_filters, script_start_time, retention_period, min_severity, login_retry_interval, login_url, 
                 graph_manager, send_graphs, executable_path, binary_location, use_duration_threshold , duration_threshold ,logger=None):
        self.api_url = api_url
        self.user = user
        self.password = password
        self.telegram_client = telegram_client
        self.logger = logger if logger else logging.getLogger(__name__)
        self.token = None
        self.max_login_retries = max_login_retries
        self.login_retry_delay = login_retry_delay
        self.last_cleanup_time = time.time()
        self.cleanup_interval = cleanup_interval
        self.main_loop_sleep_duration = main_loop_sleep_duration
        self.use_trigger_filters = use_trigger_filters
        self.trigger_filters = trigger_filters
        self.script_start_time = script_start_time
        self.retention_period = retention_period
        self.min_severity = min_severity
        self.login_retry_interval = login_retry_interval
        self.login_url = login_url
        self.graph_manager = graph_manager
        self.send_graphs = send_graphs
        self.executable_path = executable_path
        self.binary_location = binary_location
        self.use_duration_threshold = use_duration_threshold
        self.duration_threshold = duration_threshold

           
        
    async def login(self, session):
 
        if self.send_graphs:
            info_message = "Attempting web login..."
            self.logger.info(info_message)
            await self.telegram_client.send_message(session, info_message, message_type="INFO")
            session_cookie = await self.web_login(session, self.user, self.password)
            self.graph_manager.set_session_cookie(session_cookie)

                
        attempt_count = 0

        while attempt_count < self.max_login_retries:
            self.logger.info(f"Attempt {attempt_count + 1} to login to Zabbix API.")
            await self.telegram_client.send_message(session, "Attempting to login to Zabbix API...", message_type="INFO")

            headers = {"Content-Type": "application/json-rpc"}
            payload = {
                "jsonrpc": "2.0",
                "method": "user.login",
                "params": {"username": self.user, "password": self.password},
                "id": 1
            }

            try:
                async with session.post(self.api_url, headers=headers, json=payload) as response:
                    response_data = await response.json()

                    if "result" in response_data:
                        token = response_data["result"]
                        success_message = "Successfully logged in to Zabbix API."
                        self.logger.info(success_message)
                        await self.telegram_client.send_message(session, success_message, message_type="INFO")
                        return token

                    else:
                        error_message = f"Error logging into Zabbix: {response_data.get('error', 'Unknown error')}"
                        self.logger.error(error_message)
                        await self.telegram_client.send_message(session, error_message, message_type="ERROR")

            except Exception as e:
                error_message = f"Error logging into Zabbix: {e}"
                self.logger.error(error_message)
                await self.telegram_client.send_message(session, error_message, message_type="ERROR")

            attempt_count += 1
            if attempt_count < self.max_login_retries:
                self.logger.info(f"Retrying in {self.login_retry_delay} seconds...")
                await asyncio.sleep(self.login_retry_delay)

        self.logger.error("Failed to login to Zabbix after maximum retry attempts.")
        await self.telegram_client.send_message(session, "Failed to login to Zabbix after maximum retry attempts.", message_type="ERROR")
        return None

    async def get_host_ip_by_id(self, session, host_id):
        self.logger.info(f"Fetching IP for host ID: {host_id}")

        # API endpoint and request setup
        headers = {"Content-Type": "application/json-rpc"}
        payload = {
            "jsonrpc": "2.0",
            "method": "hostinterface.get",
            "params": {
                "output": ["ip"],
                "hostids": [host_id],
                "filter": {"type": 1}  
            },
            "auth": self.token,
            "id": 2
        }

        # Performing the API call
        try:
            async with session.post(self.api_url, headers=headers, json=payload) as response:
                response_data = await response.json()
                self.logger.debug(f"Response from Zabbix: {response_data}")

                # Processing the response
                if "result" in response_data and isinstance(response_data["result"], list):
                    if response_data["result"]:
                        host_ip = response_data["result"][0].get("ip", "N/A")
                        self.logger.info(f"Fetched IP for host ID {host_id}")
                        return host_ip
                    else:
                        self.logger.warning(f"No IP address found for host ID {host_id}.")
                        await self.telegram_client.send_message(f"No IP address found for host ID {host_id}.")
                        return "N/A"
                else:
                    if "error" in response_data:
                        error_message = f"Error in response for host ID {host_id}: {response_data['error']}"
                        self.logger.error(error_message)
                        await self.telegram_client.send_message(session, error_message, message_type="ERROR")
                    else:
                        error_message = f"Unexpected response structure for host ID {host_id}: {response_data}"
                        self.logger.error(error_message)
                        await self.telegram_client.send_message(session, error_message, message_type="ERROR")
                    return "N/A"
        except Exception as e:
            error_message = f"Exception occurred while fetching IP for host ID {host_id}: {e}"
            self.logger.error(error_message)
            await self.telegram_client.send_message(error_message)
            return "N/A"
        
    async def get_item_id(self, session, host_id, item_name):
        headers = {"Content-Type": "application/json-rpc"}
        payload = {
            "jsonrpc": "2.0",
            "method": "item.get",
            "params": {
                "output": ["itemid", "name"],
                "hostids": host_id,
                "search": {"name": item_name},
                "sortfield": "name"
            },
            "auth": self.token,
            "id": 1
        }

        async with session.post(self.api_url, headers=headers, json=payload) as response:
            response_data = await response.json()

        # Extract item_id for the specified item name
        for item in response_data.get('result', []):
            if item_name.lower() in item.get('name', '').lower():
                self.logger.info(f"Found item ID for {item_name}: {item.get('itemid')}")
                return item.get('itemid')

        self.logger.info(f"No item found for name {item_name} on host ID {host_id}")
        return None
    
    async def get_all_items(self, session, host_id):
        headers = {"Content-Type": "application/json-rpc"}
        payload = {
            "jsonrpc": "2.0",
            "method": "item.get",
            "params": {
                "output": ["itemid", "name"],
                "hostids": host_id
            },
            "auth": self.token,
            "id": 1
        }
        async with session.post(self.api_url, headers=headers, json=payload) as response:
            response_data = await response.json()
            return response_data.get('result', [])

    async def fetch_and_distribute_triggers(self, session,trigger_filter=None):

        while True:
            current_time = time.time()
            if current_time - self.last_cleanup_time > self.cleanup_interval:
                self.alarm_manager.cleanup_sent_alarms(self.retention_period)
                self.last_cleanup_time = current_time

            if self.token is None:
                self.token = await self.login(session)
                self.graph_manager.set_token(self.token)
                if self.token is None:
                    await asyncio.sleep(self.login_retry_interval)
                    continue

            try:
                if self.use_trigger_filters:
                    for trigger_filter in self.trigger_filters:
                        self.logger.info("////////////////////////////////////////////////////////////")
                        problem_triggers = await self.fetch_triggers(session, "1", trigger_filter, use_duration_threshold=self.use_duration_threshold, duration_threshold=self.duration_threshold)
                        for trigger in problem_triggers:
                            await self.alarm_manager.process_problem_trigger(session, trigger, current_time)

                        resolved_triggers = await self.fetch_triggers(session, "0", trigger_filter)
                        for trigger in resolved_triggers:
                            await self.alarm_manager.process_resolved_trigger(session, trigger, current_time)
                else:
                    #Fetch all triggers without filter but severity
                    self.logger.info("////////////////////////////////////////////////////////////")
                    problem_triggers = await self.fetch_triggers(session, "1", min_severity=self.min_severity, use_duration_threshold=self.use_duration_threshold, duration_threshold=self.duration_threshold)
                    for trigger in problem_triggers:
                        await self.alarm_manager.process_problem_trigger(session, trigger, current_time)

                    resolved_triggers = await self.fetch_triggers(session, "0", min_severity=self.min_severity)
                    for trigger in resolved_triggers:
                        await self.alarm_manager.process_resolved_trigger(session, trigger, current_time)
                                        

            except Exception as e:
                error_message = f"Error in fetch_and_distribute_triggers : {e}"
                self.logger.error(error_message)
                await self.telegram_client.send_message(session, error_message, message_type="ERROR")

                self.logger.info(f"Sleeping for {self.main_loop_sleep_duration} seconds after error...")
                await asyncio.sleep(self.main_loop_sleep_duration)

            self.logger.info("////////////////////////////////////////////////////////////")  
            self.logger.info("---------------------------------------------------------------------")
            self.logger.info(f"Cycle completed, sleeping for {self.main_loop_sleep_duration} seconds...")
            self.logger.info("---------------------------------------------------------------------")
            await asyncio.sleep(self.main_loop_sleep_duration)


    async def fetch_triggers(self, session, trigger_state, trigger_filter=None, min_severity=None, use_duration_threshold=None, duration_threshold=None):
        fetching_type = "PROBLEM" if trigger_state == "1" else "RESOLVED"
        headers = {"Content-Type": "application/json-rpc"}
        
        MAX_SEVERITY_LEVEL = 5

        # Base parameters for the payload
        params = {
            "output": ["description", "priority", "triggerid", "lastchange"],
            "expandDescription": 1,
            "selectHosts": ["host", "hostid"],
            "sortfield": "lastchange",
            "sortorder": "DESC",
            "lastChangeSince": int(self.script_start_time),
            "monitored": True,
            "active": True,
            "filter": {"value": trigger_state}
        }

        if use_duration_threshold:
            threshold = int(time.time()) - (duration_threshold * 60) 
            params["lastChangeTill"] = threshold  

        # Apply trigger_filter or min_severity
        if trigger_filter is not None:
            params["filter"].update(trigger_filter)
        elif min_severity is not None:
            if min_severity > MAX_SEVERITY_LEVEL:
                self.logger.warning(f"min_severity ({min_severity}) is higher than maximum severity level ({MAX_SEVERITY_LEVEL}). Adjusting to maximum.")
                min_severity = MAX_SEVERITY_LEVEL
            severity_range = list(range(min_severity, MAX_SEVERITY_LEVEL + 1))
            params["filter"]["priority"] = severity_range

        payload = {
            "jsonrpc": "2.0",
            "method": "trigger.get",
            "params": params,
            "auth": self.token,
            "id": 3
        }

        async with session.post(self.api_url, headers=headers, json=payload) as response:
            response_data = await response.json()

            if "error" in response_data:
                error_message = f"Error fetching {fetching_type} triggers from Zabbix: {response_data['error']}"
                self.logger.error(error_message)
                await self.telegram_client.send_message(session, error_message, message_type="ERROR")
                return []
            else:
                trigger_count = len(response_data['result'])
                    
                if trigger_filter is not None:                   
                    self.logger.info(f"Found {trigger_count} {fetching_type} triggers from Zabbix with {trigger_filter} filter.")
                else:
                    if use_duration_threshold:               
                        self.logger.info(f"Found {trigger_count} {fetching_type} triggers from Zabbix with min severity {min_severity} and min duration threshold {duration_threshold} minutes.")
                    else:
                        self.logger.info(f"Found {trigger_count} {fetching_type} triggers from Zabbix with min severity {min_severity}.")
                return response_data.get("result", [])
                 

    async def web_login(self, session, username, password):

        chrome_options = Options()
        chrome_options.binary_location = self.binary_location  
        chrome_options.add_argument("--headless")  # Run Chrome in headless mode
        chrome_options.add_argument("--no-sandbox")  # Sandbox requires a GUI
        chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems


        if os.name == 'posix':
            # Correct way to set executable path in Selenium 4
            service = Service(executable_path=self.executable_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            driver = webdriver.Chrome(options=chrome_options)

        try:
            driver.get(self.login_url)

            # Wait for the username field to be present
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, 'name'))
            )
            
            # Fill the username and password and submit the form
            driver.find_element(By.NAME, 'name').send_keys(username)
            driver.find_element(By.NAME, 'password').send_keys(password)
            driver.find_element(By.NAME, 'enter').click()

            # Wait for login to complete, check for a known element after login
            # Adjust the element and timeout according to your application
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "page-title-general"))
            )

            # Check if login was successful by verifying if the 'zbx_sessionid' cookie is set
            for cookie in driver.get_cookies():
                if cookie['name'] == 'zbx_session':
                    info_message = "Web login successful."
                    self.logger.info(info_message)
                    await self.telegram_client.send_message(session, info_message, message_type="INFO")
                    return cookie['value']

            error_message = "Web login failed: 'zbx_session' cookie not found"
            self.logger.error(error_message)
            await self.telegram_client.send_message(session, error_message, message_type="ERROR")
            return None

        except TimeoutException:
            error_message = "Timeout occurred during web login"
            self.logger.error(error_message)
            await self.telegram_client.send_message(session, error_message, message_type="ERROR")
            return None
        except NoSuchElementException:
            error_message = "Required element not found during web login"
            self.logger.error(error_message)
            await self.telegram_client.send_message(session, error_message, message_type="ERROR")
            return None
        finally:
            # Close the Chrome driver
            driver.quit()

        
        
        
    

        