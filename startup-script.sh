#!/bin/bash
# This script is meant to be run at startup by putting the following command at /etc/rc.local:
# sudo -u example-user /home/example-user/resource-scheduling-telegram-bot/startup-script.sh &

project_path="prj-path"

cd $project_path
source "$project_path/non-git/bot-environment/bin/activate"
nohup python3 "$project_path/resource-scheduling-telegram-bot.py" >> "$project_path/non-git/logs/resource-scheduling-telegram-bot.log" 2>&1 &
while true; do logrotate "$project_path/logrotate.conf" -s "$project_path/non-git/logrotate.status"; sleep 3600; done

# In order to find out which process numbers have been assignated (in case you want to kill gersBot processes):
# $ ps aux | grep telegram-bot
