#!/bin/bash
# This script will be automatically copied to non-git/ folder and modified with aprropiate path
# It is meant to be run at startup by putting the following command at /etc/rc.local:
# sudo -u example-user-editable-by-install.sh prj-path-editable-by-install.sh/non-git/startup-script.sh &

project_path="prj-path-editable-by-install.sh"

cd $project_path
source "$project_path/non-git/bot-environment/bin/activate"
nohup python3 "$project_path/resource-scheduling-telegram-bot.py" >> "$project_path/non-git/logs/resource-scheduling-telegram-bot.log" 2>&1 &
while true; do logrotate "$project_path/non-git/logrotate.conf" -s "$project_path/non-git/logrotate.status"; sleep 3600; done

# In order to find out which process numbers have been assignated (in case you want to kill resource-scheduling-telegram-bot processes):
# $ ps aux | grep telegram-bot
