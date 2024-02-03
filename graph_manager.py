import time
from selenium import webdriver

class GraphManager:
    def __init__(self, api_url, base_url, telegram_client, zabbix_client, width, height, logger):
        self.session_cookie = None
        self.api_url = api_url
        self.base_url = base_url
        self.telegram_client = telegram_client
        self.zabbix_client = zabbix_client
        self.width = width
        self.height = height
        self.token = None
        self.logger = logger


    def set_session_cookie(self, session_cookie):
        self.session_cookie = session_cookie

    def get_session_cookie(self):
        return self.session_cookie
    
    def set_token(self, token):
        self.token = token


    def is_related_to(self, trigger, keywords):
        # Check if any of the keywords are in the trigger's description
        trigger_description = trigger['description'].lower()
        for keyword in keywords:
            if keyword.lower() in trigger_description:
                return True

        return False


    async def get_graph_id(self, session, host_id, item_name):
        headers = {"Content-Type": "application/json-rpc"}

        # Base parameters for the payload
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
                self.logger.info(f"Found {item_name} item ID: {item.get('itemid')}")
                return item.get('itemid')

        self.logger.info(f"No {item_name} item found for host ID: {host_id}")
        return None
    
    
    async def fetch_graph_image(self, session, itemid):
        # Replace with your Zabbix frontend URL
        # Note that URL parameters are now using relative time strings and are URL-encoded
        graph_url = f"{self.base_url}/zabbix/chart.php?from=now-1h&to=now&itemids%5B0%5D={itemid}&width={self.width}&height={self.height}&type=0"
        cookies = {'zbx_session': self.session_cookie}

        # Generate a unique file name
        timestamp = int(time.time())
        file_name = f"item_graph_{itemid}_{timestamp}.png"

        try:
            async with session.get(graph_url, cookies=cookies) as response:
                if response.status == 200:
                    # Read the content of the response and save it as an image file
                    graph_image = await response.read()
                    with open(file_name, "wb") as f:
                        f.write(graph_image)
                    return file_name
                else:
                    error_message = f"Failed to fetch item graph image for itemid: {itemid}, Status: {response.status}"
                    self.logger.error(error_message)
                    await self.telegram_client.send_message(session, error_message, message_type="ERROR")
                    return None
        except Exception as e:
            error_message = f"Error fetching item graph image: {e}"
            self.logger.error(error_message)
            await self.telegram_client.send_message(session, error_message, message_type="ERROR")
            return None
        

    async def process_graphs(self, session, trigger, host_id, alarm_id, reply_id):
        memory_keywords = ['memory usage', 'ram', 'out of memory']
        if self.is_related_to(trigger, memory_keywords):
            item_id = await self.zabbix_client.get_item_id(session, host_id, "Memory Usage(%)")                        
            response = await self.fetch_graph_image(session, item_id)
            if response is not None:
                result = await self.telegram_client.send_graph_image(session, response,reply_to_message_id=reply_id)
                if result:
                    self.logger.info(f"Sent graph image for alarm {alarm_id}")
                else:
                    error_message = f"Failed to send graph image for MEMORY alarm {alarm_id}"
                    self.telegram_client.send_message(session, error_message, message_type="ERROR")
            else:
                error_message = f"Failed to retrieve graph image for MEMORY alarm {alarm_id}"
                self.telegram_client.send_message(session, error_message, message_type="ERROR")

        cpu_keywords = ['processor', 'cpu usage', 'process']
        if self.is_related_to(trigger, cpu_keywords):
            item_id = await self.get_graph_id(session, host_id, "CPU Utilization(Percent)")
            response = await self.fetch_graph_image(session, item_id)                        
            if response is not None:
                result = await self.telegram_client.send_graph_image(session, response,reply_to_message_id=reply_id)
                if result:
                    self.logger.info(f"Sent graph image for alarm {alarm_id}")
                else:
                    error_message = f"Failed to send graph image for CPU alarm {alarm_id}"
                    self.telegram_client.send_message(session, error_message, message_type="ERROR")
            else:
                error_message = f"Failed to retrieve graph image for CPU alarm {alarm_id}"
                self.telegram_client.send_message(session, error_message, message_type="ERROR")

        disk_keywords = ['space', 'datastore', 'lun']
        if self.is_related_to(trigger, disk_keywords):
            # Tokenize the trigger description
            trigger_tokens = trigger['description'].lower().split()

            # Fetch all items for the host
            all_items = await self.zabbix_client.get_all_items(session, host_id)

            # Initialize variables to store the best matching item and its score
            best_matching_item_id = None
            best_matching_score = 0

            for item in all_items:
                if "percentage" in item['name'].strip().lower():
                    item_name_tokens = item['name'].lower().split()

                    # Calculate the relevance score (count of common tokens)
                    score = len(set(trigger_tokens) & set(item_name_tokens))

                    # Check if the current item has a higher score
                    if score > best_matching_score:
                        best_matching_item_id = item['itemid']
                        best_matching_score = score

            # If a matching item is found, fetch and send the graph image
            if best_matching_item_id:
                response = await self.fetch_graph_image(session, best_matching_item_id)
                if response is not None:
                    result = await self.telegram_client.send_graph_image(session, response, reply_to_message_id=reply_id)
                    if result:
                        self.logger.info(f"Sent graph image for disk alarm {alarm_id}")
                    else:
                        error_message = f"Failed to send graph image for disk alarm {alarm_id}"
                        await self.telegram_client.send_message(session, error_message, message_type="ERROR")
                else:
                    error_message = f"Failed to retrieve graph image for disk alarm {alarm_id}"
                    await self.telegram_client.send_message(session, error_message, message_type="ERROR")
            else:
                error_message = f"No matching disk item found for alarm {alarm_id}"
                await self.telegram_client.send_message(session, error_message, message_type="ERROR")

        
