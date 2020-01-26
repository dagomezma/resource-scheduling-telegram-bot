#!/bin/bash

if [[ $(dpkg -s python3-venv 2>&1) =~ "not installed" ]]; then
    echo "Python 3 virtual environments package (python3-venv) is not installed. Nothing will be done."
else
    BOTFILE=resource-scheduling-telegram-bot.py
    LOGCONF=logrotate.conf
    if ! [[ -f "$BOTFILE" && -f "$LOGCONF" ]]; then
        echo "Not currently in schedule-bot folder. Nothing will be done."
    else
        echo "##################################################################"
    	echo "Refer your telegram TOKEN here (leave empty to quit)."
        echo "##################################################################"
        echo -n "Token: "
        read token
	if ! [ -z "$token" ]; then # if not empty
	    echo "Beginning creation of python3 virtual envirnoment..."
            python3 -m venv non-git/bot-environment
            source non-git/bot-environment/bin/activate
            pip install -r requirements.txt

	    echo "Writing default bot configurations..."
            mkdir -p non-git/logs
            mkdir -p non-git/user-configs
            echo -e "RES-A\nRES-B\nRES-C\n" > non-git/user-configs/RESOURCES.txt # example resources
            echo -e "ACT-1\nACT-2\n" > non-git/user-configs/ACTIVITIES.txt # example activities
            touch non-git/user-configs/TELEGRAM-BOT-TOKEN.txt
            touch non-git/user-configs/AUTORIZED-TELEGRAM-IDS.txt

	    echo "Writing token to appropriate file..."
            echo $token > non-git/user-configs/TELEGRAM-BOT-TOKEN.txt

	    echo "Applying custom changes to schedule package..."
            sh custom-schedule-lib/apply-schedule-changes.sh

            echo "Updating bot path at logrotate.conf...." 
            sed -i "s+bot-path+$PWD+g" logrotate.conf
        fi
    fi
fi
