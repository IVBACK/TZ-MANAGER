import asyncio
import os
import urllib.parse
import logging
import aiohttp
from selenium import webdriver

class TelegramClient:
    def __init__(self, bot_token, chat_id, logger=None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.logger = logger if logger else logging.getLogger(__name__)
        self.image_directory = os.getcwd()

    async def send_message(self, session, message, message_type="ALERT", reply_to_message_id=None):
        try:
            # Prefix the message based on its type
            if message_type == "ERROR":
                message = f"🚨 Error: {message}"
            elif message_type == "INFO":
                message = f"ℹ️ Info: {message}"
            elif message_type == "ALERT":
                message = f"⚠️ {message}"
            elif message_type == "RESOLVED":
                message = f"✅ {message}"
            elif message_type == "REMINDER":  # New message type
                message = f"⏰ Reminder: {message}"

            # Format the message as HTML
            html_message = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
            # URL encode the HTML message
            encoded_message = urllib.parse.quote(html_message)
            
            send_text = f'https://api.telegram.org/bot{self.bot_token}/sendMessage?chat_id={self.chat_id}&parse_mode=HTML&text={encoded_message}'
            
            if reply_to_message_id:
                send_text += f'&reply_to_message_id={reply_to_message_id}'

            # Make the request to the Telegram API
            async with session.get(send_text) as response:
                response_data = await response.json()
                if response_data.get("ok"):
                    return response_data.get("result")
                elif response_data.get("error_code") == 429:
                    retry_after = response_data.get("parameters", {}).get("retry_after", 60)
                    self.logger.info(f"Rate limit hit, retrying after {retry_after} seconds")
                    await asyncio.sleep(retry_after)  # Wait before retrying
                    return await self.send_message(session, message, message_type, reply_to_message_id)  # Recursively retry sending the message
                else:
                    self.logger.error(f"Error sending Telegram message: {html_message} /// Response: {response_data}")
                    return None
        except Exception as e:
            self.logger.error(f"Error sending Telegram message: {html_message} /// Exception: {e}")
            return None
        
    async def send_graph_image(self, session, file_name, reply_to_message_id):
        file_path = os.path.join(self.image_directory, file_name)

        try:
            with open(file_path, 'rb') as file:
                data = aiohttp.FormData()
                data.add_field('chat_id', self.chat_id)
                data.add_field('photo', file, filename=file_name)
                data.add_field('reply_to_message_id', str(reply_to_message_id))

                async with session.post(f'https://api.telegram.org/bot{self.bot_token}/sendPhoto', data=data) as response:
                    if response.status == 200:
                        # Successfully sent the image, now delete it
                        try:
                            os.remove(file_path)
                            self.logger.info(f"Deleted file: {file_name}")
                        except OSError as e:
                            self.logger.error(f"Error deleting file {file_name}: {e}")
                        return True
                    else:
                        self.logger.error(f"Failed to send image. Status: {response.status}")
                        return False
        except Exception as e:
            self.logger.error(f"Error opening or sending file {file_name}: {e}")
            return False