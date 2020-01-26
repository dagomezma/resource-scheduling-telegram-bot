#!/bin/bash
# This script is meant to be run at startup by putting the following command at /etc/rc.local:
# sudo -u example-user /home/example-user/resource-scheduling-telegram-bot/startup-script.sh &

bot_path="/home/example-user/resource-scheduling-telegram-bot"

cd $bot_path
source "$bot_path/bot-environment/bin/activate"
nohup python3 "$bot_path/resource-scheduling-telegram-bot.py" >> "$bot_path/non-git/logs/resource-scheduling-telegram-bot.log" 2>&1 &
while true; do logrotate "$bot_path/logrotate.conf" -s "$bot_path/non-git/logrotate.status"; sleep 3600; done

# In order to find out which process numbers have been assignated (in case you want to kill gersBot processes):
# $ ps aux | grep telegram-bot