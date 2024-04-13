#!/usr/bin/env python3
import asyncio
import time
from aiohttp import ClientSession
from config_manager import ConfigManager
from graph_manager import GraphManager
from logger_manager import LoggerManager
from telegram_client import TelegramClient
from zabbix_client import ZabbixClient
from alarm_manager import AlarmManager
from selenium import webdriver

class MonitoringApplication:
    def __init__(self):
        self.config_manager = ConfigManager('config.ini')
        self.logger_manager = LoggerManager('logs.log')
        settings = self.config_manager.get_settings()
        trigger_filters = self.config_manager.get_trigger_filters()

        self.logger = self.logger_manager.logger
        self.telegram_client = TelegramClient(settings['BOT_TOKEN'], settings['CHAT_ID'], logger=self.logger)

        # Initialize GraphManager without zabbix_client
        graph_settings = self.config_manager.get_graph_settings()
        self.graph_manager = GraphManager(
            api_url=settings['API_URL'],
            base_url=graph_settings['BASE_URL'], 
            telegram_client=self.telegram_client,
            width=int(graph_settings['WIDTH']),
            height=int(graph_settings['HEIGTH']), 
            zabbix_client=None,  # Initially set to None
            logger=self.logger
        )

        # Initialize ZabbixClient with the partially initialized GraphManager
        self.zabbix_client = ZabbixClient(
            api_url=settings['API_URL'],
            user=settings['API_USER'],
            password=settings['API_PASSWORD'],
            telegram_client=self.telegram_client,
            max_login_retries=int(settings['MAX_LOGIN_RETRIES']),
            login_retry_delay=int(settings['LOGIN_RETRY_DELAY']),
            cleanup_interval=int(settings['CLEANUP_INTERVAL']),
            use_trigger_filters=settings.get('USE_TRIGGER_FILTERS', 'True').lower() == 'true',
            main_loop_sleep_duration=int(settings['MAIN_LOOP_SLEEP_DURATION']),
            trigger_filters=trigger_filters,
            script_start_time=time.time(),
            retention_period=int(settings['RETENTION_PERIOD']),
            min_severity=int(settings['MIN_SEVERITY']),
            login_retry_interval=int(settings['LOGIN_RETRY_INTERVAL']),
            login_url=graph_settings['LOGIN_URL'],
            graph_manager=self.graph_manager,
            send_graphs=graph_settings.get('SEND_GRAPHS', 'True').lower() == 'true',
            executable_path=graph_settings['EXECUTABLE_PATH'],
            binary_location=graph_settings['BINARY_LOCATION'],
            use_duration_threshold=settings.get('USE_DURATION_THRESHOLD', 'True').lower() == 'true',
            duration_threshold=int(settings['DURATION_THRESHOLD']),
            logger=self.logger
        )

        # Now, update the GraphManager with the fully initialized ZabbixClient
        self.graph_manager.zabbix_client = self.zabbix_client
        self.graph_manager.session_cookie = self.zabbix_client

        # Initialize AlarmManager
        self.alarm_manager = AlarmManager(
            send_resolved_restarts=settings.get('SEND_RESOLVED_RESTARTS', 'True').lower() == 'true', 
            send_reminder=settings.get('SEND_REMINDER', 'True').lower() == 'true',
            telegram_client=self.telegram_client, 
            reminder_threshold=int(settings['REMINDER_THRESHOLD']), 
            graph_manager=self.graph_manager,
            send_old_resolved = settings.get('SEND_OLD_RESOLVED', 'True').lower() == 'true',
            send_graphs=graph_settings.get('SEND_GRAPHS', 'True').lower() == 'true',
            logger=self.logger
        )

        # Pass dependencies to AlarmManager and ZabbixClient
        self.alarm_manager.zabbix_client = self.zabbix_client
        self.zabbix_client.alarm_manager = self.alarm_manager
        

    async def run(self):
        try:
            async with ClientSession() as session:
                await self.telegram_client.send_message(session, "TZ-MANAGER started.", message_type="INFO")
                await self.zabbix_client.fetch_and_distribute_triggers(session)

        except Exception as e:
            error_message = f"Unexpected error occurred: {str(e)}"
            self.logger.error(error_message)
            await self.telegram_client.send_message(session, error_message, message_type="ERROR")
            # Optionally, re-raise the exception or handle it as needed
            raise

if __name__ == "__main__":
    app = MonitoringApplication()
    asyncio.run(app.run())