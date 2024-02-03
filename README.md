TZ-MANAGER created with the assistance of GPT and GitHub Copilot.

Configuration Guide for config.ini
This README provides detailed information on configuring the config.ini file for TZ-MANAGER. Each setting in the config.ini file is crucial for the application's functionality.

Change the name of the config_template.ini file to config.ini.

[Settings] 
API_URL
Description: The URL for Zabbix API interactions.
Format: URL string (e.g., http://example.com/api)
Required: Yes 

API_USER
Description: Username for Zabbix API authentication.
Format: String
Required: Yes

API_PASSWORD
Description: Password for Zabbix API authentication.
Format: String
Required: Yes

BOT_TOKEN
Description: Telegram bot token for messaging and alerts.
Format: String
Required: Yes

CHAT_ID
Description: Telegram chat ID for sending messages.
Format: Numeric/String
Required: Yes

LOGIN_RETRY_INTERVAL
Description: Interval (seconds) between login attempts.
Format: Integer 
Required: Optional (default: 30)

MAIN_LOOP_SLEEP_DURATION
Description: Sleep duration (seconds) for the main loop.
Format: Integer 
Required: Optional (default: 30)

CLEANUP_INTERVAL
Description: Interval (seconds) for cleanup operations.
Format: Integer 
Required: Optional (default: 3600)

MAX_LOGIN_RETRIES
Description: Max login retry attempts.
Format: Integer 
Required: Optional (default: 5)

LOGIN_RETRY_DELAY
Description: Delay (seconds) between retry attempts.
Format: Integer 
Required: Optional (default: 10)

RETENTION_PERIOD
Description: This parameter specifies the duration in seconds for retaining alarms. Alarms that exceed this duration are automatically cleared in each cleaning cycle, ensuring that only recent and relevant alarms are maintained.
Format: Integer 
Required: Optional (default: 86400)

SEND_REMINDER
Description: Flag to enable/disable reminder. 
Format: Boolean (True/False) 
Required: Optional (default: False)

RESEND_THRESHOLD
Description: Threshold (seconds) for resending notifications. 
Format: Integer 
Required: Optional (default: 1800)

USE_TRIGGER_FILTERS
Description: Flag to enable/disable trigger filters.
Format: Boolean (True/False) 
Required: Optional (default: False)

MIN_SEVERITY
Description: Minimum severity level for triggers. (Only valid if USER_TRIGGER_FILTERS is "False")
Format: Integer 
Required: Optional (default: 0)

SEND_RESOLVED_RESTARTS
Description: Flag to send/not send resolved restart notifications.
Format: Boolean (True/False) 
Required: Optional (default: False)

SEND_OLD_RESOLVED
Description: Flag to send/not send old resolved notifications.
Format: Boolean (True/False) 
Required: Optional (default: False)

[GraphSettings]
SEND_GRAPHS
Description: Flag to enable/disable sending graphs. (Only for memory, cpu and disk alarms!)
Format: Boolean (True/False)
Required: Optional (default: True)

LOGIN_URL
Description: The URL for Zabbix WEB interactions.
Format: URL string (e.g., http://example.com/)
Required: Yes 

BASE_URL
Description: The URL for crating image URL from Zabbix WEB.
Format: URL string (e.g., http://example.com/)
Required: Yes

EXECUTABLE_PATH
Description: File path for chromedriver. (For Linux Os)
Format: File path (e.g., /path/to/chromedriver)
Required: Optional (default: /usr/local/bin/chromedriver)

BINARY_LOCATION
Description: File path for google-chrome binary. (For Linux Os)
Format: File path (e.g., /path/to/google-chrome)
Required: Optional (default: /usr/bin/google-chrome)

WIDTH = 1000
Description: Graph image width. 
Format: Integer 
Required: Optional (default: 1000)

HEIGTH = 300
Description: Graph image height. 
Format: Integer 
Required: Optional (default: 300)

[TriggerFilters]
Description: Custom filters for various triggers. (Only valid if USE_TRIGGER_FILTERS is "True") Doesn't support macros!
Format: String, trigger name in Zabbix (e.g., {HOST.NAME} has just been restarted)
Required: Optional, based on application needs.

Example:

filter1 = {HOST.NAME} has just been restarted
filter2 = Zabbix agent on {HOST.NAME} is unreachable for 5 minutes
filter3 = Unavailable by ICMP ping
filter4 = Memory Usage Over Limits %%80 on {HOST.NAME}
filter5 = ICMP ping loss over %%10 on {HOST.NAME}
filter6 = Unavailable by ICMP ping (>5 min.)
filter7 = VMware: Hypervisor is down
filter8 = {HOST.NAME} Rebooted
