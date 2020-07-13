#!/bin/bash

if [ $(id -u) = 0 ]; then
    echo "Shouldn't be run as root. Nothing will be done."
elif [[ $(dpkg -s python3-venv 2>&1) =~ "not installed" ]]; then
    echo "Python 3 virtual environments package (python3-venv) is not installed. Nothing will be done."
else
    BOTFILE="resource-scheduling-telegram-bot.py"
    LOGCONF="setup-files/logrotate.conf"
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
            touch non-git/logs/resource-scheduling-telegram-bot.log
            touch non-git/logrotate.status
            touch non-git/user-configs/TELEGRAM-BOT-TOKEN.txt
            touch non-git/user-configs/AUTHORIZED-TELEGRAM-IDS.txt
            
            # default resources and activities
            if ! [[ -f non-git/user-configs/RESOURCES.txt ]]; then
                echo -e "RES-A\nRES-B\nRES-C\n" > non-git/user-configs/RESOURCES.txt # example resources
            else
                touch non-git/user-configs/RESOURCES.txt
            fi
            if ! [[ -f non-git/user-configs/ACTIVITIES.txt ]]; then
                echo -e "ACT-1\nACT-2\n" > non-git/user-configs/ACTIVITIES.txt # example activities
            else
                touch non-git/user-configs/ACTIVITIES.txt
            fi

            echo "Writing token to appropriate file..."
            echo $token > non-git/user-configs/TELEGRAM-BOT-TOKEN.txt

            echo "Applying custom changes to schedule package..."
            sh setup-files/custom-schedule-lib/apply-schedule-changes.sh

            echo "Extracting startup-script.sh file..."
            cp setup-files/startup-script.sh non-git/
            echo "Updating project path at startup-script.sh file..."
            sed -i "s+prj-path-editable-by-install.sh+$PWD+g" non-git/startup-script.sh
            echo "Updating user at startup-script.sh file..."
            sed -i "s+example-user-editable-by-install.sh+$(id -un)+g" non-git/startup-script.sh
            
            echo "Extracting logrotate.conf file..."
            cp setup-files/logrotate.conf non-git/
            echo "Updating project path at logrotate.conf file..."
            sed -i "s+prj-path-editable-by-install.sh+$PWD+g" non-git/logrotate.conf
            echo "Updating user at logrotate.conf file..."
            sed -i "s+example-user-editable-by-install.sh+$(id -un)+g" non-git/logrotate.conf
            echo "Updating group at logrotate.conf file..."
            sed -i "s+example-group-editable-by-install.sh+$(id -gn)+g" non-git/logrotate.conf
            
            echo "#########################"
            echo "If you want to have your bot executed at boot, remember to add the following line to /etc/rc.local file:"
            echo "sudo -u $(id -un) $PWD/non-git/startup-script.sh &"
            
            echo ""
            echo "Sucessful installation!"
        fi
    fi
fi
