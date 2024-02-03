import datetime
from datetime import datetime
import time
import logging
from selenium import webdriver

class AlarmManager:
    def __init__(self, send_resolved_restarts, send_reminder , telegram_client, graph_manager, send_graphs, send_old_resolved, reminder_threshold ,logger=None):
        self.sent_alarms = {}
        self.send_resolved_restarts = send_resolved_restarts
        self.send_reminder = send_reminder
        self.telegram_client = telegram_client

        self.graph_manager = graph_manager
        self.send_graphs = send_graphs
        self.send_old_resolved = send_old_resolved
        self.reminder_threshold = reminder_threshold
        self.logger = logger if logger else logging.getLogger(__name__)


    def cleanup_sent_alarms(self, retention_period):
        current_time = time.time()
        removed_count = 0

        for alarm_id in list(self.sent_alarms.keys()):
            if current_time - self.sent_alarms[alarm_id]['last_sent'] > retention_period:
                del self.sent_alarms[alarm_id]
                removed_count += 1

        if removed_count > 0:
            self.logger.info(f"Cleanup: Removed {removed_count} old alarms from cache.")

    def format_duration(self, seconds):
        # Convert seconds to hours, minutes, and remaining seconds
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        seconds = round(seconds)  # Round the seconds to the nearest whole number

        # Convert hours and minutes to integers to remove the decimal point
        hours = int(hours)
        minutes = int(minutes)

        # Create a formatted string
        duration_str = ""
        if hours > 0:
            duration_str += f"{hours} hours "
        if minutes > 0:
            duration_str += f"{minutes} minutes "
        if seconds > 0 or (hours == 0 and minutes == 0):
            # Include seconds if it's the only unit or if there are any seconds
            duration_str += f"{seconds} seconds"

        return duration_str.strip()  # Remove leading/trailing spaces

    def convert_unix_to_standard(self, unix_timestamp):
        # Convert the Unix timestamp to a datetime object
        timestamp = datetime.fromtimestamp(int(unix_timestamp))
        # Format the datetime object to a string in the desired format
        return timestamp.strftime('%Y-%m-%d %H:%M:%S')

    def is_restart_related(self, trigger):
        # Example condition - this is highly dependent on how your triggers are set up
        if 'restart' in trigger['description'].lower():
            return True
        return False
    
    async def process_problem_trigger(self, session, trigger, current_time):
        try:
            alarm_id = trigger['triggerid']
            if 'hosts' in trigger and trigger['hosts'] and all(k in trigger['hosts'][0] for k in ['host', 'hostid']):
                host_info = trigger.get('hosts', [{}])[0]
                host_id = host_info.get('hostid', 'default_host_id')  # Provide a default value
                host_name = host_info.get('host', 'default_host_name')

                if alarm_id not in self.sent_alarms or self.sent_alarms[alarm_id]["status"] == "resolved":
                    alert_time = self.convert_unix_to_standard(trigger['lastchange'])
                    host_ip = await self.zabbix_client.get_host_ip_by_id(session, host_id)  # Use self to access class method
                    problem_message = f"Alarm Triggered at {alert_time} - Host '{host_name}' ({host_ip}): {trigger['description']}"

                    message_sent = await self.telegram_client.send_message(session, problem_message, message_type="ALERT")
                    if message_sent:
                        self.sent_alarms[alarm_id] = {
                            "status": "problem",
                            "message_id": message_sent["message_id"],
                            "last_sent": current_time,
                            "last_remind": current_time,  # Add a last_reminder key with the current time to track when the last reminder was sent
                            "host_ip": host_ip
                        }
                        self.logger.alert(f"Sent Problem Alert: {problem_message}")
                        
                        if self.send_graphs:
                            await self.graph_manager.process_graphs(session, trigger, host_id, alarm_id, reply_id = self.sent_alarms[alarm_id]["message_id"])  #!!!!!

                    else:
                        self.logger.error(f"Failed to send Problem Alert: {problem_message}")
                else:
                    if self.sent_alarms[alarm_id]["status"] == "problem" and current_time - self.sent_alarms[alarm_id]["last_remind"] > self.reminder_threshold:
                        if self.send_reminder:
                            reply_id = self.sent_alarms[alarm_id]["message_id"]
                            
                            reminder_message = f"Problem Continues for {self.format_duration(current_time - self.sent_alarms[alarm_id]['last_sent'])}"
                            message_sent = await self.telegram_client.send_message(session, reminder_message, message_type="REMINDER", reply_to_message_id=reply_id)
                                                                                 
                            if message_sent:                                
                                self.sent_alarms[alarm_id]["last_remind"] = current_time
                                self.logger.alert(f"Sent Problem Reminder: {reminder_message}")                           
                            
                            else:
                                self.logger.error(f"Failed to send Problem Reminder: {reminder_message}")
                    else:    
                        self.logger.info(f"Skipping already sent alert {alarm_id}.")
            else:
                self.logger.error(f"Missing 'host' or 'hostid' key in trigger data for alarm_id {alarm_id}: {trigger}")
                return
        except Exception as e:
                error_message = f"Error in process_problem_trigger : {e}"
                self.logger.error(error_message)
                await self.telegram_client.send_message(session, error_message, message_type="ERROR")
        
    async def process_resolved_trigger(self, session, trigger, current_time):
        try:
            if self.is_restart_related(trigger) and not self.send_resolved_restarts:
                self.logger.info("Resolved restart message not sent due to configuration settings.")
                return
            alarm_id = trigger['triggerid']
            if 'hosts' in trigger and trigger['hosts'] and 'host' in trigger['hosts'][0] and 'hostid' in trigger['hosts'][0]:
                host_id = trigger['hosts'][0]['hostid']
                host_name = trigger['hosts'][0]['host']
                alert_time = self.convert_unix_to_standard(trigger['lastchange'])
                if alarm_id in self.sent_alarms and self.sent_alarms[alarm_id]["status"] == "problem":
                    host_ip = await self.zabbix_client.get_host_ip_by_id(session, host_id)  # Use self to access class method
                    resolved_message = f"Problem Resolved at {alert_time} - Host '{host_name}' ({host_ip}): {trigger['description']}"
                    reply_id = self.sent_alarms[alarm_id]["message_id"]
                    if reply_id:
                        message_sent = await self.telegram_client.send_message(session, resolved_message, message_type="RESOLVED", reply_to_message_id=reply_id)
                        message_id = message_sent.get("message_id", None)
                        if message_id:
                            self.sent_alarms[alarm_id]["status"] = "resolved"
                            self.sent_alarms[alarm_id]["message_id"] = message_sent["message_id"]
                            self.sent_alarms[alarm_id]["last_sent"] = current_time
                            self.logger.resolved(f"Sent Resolved Alert as a reply: {resolved_message}")
                        else:
                            self.logger.error(f"Failed to send Resolved Alert as a reply: {resolved_message}")
                elif alarm_id not in self.sent_alarms:
                    if self.send_old_resolved == False:
                        self.logger.info("Old Resolved message not sent due to configuration settings.")
                        return
                    self.logger.info(f"Resolved alarm {alarm_id} was not previously tracked. Sending new message.")
                    host_ip = await self.zabbix_client.get_host_ip_by_id(session, host_id)  # Use self to access class method
                    resolved_message = f"Problem Resolved at {alert_time} - Host '{host_name}' ({host_ip}): {trigger['description']}"
                    message_sent = await self.telegram_client.send_message(session, resolved_message, message_type="RESOLVED")
                    message_id = message_sent.get("message_id", None)
                    if message_id:
                        self.sent_alarms[alarm_id] = {
                            "status": "resolved",
                            "message_id": message_id,
                            "last_sent": current_time,
                            "last_remind": current_time,  # Also add the last_sent time
                            "host_ip": host_ip
                        }
                        self.logger.resolved(f"Sent Resolved message as new: {resolved_message}")
                    else:
                        self.logger.error(f"Failed to send Resolved message as new: {resolved_message}")
                else:
                    self.logger.info(f"Skipping already sent resolved {alarm_id}.")
            else:
                error_message = f"Missing 'host' or 'hostid' key in trigger data for alarm_id {alarm_id}: {trigger}"
                self.telegram_client.send_message(session, error_message, message_type="ERROR")
                return
        except Exception as e:
                error_message = f"Error in process_resolved_trigger : {e}"
                self.logger.error(error_message)
                await self.telegram_client.send_message(session, error_message, message_type="ERROR")
        
    
        