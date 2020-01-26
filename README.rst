=================
Table of contents
=================

- `Introduction`_

- `Features`_

- `Bot Commands`_

- `Installing (GNU-Linux, Debian-like)`_

  #. `Using Git`_

  #. `Downloading tar`_

  #. `Finishing setup`_

  #. `Configure it`_

- `Running at OS start-up (GNU-Linux)`_

- `License`_

============
Introduction
============

This resource-scheduling-telegram-bot is a libre software telegram bot written in Python which you can use in your organization or group to manage resource scheduling, i.e. review and assign turns to a group of resources among a group of people.

Although this bot could be used for any similar purpose, it was created with user-accesed computing resources in mind, as well as with working hours limitations in mind. Because of this, the possibility of specifying beginning-of-night and end-of-night hours is not only there but turned on by default, this mindset made possible to schedule resources such as a computer with high processing capabilities to be left with some simulations for a complete night and be checked and be available for other users the next morning. Modifications to this behaviour are possible with a few changes within the code.

This bot works in a first-come-first-served manner (no further authorization required), if your organization/group is ok with this, this bot is for you.

An instance of this bot is not readily available to the public as use-cases for a bot like this are expected to differ greatly between implementations (list of resources, list of authorized users, etc.), as well as to preserve possibly private data from potential users, such as telegram profiles and resource names. Potential users are expected to install and run their own copy of this software. I may implement an example-scheduling-bot in the future if this project shows some response.

============
Features
============

- Interval-driven scheduling.
- Night hours (non-working hours) are managed as a sole chunk by default.
- Easy access for users.
- Easy Telegram ID blocking system (plain text file).
- Use of sqlite for automated managing of users and turns.
- Custon non-git folder required so sensitive data is not accidentally uploaded to a repository.

============
Bot Commands
============

.. list-table:: List of commands
   :widths: 15 38 47
   :header-rows: 1

   * - Command
     - Description
     - Usage
   * - sched
     - Evince current schedule found in database, for selected Resource
     - | /sched <resource>
       | e.g. /sched RESOURCE-1
   * - request
     - | Request a turn. A list of slots available according to project will be shown with (+interval) shown as the proper duration. If [interval] is not declared by user, a default value will be shown in (+interval).
       | 
       | Valid float intervals: Any multiple of 0.5 (hours)
       | Valid string intervals: NIGHT
     - | /request <resource> <activity> [interval]
       | e.g. /request RESOURCE-1 ACTIVITY-1
       | e.g. /request RESOURCE-1 ACTIVITY-2 1.5
       | e.g. /request RESOURCE-1 ACTIVITY-3 NIGHT
   * - rm
     - Request removal of a turn. You'll be able to select which turn to remove from a list of appropriate turns, if any.
     - /rm
   * - myTurns
     - All your turns will be listed.
     - /myTurns
   * - remindersHere
     - If you run this command, the bot will begin to remind you about your turns 10 min before each each turn is about to start/end. The bot will do this only for the particular chat from which this command was texted.
     - /remindersHere
   * - stopReminders
     - If you run this command, the bot stop sending reminders.
     - /stopReminders

Note: You can type everything in lowercase if you want.

===================================
Installing (GNU-Linux, Debian-like)
===================================

Using Git
---------

.. code:: shell

    $ git clone https://github.com/dagomezma/resource-scheduling-telegram-bot.git

Downloading tar
---------------

.. code:: shell

    $ wget https://github.com/dagomezma/resource-scheduling-telegram-bot.tgz
    $ tar -xzvf resource-scheduling-telegram-bot.tgz

Finishing setup
----------------

If missing, install the python3 virtual environments package:

.. code:: shell

    $ sudo apt install python3-venv

Use the setup script install.sh and follow its instructions:

.. code:: shell

    $ chmod +x install.sh
    $ ./install.sh

Then you can execute the bot by running:

.. code:: shell

    $ source non-git/bot-environment/bin/activate
    $ python3 resource-scheduling-telegram-bot.py

After that, you will be receiving logs to stdin and stderr (at your terminal), you should be able to test your bot now by sending messages to it on the telegram app. Whenever you want to quit the bot you just have to press Ctrl+C on the terminal.

You may want the bot to run on the background and having no dependence on your current terminal session. To do that, you can use:

.. code:: shell

    $ nohup python3 resource-scheduling-telegram-bot.py &

Also, if you want to get back your regular python environment you can use the following command:

.. code:: shell

    $ deactivate

Configure it
------------

To configure the available resources so your users can choose between them, you only have to change the contents of the folder non-git/user-configs.

.. list-table:: List of commands
   :widths: 30 70
   :header-rows: 1

   * - File
     - Description
   * - TELEGRAM-BOT-TOKEN.txt
     - One line, your telegram bot token, it is asked at install.sh so it should not be changed.
   * - RESOURCES.txt
     - Put your available resources one line at a time, by default contains three example resources.
   * - ACTIVITIES.txt
     - Put your available activities one line at a time, by default contains three example activities.
   * - AUTHORIZED-TELEGRAM-IDS.txt
     - Only relevant if global variable ALLOW_ONLY_AUTHORIZED_IDS is set as true within the python code. Put the user telegram IDs you wish to whitelist, one lite at a time.

==================================
Running at OS start-up (GNU-Linux)
==================================

I've left a BASH script for this bot so it can be run at startup for the python environment within the project folder. If you want to use it for automatic execution at startup, put the following command at your /etc/rc.local file (should work for any distribution that uses systemd), remember to change example-user for a valid user.

.. code:: shell

    sudo -u example-user /path/to/bot/startup-script &

.. warning::

    You should use a regular user for the execution of the bot, as exemplified by the previous command. Otherwhise you would be vulnerable to cross-user attacks, where superuser executes code which can be modified by a regular user, making it possible for a regular user to gain access to superuser priviliges by changing the code, this may be specially critical if there is a trigger for automatic superuser execution at start up time, like in this case.

===============
Changes to make
===============

There is a file named AUTHORIZED-TELEGRAM-IDS.txt within the non-git folder. I expect to add the possibility to make this file function as a whitelist in the future: only IDs listed there will be able to communicate with the bot. This function will work depending on the boolean state ALLOW_ONLY_AUTHORIZED_IDS within the first lines of code.

=======
License
=======

As stated in the license file, you may copy, distribute and modify this under `GPLv3 <https://www.gnu.org/licenses/gpl-3.0.en.html>`_.
