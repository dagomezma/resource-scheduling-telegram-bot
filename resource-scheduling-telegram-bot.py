# coding=utf8
# This resource-scheduling-telegram-bot.py can serve as a turn assignation bot.

# Dependencies listed at requirements.txt file.
# Python3 v3.8
# python-telegram-bot v11.1.0
# WARNING: designed for python-telegram-bot v11.1
#          it is expected to fail for newer package versions.
# Custom changes were made to schedule v0.60
# (replication is possible via apply-schedule-changes.sh file)

#     ToDo: for /sched RESOURCE (RS), make bot show currently developing turn as
#     BOLD-ITALIC text (currently: the current turn is not even shown).

import sys
from telegram.ext import Updater, MessageHandler, CommandHandler, CallbackQueryHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
from datetime import datetime
from datetime import timedelta
import sqlite3
import schedule

# configs
BOT_UNDER_MAINTENANCE = False
ALLOW_ONLY_AUTHORIZED_IDS = False # change this if you want to blocking
                                  # IDs not explicitly set at .txt file.

# read plain-text file configs as global variables.
with open("non-git/user-configs/TELEGRAM-BOT-TOKEN.txt") as f:
    TOKEN = f.read().splitlines()[0]
with open("non-git/user-configs/RESOURCES.txt") as f:
    AVAILABLE_RESOURCES = f.read().splitlines()
with open("non-git/user-configs/ACTIVITIES.txt") as f:
    AVAILABLE_ACTIVITIES = f.read().splitlines()

if ALLOW_ONLY_AUTHORIZED_IDS:
    with open("non-git/user-configs/AUTHORIZED-TELEGRAM-IDS.txt") as f:
        AUTHORIZED_IDS = f.read().splitlines()
        # Note : Every telegram user has a unique ID... AFTER some users have
        # interacted with your bot, you will be able to read their IDs
        # from your SQLITE database, so you will be able to define
        # their IDs in the AUTHORIZED-TELEGRAM-IDS.txt file.
        #
        # This list may be useful to you if you want to restrict
        # interactions with your bot to IDs within this array.
        # In the end, I did not need to implement such a restricton
        # (if unauthorized users are using your bot this may prove useful)

# GLOBAL VARIABLES DEFINITIONS
DATABASE_FILENAME = 'non-git/schedules.db'
AVAILABLE_STR_INTERVALS = ['DEFAULT', 'NIGHT']
DAYS_IN_WINDOW = 7 # How far into the future users will be able to reserve turns
SLOTS_IN_DAY = 48  # Must be an even integer
BEG_OF_NIGHT = datetime.strptime('18:00:00', "%H:%M:%S")
END_OF_NIGHT = datetime.strptime('07:00:00', "%H:%M:%S")

if not (SLOTS_IN_DAY % 2 == 0 and SLOTS_IN_DAY <= 60):
    sys.exit("Programming error: SLOTS_IN_DAY constant should be an even \
    integer and <= 60.")

SLOT_SIZE = 24 * 60 // SLOTS_IN_DAY  # slot size unit is minutes
#     After this operations SLOT_SIZE is 30 minutes by default, changes may be
# made to the variable SLOTS_IN_DAY in order to change SLOT_SIZE, which was
# thought with 'minutes' as its unit.
LAST_NIGHT_SLOT = (60 * END_OF_NIGHT.hour + END_OF_NIGHT.minute) // SLOT_SIZE
#     The bot does differentiate between day and night, at an office it makes
# sense to be able to divide day in intervals, and to keep the night as just
# one "super-interval" I deliberately made it like this because sometimes the
# use of a RS for us has to be really long. People in such a circumstance is
# encouraged to take the night turn instead of requesting for a large number
# of hours within day (when other users may need the RSs for shorter intervals).

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def do_on_any_message(bot, update):
    if BOT_UNDER_MAINTENANCE:
        update.message.reply_text('''Sorry, I'm currently under maintenance.''')
    get_user_data(bot, update)


def get_user_data(bot, update):
    telegram_id = update.message.from_user.id
    username = update.message.from_user.username
    user_fn = update.message.from_user.first_name
    user_ln = update.message.from_user.last_name
    conn = sqlite3.connect(DATABASE_FILENAME)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO tbl_users (telegramID, username, userFN, userLN) VALUES ('"
              + str(telegram_id) + "','"
              + str(username) + "','"
              + str(user_fn) + "','"
              + str(user_ln) + "')")
    conn.commit()
    conn.close()


def start(bot, update):
    update.message.reply_text('''\
Hello, I\'m scheduling-bot, please use commands to communicate with me.

Commands are to be sent to me with a keyword starting with a slash (/).

There are two types of arguments for such commands:
Mandatory: <>
Optional: []

############
Beginning list of available commands
############

Command: /sched <resource>
# Evince current schedule found in database, for selected resource (RS).
# RSs available:
# ''' + str(AVAILABLE_RESOURCES) + '''
# e.g. /sched SIM-PC-1

Command: /request <resource> <activity> [interval needed]
# Request a turn.
# A list of slots available according to the activity will be shown with (+interval) shown as the proper duration.
# If [interval] is not declared by user, a default value will be shown in (+interval).
#
# Types of activities available:
# ''' + str(AVAILABLE_ACTIVITIES) + '''
# Valid string intervals: ''' + str(AVAILABLE_STR_INTERVALS) + '''
# Valid float intervals: Any multiple of 0.5 (hours)
# e.g. /request SIM-PC-1 ACTIVITY-1
# e.g. /request SIM-PC-2 ACTIVITY-2 1.5
# e.g. /request SIM-PC-1 ACTIVITY-3 NIGHT

Command: /rm
# Requests removal of a turn.
# You'll be able to select which turn to remove from a list of appropriate turns, if any.

Command: /myTurns
# All your turns will be listed.

Command: /remindersHere
# If you run this command, I'll begin to remind you about your turns 10 min before each each one.
# I'll do this only for the particular chat from which this command was texted.

Command: /stopReminders
# If you run this command, I'll stop sending reminders.

# Note: You can type everything in lowercase if you want.''')


def remove_buttons_if_timeout(bot, job, msg_reply, chat_data):
    bot.edit_message_text(text="I waited 20 seconds. Timed out.",
                          chat_id=job.context,
                          message_id=msg_reply.message_id)
    if 'job' in chat_data:
        job.schedule_removal()  # remove job automatically if timeout met
        del chat_data['job']
    set_busy_state(0)


def request_turn(bot, update, args, job_queue, chat_data):
    chat_id = update.message.chat_id
    telegram_id = update.message.from_user.id
    cb_id = 'set'  # Command identifier for "button" method to recognize
    try:
        rs = str(args[0]).upper()
        actvty_type = str(args[1]).upper()
        try:
            asked_interval = str(args[2]).upper()
        except (IndexError, ValueError):
            asked_interval = 'DEFAULT'

        eng_fn = update.message.from_user.first_name
        eng_ln = update.message.from_user.last_name
        if not (eng_fn is None or eng_ln is None):
            eng_name = eng_fn + ' ' + eng_ln

            if not get_busy_state():

                if not (rs in AVAILABLE_RESOURCES):
                    update.message.reply_text(
                        'Sorry, as much as you\'d want, "' + args[0] + '" is not a valid location to ask for.')
                    return
                if not (actvty_type in AVAILABLE_ACTIVITIES):
                    update.message.reply_text(
                        'Sorry, as much as you\'d want, "' + args[1] + '" is not a valid activity to schedule.')
                    return
                str_duration = '(+0.5h)'
                slots_to_take = 1
                if is_number(asked_interval):
                    if (float(asked_interval) % 0.5) == 0:
                        if float(asked_interval) <= 5:
                            str_duration = '(+' + asked_interval + 'h)'
                            slots_to_take = float(asked_interval) * 60 // SLOT_SIZE
                        else:
                            update.message.reply_text(
                                'Sorry, you can\'t ask for a turn of more than 5 hours. Consider asking for a'
                                + ' night turn')
                            return
                    else:
                        update.message.reply_text(
                            'Sorry, the interval number you entered is not a multiple of 0.5 hours.')
                        return
                else:
                    if asked_interval in AVAILABLE_STR_INTERVALS:
                        if asked_interval == 'NIGHT':
                            str_duration = '(upTo7am)'
                            slots_to_take = 26
                        elif asked_interval == 'DEFAULT':
                            str_duration = get_default_interval_for_activity(actvty_type)[1]
                            slots_to_take = get_default_interval_for_activity(actvty_type)[2]
                    else:
                        update.message.reply_text('Sorry, the interval you entered is not a valid interval.')
                        return

                # Obtain available slots for activity
                possible_slots = obtain_empty_list(actvty_type, asked_interval, 5, rs)
                if len(possible_slots) > 0:
                    if 'job' in chat_data:
                        update.message.reply_text(
                            'Sorry ' + eng_name + ', you can\'t ask for two requests at the same time.')
                    else:
                        set_busy_state(1)
                        keyboard = []
                        for i in range(0, len(possible_slots)):
                            cb_data = str(telegram_id) + '|' + cb_id + '|' + rs + '|' + actvty_type\
                                      + '|' + possible_slots[i] + '|' + str(slots_to_take)
                            keyboard.append([InlineKeyboardButton(possible_slots[i] + ' ' + str_duration,
                                                                  callback_data=cb_data)])
                        cb_data = str(telegram_id) + '|' + cb_id + '|' + 'cancel'
                        keyboard.append([InlineKeyboardButton('cancel',
                                                              callback_data=cb_data)])
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        msg_rpl_text = update.message.reply_text('Slots available for ' + actvty_type
                                                                 + ' @ ' + rs + ':', reply_markup=reply_markup)
                        # Add job to queue
                        job = job_queue.run_once(
                            lambda bot, job: remove_buttons_if_timeout(bot, job, msg_rpl_text, chat_data), 20,
                            context=chat_id)
                        chat_data['job'] = job
                        print(datetime.now().strftime('%Y-%m-%d %H:%M:%S') +
                              ', job set at chat #' + str(chat_id) + ' (' + eng_name + ')')
                else:
                    update.message.reply_text(
                        'Sorry ' + eng_name + ', no slots available for your ' + actvty_type + ' activity.')
                    return
            else:
                if 'job' in chat_data:
                    update.message.reply_text(
                        'Sorry ' + eng_name + ', you can\'t ask for two requests at the same time.')
                else:
                    update.message.reply_text(
                        'Sorry ' + eng_name + ', I\'m currently busy with another user.')
        else:
            update.message.reply_text(
                'Sorry, your user has to have both a first name and a last name. Request not possible.')
    except (IndexError, ValueError):
        update.message.reply_text('Usage: /request <resource> <activity> [interval needed]')


def init_database():
    conn = sqlite3.connect(DATABASE_FILENAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tbl_botStatus
                       (     Property       TEXT,
                            propValue    INTEGER,
                           UNIQUE(Property))''')
    c.execute('''CREATE TABLE IF NOT EXISTS tbl_days
                       (        dayID     INTEGER PRIMARY KEY,
                                  day        TEXT,
                             UNIQUE(day))''')
    c.execute('''CREATE TABLE IF NOT EXISTS tbl_daySlots
                       (       slotID     INTEGER PRIMARY KEY,
                             timeSlot        TEXT,
                             UNIQUE(timeSlot))''')
    c.execute('''CREATE TABLE IF NOT EXISTS tbl_activities
                       (    activityID     INTEGER PRIMARY KEY,
                              activity        TEXT,
                        UNIQUE(activity))''')
    c.execute('''CREATE TRIGGER IF NOT EXISTS UniqueColumnCheckNullInsert
                         BEFORE INSERT
                             ON tbl_activities
                           WHEN NEW.activity IS NULL
                          BEGIN
                                SELECT CASE WHEN((
                                  SELECT 1
                                    FROM tbl_activities
                                   WHERE activity IS NULL)
                                                 NOTNULL) THEN RAISE(IGNORE) END;
                                   END;''')
    c.execute('''CREATE TABLE IF NOT EXISTS tbl_users
                       (       userID    INTEGER PRIMARY KEY,
                           telegramID    INTEGER NOT NULL,
                           mainChatID    INTEGER,
                             username       TEXT,
                               userFN       TEXT,
                               userLN       TEXT,
                        UNIQUE(telegramID))''')
    for rs in AVAILABLE_RESOURCES:
        c.execute('''CREATE TABLE IF NOT EXISTS "tbl_slots''' + rs + '''"
                         (     dayID       INTEGER,
                              slotID       INTEGER,
                              userID       INTEGER,
                           activityID       INTEGER,
                          FOREIGN KEY (dayID)     REFERENCES             tbl_days(dayID),
                          FOREIGN KEY (slotID)    REFERENCES        tbl_daySlots(slotID),
                          FOREIGN KEY (userID)    REFERENCES           tbl_users(userID),
                          FOREIGN KEY (activityID) REFERENCES tbl_activities(activityID),
                          UNIQUE(dayID, slotID))''')
        c.execute('''CREATE VIEW IF NOT EXISTS "view_slots''' + rs + '''" AS
                        SELECT (d.day || ' ' || t.timeSlot)         AS cdate,
                                                                u.telegramID,
                               (u.userFN || ' ' || u.userLN) AS userFullName,
                                                                  a.activity
                          FROM "tbl_slots''' + rs + '''" AS rs,
                               tbl_days                AS d,
                               tbl_daySlots            AS t,
                               tbl_users               AS u,
                               tbl_activities AS a
                         WHERE rs.dayID      =  d.dayID
                           AND rs.slotID     =  t.slotID
                           AND rs.userID     = u.userID
                           AND rs.activityID  = a.activityID
                  ''')

    # Create bot status 'busy' and init it as False, if not already existent
    c.execute("INSERT OR IGNORE INTO tbl_botStatus (Property, propValue) VALUES ('bool_busy', 0)")
    # Create NULL activity, if not already existent
    c.execute("INSERT OR IGNORE INTO tbl_activities (activity) VALUES (NULL)")
    # Create NULL user, if not already existent
    c.execute("""INSERT OR IGNORE INTO tbl_users (telegramID, mainChatID, username, userFN, userLN)
                                          VALUES (\'NA\', NULL, NULL, NULL, NULL)""")
    # populate daySlots table
    d = datetime.strptime('00:00:00', '%H:%M:%S')
    while d <= datetime.strptime('23:59:59', '%H:%M:%S'):
        c.execute("INSERT OR IGNORE INTO tbl_daySlots (timeSlot) VALUES (\'" + d.strftime('%H:%M:%S') + "\')")
        d += timedelta(minutes=SLOT_SIZE)
    for a in AVAILABLE_ACTIVITIES:
        c.execute("INSERT OR IGNORE INTO tbl_activities (activity) VALUES (\'" + str(a) + "\')")
    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    set_busy_state(0)  # in case last bot execution ended when busy
    update_slots()


def update_slots():
    ahora = datetime.now()
    ahora_day = datetime(ahora.year, ahora.month, ahora.day)
    current_slot = ((3600 * ahora.hour + 60 * ahora.minute + ahora.second) // 60 // SLOT_SIZE) + 1

    conn = sqlite3.connect(DATABASE_FILENAME)
    c = conn.cursor()
    c.execute("SELECT dayID, day FROM tbl_days WHERE dayID IN (SELECT MAX(dayID) FROM tbl_days)")
    max_day_row = c.fetchall()
    # max_day_id = c.fetchall()[0][0]
    if len(max_day_row) == 0:
        max_day_id = 0
        max_day = ahora_day - timedelta(days=1)
    else:
        max_day_id = int(max_day_row[0][0]) - 2
        max_day = datetime.strptime(max_day_row[0][1], "%Y-%m-%d") - timedelta(days=2)
    null_ac_id = int(c.execute("SELECT activityID FROM tbl_activities WHERE activity IS NULL").fetchall()[0][0])
    null_user_id = int(c.execute("SELECT userID FROM tbl_users WHERE telegramID IS \'NA\'").fetchall()[0][0])
    last_day_of_window = datetime(ahora.year, ahora.month, ahora.day) + timedelta(days=DAYS_IN_WINDOW)
    while max_day < last_day_of_window:
        max_day_id += 1
        max_day += timedelta(days=1)
        c.execute('INSERT OR IGNORE INTO tbl_days (dayID, day) VALUES ('
                  '\'' + str(max_day_id) + '\', '
                  '\'' + datetime(max_day.year, max_day.month, max_day.day).strftime('%Y-%m-%d') + '\''
                  + ')')
        for rs in AVAILABLE_RESOURCES:
            if max_day == ahora_day:  # fill from this slot until midnight
                for ii in range(current_slot, SLOTS_IN_DAY + 1):
                    c.execute('INSERT OR IGNORE INTO "tbl_slots' + rs + '" (dayID, slotID, userID, activityID) VALUES ('
                              + '\'' + str(max_day_id) + '\', '
                              + '\'' + str(ii) + '\','
                              + '\'' + str(null_user_id) + '\','
                              + '\'' + str(null_ac_id) + '\''
                              + ')')
            else:
                if max_day < last_day_of_window:
                    for ii in range(1, SLOTS_IN_DAY + 1):
                        c.execute('INSERT OR IGNORE INTO "tbl_slots' + rs + '"'
                                  + ' (dayID, slotID, userID, activityID) VALUES ('
                                  + '\'' + str(max_day_id) + '\', '
                                  + '\'' + str(ii) + '\','
                                  + '\'' + str(null_user_id) + '\','
                                  + '\'' + str(null_ac_id) + '\''
                                  + ')')
                else:  # fill from midnight until morning + 2 slots
                    for ii in range(1, LAST_NIGHT_SLOT + 2):
                        c.execute('INSERT OR IGNORE INTO "tbl_slots' + rs + '"'
                                  + ' (dayID, slotID, userID, activityID) VALUES ('
                                  + '\'' + str(max_day_id) + '\', '
                                  + '\'' + str(ii) + '\','
                                  + '\'' + str(null_user_id) + '\','
                                  + '\'' + str(null_ac_id) + '\''
                                  + ')')
    conn.commit()
    conn.close()
    set_busy_state(0)  # in case last bot execution ended when busy


def set_busy_state(bool_busy):
    # Sets current state of bot

    conn = sqlite3.connect(DATABASE_FILENAME)
    c = conn.cursor()
    c.execute("""
        UPDATE tbl_botStatus
           SET    propValue = """ + str(bool_busy) + """
         WHERE Property IN (SELECT Property
                              FROM tbl_botStatus
                             WHERE Property IS 'bool_busy'
                         );""")
    conn.commit()
    conn.close()


def get_busy_state():
    # Sets current state of bot

    conn = sqlite3.connect(DATABASE_FILENAME)
    c = conn.cursor()
    c.execute("""SELECT Property, propValue FROM tbl_botStatus WHERE Property IS 'bool_busy';""")
    rows = c.fetchall()
    bool_busy = rows[0][1]
    conn.commit()
    conn.close()
    return bool_busy


def obtain_contiguous_intervals(rs, from_beg_of_db=False):
    # Obtains a table with all contiguous intervals related to the presence of
    # user-activity, from current time onwards.
    # Table has the following columns:
    # startDateTime endDateTime telegramID userFullName activity rs

    conn = sqlite3.connect(DATABASE_FILENAME)
    c = conn.cursor()
    ahora = datetime.now()
    if from_beg_of_db:
        c.execute('''SELECT MIN(date) AS fromdate, MAX(date) AS enddate, telegramID, user, activity
                       FROM    (--get closest preceeding different key
                             SELECT t.*, MAX(t2.date) as key2
                               FROM (SELECT cdate AS date, telegramID, userFullName AS user, activity FROM "view_slots'''
                  + rs + '''"
                               ) AS t
                          LEFT JOIN (SELECT cdate AS date, telegramID, userFullName AS user, activity FROM "view_slots'''
                  + rs + '''"
                               ) AS t2
                                 ON t2.date < t.date AND NOT (t2.user IS t.user AND t2.activity IS t.activity)
                           GROUP BY t.date
                               )
                   GROUP BY key2;
                   ''')
    else:
        c.execute('''SELECT MIN(date) AS fromdate, MAX(date) AS enddate, telegramID, user, activity
                       FROM    (--get closest preceeding different key
                             SELECT t.*, MAX(t2.date) as key2
                               FROM (SELECT cdate AS date, telegramID, userFullName AS user, activity FROM "view_slots'''
                  + rs + '''" WHERE cdate >  \''''
                  + ahora.strftime('%Y-%m-%d %H:%M:%S') + '''\') AS t
                          LEFT JOIN (SELECT cdate AS date, telegramID, userFullName AS user, activity FROM "view_slots'''
                  + rs + '''" WHERE cdate >  \''''
                  + ahora.strftime('%Y-%m-%d %H:%M:%S') + '''\') AS t2
                                 ON t2.date < t.date AND NOT (t2.user IS t.user AND t2.activity IS t.activity)
                           GROUP BY t.date
                               )
                   GROUP BY key2;
                   ''')
    rows = c.fetchall()
    conn.commit()
    conn.close()
    # Add also the rs name to the tuple containing intervals information
    for i in range(0, len(rows)):
        rows[i] = rows[i] + (rs,)
    return rows


def assign_engineer(telegram_id, rs, actvty_type, cdate, slots_to_take=0):
    if slots_to_take == 0:
        if actvty_type in ['PV', 'GR', 'N-0']:
            slots_to_take = 30 // SLOT_SIZE  # 1 if SLOT_SIZE == 30
        elif actvty_type in ['N-1', 'BN-1', 'TS']:
            slots_to_take = 60 // SLOT_SIZE  # 2 if SLOT_SIZE == 30
        elif actvty_type in ['ARPA']:
            slots_to_take = 120 // SLOT_SIZE  # 2 if SLOT_SIZE == 30
        elif actvty_type in ['N-1-1', 'BN-1-1']:
            slots_to_take = 780 // SLOT_SIZE  # 26 if SLOT_SIZE == 30

    conn = sqlite3.connect(DATABASE_FILENAME)
    c = conn.cursor()
    user_id = int(c.execute("SELECT userID FROM tbl_users WHERE telegramID IS \'"
                            + str(telegram_id) + "\'").fetchall()[0][0])
    if actvty_type == "NULL":
        ac_id = int(c.execute("SELECT activityID FROM tbl_activities WHERE activity IS NULL").fetchall()[0][0])
    else:
        ac_id = int(c.execute("SELECT activityID FROM tbl_activities WHERE activity IS \'"
                              + actvty_type + "\'").fetchall()[0][0])
    c.execute('''
    UPDATE "tbl_slots''' + rs + '''"
       SET    userID = \'''' + str(user_id) + '''\',
           activityID = \'''' + str(ac_id) + '''\'
     WHERE (dayID || \' \' || slotID) IN (
    SELECT (dayID || \' \' || slotID)
      FROM (SELECT rs.dayID, rs.slotID, (d.day || \' \' || t.timeSlot) AS cdate
              FROM "tbl_slots''' + rs + '''" AS rs, tbl_days AS d, tbl_daySlots AS t
             WHERE rs.dayID = d.dayID
               AND rs.slotID = t.slotID
               AND cdate >= \'''' + cdate + '''\' LIMIT ''' + str(slots_to_take) + '''));''')
    conn.commit()
    conn.close()


def send_turn_list(bot, update, args, job_queue, chat_data):
    try:
        # args[0] should contain name of RS
        rs = str(args[0]).upper()

        if not (rs in AVAILABLE_RESOURCES):
            update.message.reply_text(
                'Sorry, as much as you\'d want, "' + args[0] + '" is not a valid location to ask for.')
            return

        contgs_intvs = obtain_contiguous_intervals(rs)
        used_contgs_intvs = []
        for i in range(0, len(contgs_intvs)):
            if contgs_intvs[i][3] is not None:
                used_contgs_intvs.append(contgs_intvs[i])

        turn_list_msg = '### CURRENT SCHEDULE IN DATABASE (RS: ' + rs + ') ###\n\n'

        for i in range(0, len(used_contgs_intvs)):
            this_turn_start = datetime.strptime(used_contgs_intvs[i][0], '%Y-%m-%d %H:%M:%S')
            this_turn_end = datetime.strptime(used_contgs_intvs[i][1], '%Y-%m-%d %H:%M:%S') + timedelta(minutes=SLOT_SIZE)

            turn_list_msg += 'Turn for ' + str(used_contgs_intvs[i][3]) + ' (' + str(used_contgs_intvs[i][4]) + ')\n'
            turn_list_msg += '  Starts: ' + this_turn_start.strftime('%Y-%m-%d %H:%M') + '\n'
            turn_list_msg += '    Ends: ' + this_turn_end.strftime('%Y-%m-%d %H:%M')
            if not (i == len(used_contgs_intvs)):
                turn_list_msg += '\n'
        if len(used_contgs_intvs) == 0:
            turn_list_msg += 'Nothing here (everything available)...'
        update.message.reply_text(turn_list_msg)

    except (IndexError, ValueError):
        update.message.reply_text('Usage: /sched <resource>')


def send_user_turn_list(bot, update):
    telegram_id = update.message.from_user.id
    user_contgs_rows = get_user_turn_list(telegram_id)
    turn_list_msg = '### YOUR CURRENT APPOINTMENTS ###\n\n'

    for i in range(0, len(user_contgs_rows)):
        this_turn_start = datetime.strptime(user_contgs_rows[i][0], '%Y-%m-%d %H:%M:%S')
        this_turn_end = datetime.strptime(user_contgs_rows[i][1], '%Y-%m-%d %H:%M:%S') + timedelta(minutes=SLOT_SIZE)

        turn_list_msg += 'Turn for ' + str(user_contgs_rows[i][4]) + ' activity @ ' + str(user_contgs_rows[i][5]) + ':\n'
        turn_list_msg += '  Starts: ' + this_turn_start.strftime('%Y-%m-%d %H:%M') + '\n'
        turn_list_msg += '    Ends: ' + this_turn_end.strftime('%Y-%m-%d %H:%M')
        if not (i == len(user_contgs_rows)):
            turn_list_msg += '\n'
    if len(user_contgs_rows) == 0:
        turn_list_msg += 'Nothing here (you have not assigned new turns)...'
    update.message.reply_text(turn_list_msg)


def request_turn_removal(bot, update, job_queue, chat_data):
    if 'job' in chat_data:
        update.message.reply_text(
            'Sorry, you can\'t ask for two requests at the same time.')
    else:
        chat_id = update.message.chat_id
        telegram_id = update.message.from_user.id
        cb_id = 'rm'
        user_contgs_intvls = get_user_turn_list(telegram_id)
        keyboard = []
        if len(user_contgs_intvls) > 0:
            for i in range(0, len(user_contgs_intvls)):
                row = user_contgs_intvls[i]
                this_turn_start_slot = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                this_turn_end_slot = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S')
                this_turn_end = this_turn_end_slot + timedelta(minutes=SLOT_SIZE)
                actvty_type = str(row[4])
                rs = str(row[5])
                turn_list_msg = ''
                turn_list_msg += actvty_type + ' @' + rs + ':\n'
                turn_list_msg += this_turn_start_slot.strftime('%Y-%m-%d %H:%M') + '\n'
                turn_list_msg += ' to ' + this_turn_end.strftime('%Y-%m-%d %H:%M')

                cb_data = str(telegram_id)\
                    + '|' + cb_id\
                    + '|' + this_turn_start_slot.strftime('%Y-%m-%d %H:%M:%S')\
                    + '|' + this_turn_end_slot.strftime('%Y-%m-%d %H:%M:%S')\
                    + '|' + rs
                keyboard.append([InlineKeyboardButton(turn_list_msg, callback_data=cb_data)])
            cb_data = str(telegram_id) + '|' + cb_id + '|' + 'cancel'
            keyboard.append([InlineKeyboardButton('cancel', callback_data=cb_data)])

            reply_markup = InlineKeyboardMarkup(keyboard)
            msg_rpl_text = update.message.reply_text('Turns available for removal:\n', reply_markup=reply_markup)
            # Add job to queue
            job = job_queue.run_once(
                lambda bot, job: remove_buttons_if_timeout(bot, job, msg_rpl_text, chat_data), 20,
                context=chat_id)
            chat_data['job'] = job
            print(datetime.now().strftime('%Y-%m-%d %H:%M:%S') +
                  ', removal job set at chat #' + str(chat_id))
        else:
            update.message.reply_text("You have no active turns to remove.")


def get_user_turn_list(telegram_id):
    # conn = sqlite3.connect(DATABASE_FILENAME)
    # c = conn.cursor()
    # user_id = int(c.execute("SELECT userID FROM tbl_users WHERE telegramID IS \'"
    #                         + str(telegram_id) + "\'").fetchall()[0][0])
    # conn.commit()
    # conn.close()
    user_contgs_rows = []
    for rs in AVAILABLE_RESOURCES:
        contg_intvs = obtain_contiguous_intervals(rs)
        for i in range(0, len(contg_intvs)):
            if contg_intvs[i][2] == telegram_id:
                user_contgs_rows.append(contg_intvs[i])
    return user_contgs_rows


def get_default_interval_for_activity(actvty_type):
    int_duration = 0.5
    str_duration = '(+0.5h)'
    if actvty_type in ['N-1', 'BN-1', 'TS']:
        int_duration = 1
        str_duration = '(+1h)'
    elif actvty_type in ['ARPA']:
        int_duration = 2
        str_duration = '(+2h)'
    elif actvty_type in ['N-1-1', 'BN-1-1']:
        int_duration = (END_OF_NIGHT - BEG_OF_NIGHT).seconds // 60 // 60
        str_duration = '(upTo7am)'
    slots_to_take = int_duration * 60 // SLOT_SIZE
    return [int_duration, str_duration, slots_to_take]


def obtain_empty_list(actvty_type, asked_interval, int_limit_of_possibilities_to_show, rs):
    # ToDo: maybe this method can be combined with get_user_turn_list

    bool_night_turn = False
    int_interval_needed = 0.5
    if asked_interval == 'DEFAULT':
        int_interval_needed = get_default_interval_for_activity(actvty_type)[0]
        if actvty_type in ['N-1-1', 'BN-1-1']:
            bool_night_turn = True
    else:
        if is_number(asked_interval):
            if (float(asked_interval) % 0.5) == 0:
                int_interval_needed = float(asked_interval)
        else:
            if asked_interval == 'NIGHT':
                bool_night_turn = True
                int_interval_needed = (END_OF_NIGHT - BEG_OF_NIGHT).seconds // 60 // 60
    beg_of_day = END_OF_NIGHT.hour
    beg_of_nig = BEG_OF_NIGHT.hour

    rows = obtain_contiguous_intervals(rs)
    blank_intervals_rows = []
    all_possible_stt_slots = []
    for i in range(0, len(rows)):
        if rows[i][3] is None:
            blank_intervals_rows.append(rows[i])
    for i in range(0, len(blank_intervals_rows)):
        i_stt_date = datetime.strptime(blank_intervals_rows[i][0], '%Y-%m-%d %H:%M:%S')
        i_end_date = datetime.strptime(blank_intervals_rows[i][1], '%Y-%m-%d %H:%M:%S')
        d = i_stt_date
        delta = timedelta(minutes=SLOT_SIZE)
        while d <= i_end_date:

            if (i_end_date + timedelta(minutes=SLOT_SIZE) - d) >= timedelta(hours=int_interval_needed):
                if not bool_night_turn and (beg_of_day <= int(d.strftime("%H")) < beg_of_nig):  # within day shift
                    if (d + timedelta(hours=int_interval_needed))\
                            <= datetime.strptime(str(d.date()) + ' ' + str(beg_of_nig) + ':00:00', "%Y-%m-%d %H:%M:%S"):
                        all_possible_stt_slots.append(d.strftime("%Y-%m-%d %H:%M"))
                elif bool_night_turn and (int(d.strftime("%H")) == beg_of_nig) and (int(d.strftime("%M")) == 0):
                    all_possible_stt_slots.append(d.strftime("%Y-%m-%d %H:%M"))
            d += delta
    return all_possible_stt_slots[0:int_limit_of_possibilities_to_show]


def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)


def button(bot, update, chat_data):
    query = update.callback_query
    telegram_id = query.from_user.id
    query_text = query.message.text

    str_query = str(query.data)
    initial_request_id = str_query.split('|')[0]
    cb_id = str_query.split('|')[1]

    if str(telegram_id) == initial_request_id:
        if str_query.split('|')[2] == 'cancel':
            bot.edit_message_text(text="Selected option: cancel",
                                  chat_id=query.message.chat_id,
                                  message_id=query.message.message_id)
        else:
            if cb_id == 'set':
                rs = str_query.split('|')[2]
                actvty_type = str_query.split('|')[3]
                cdate = str_query.split('|')[4]
                slots_to_take = int(float(str_query.split('|')[5]))

                assign_engineer(telegram_id, rs, actvty_type, cdate, slots_to_take)
                bot.edit_message_text(text="Selected option: {}\nSucessfully set!".format(cdate),
                                      chat_id=query.message.chat_id,
                                      message_id=query.message.message_id)
            elif cb_id == 'rm':
                this_turn_stt_slot = str_query.split('|')[2]
                this_turn_end_slot = str_query.split('|')[3]
                rs = str_query.split('|')[4]
                slots_to_take = (datetime.strptime(this_turn_end_slot, "%Y-%m-%d %H:%M:%S")
                                 + timedelta(minutes=SLOT_SIZE)
                                 - datetime.strptime(this_turn_stt_slot, "%Y-%m-%d %H:%M:%S")).seconds\
                    // 60 // SLOT_SIZE
                assign_engineer(telegram_id='NA',
                                rs=rs,
                                actvty_type='NULL',
                                cdate=this_turn_stt_slot,
                                slots_to_take=slots_to_take)
                bot.edit_message_text(text="Sucessfully removed!",
                                      chat_id=query.message.chat_id,
                                      message_id=query.message.message_id)

        # If option was set, remove lock on bot
        if cb_id == 'set':
            set_busy_state(0)  # set bot busy property to false

        # Remove timeout scheduled to remove buttons
        if 'job' in chat_data:
            job = chat_data['job']
            job.schedule_removal()
            del chat_data['job']


def unknown(bot, update):
    update.message.reply_text("Sorry, I didn't understand that command.")


def set_main_chat_for_user(bot, update):
    telegram_id = update.message.from_user.id
    chat_id = update.message.chat_id
    conn = sqlite3.connect(DATABASE_FILENAME)
    c = conn.cursor()
    c.execute("""
        UPDATE tbl_users
           SET mainChatID = """ + str(chat_id) + """
         WHERE telegramID = """ + str(telegram_id) + """;""")
    conn.commit()
    conn.close()
    update.message.reply_text('''Chat succesfully set as main chat!''')


def unset_main_chat_for_user(bot, update):
    # TODO: this could be a sole function with set_main_chat_for_user
    telegram_id = update.message.from_user.id
    conn = sqlite3.connect(DATABASE_FILENAME)
    c = conn.cursor()
    c.execute("""
        UPDATE tbl_users
           SET mainChatID = NULL
         WHERE telegramID = """ + str(telegram_id) + """;""")
    conn.commit()
    conn.close()
    update.message.reply_text('''I'll stop sending reminders!''')


def reminder(bot):
    next_occupied_intvls = []
    next_empty_intvls = []
    ahora = datetime.now()
    bool_current_thirty = ahora.minute // 30  # either 0 (representing 0) or 1 (representing 30)
    current_thirty = datetime(ahora.year, ahora.month, ahora.day, ahora.hour, bool_current_thirty * 30, 0)
    next_thirty = current_thirty + timedelta(minutes=SLOT_SIZE)
    for rs in AVAILABLE_RESOURCES:
        rows = obtain_contiguous_intervals(rs, from_beg_of_db=True)
        for i in range(0, len(rows)):
            if rows[i][3] is not None and rows[i][0] == next_thirty.strftime("%Y-%m-%d %H:%M:%S"):
                next_occupied_intvls.append(rows[i])
            elif rows[i][3] is not None and rows[i][1] == current_thirty.strftime("%Y-%m-%d %H:%M:%S"):
                next_empty_intvls.append(rows[i])
    for i in range(0, len(next_occupied_intvls)):
        telegram_id = next_occupied_intvls[i][2]
        conn = sqlite3.connect(DATABASE_FILENAME)
        c = conn.cursor()
        chat_id = c.execute("SELECT mainChatID FROM tbl_users WHERE telegramID = "
                            + str(telegram_id)).fetchall()[0][0]
        conn.commit()
        conn.close()
        if chat_id is not None:
            row = next_occupied_intvls[i]
            this_turn_start = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
            this_turn_end = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S') + timedelta(minutes=SLOT_SIZE)
            rs = str(row[5])
            turn_msg = 'Your turn will begin shortly:\n'
            turn_msg += 'Turn for ' + str(row[3]) + ' (' + str(row[4]) + '@' + rs + ')\n'
            turn_msg += '  Starts: ' + this_turn_start.strftime('%Y-%m-%d %H:%M') + '\n'
            turn_msg += '    Ends: ' + this_turn_end.strftime('%Y-%m-%d %H:%M') + '\n\n'
            bot.send_message(chat_id, text=turn_msg)
    for i in range(0, len(next_empty_intvls)):
        telegram_id = next_empty_intvls[i][2]
        conn = sqlite3.connect(DATABASE_FILENAME)
        c = conn.cursor()
        chat_id = c.execute("SELECT mainChatID FROM tbl_users WHERE telegramID = "
                            + str(telegram_id)).fetchall()[0][0]
        conn.commit()
        conn.close()
        if chat_id is not None:
            row = next_empty_intvls[i]
            this_turn_end = datetime.strptime(row[1], '%Y-%m-%d %H:%M:%S') + timedelta(minutes=SLOT_SIZE)
            rs = str(row[5])

            turn_msg = 'Your turn will end shortly:\n'
            turn_msg += 'Turn for ' + str(row[3]) + ' (' + str(row[4]) + '@' + rs + ')\n'
            turn_msg += '    Ends: ' + this_turn_end.strftime('%Y-%m-%d %H:%M') + '\n\n'
            bot.send_message(chat_id, text=turn_msg)


def add_schedule_jobs(bot):
    # Declare sched event for adding days to database (window always of one week)
    schedule.every().day.at("00:05").do(update_slots)
    schedule.every().hour.at(":20").do(reminder, bot)
    schedule.every().hour.at(":50").do(reminder, bot)
    schedule.run_continuously()  # for this to work I had to add code to
                                 # "schedule" package as explained here:
    # https://github.com/mrhwick/schedule/blob/master/schedule/__init__.py
    # (regarding "import threading" and both "def run_continously")
    # The above HAS to be done for the bot to work.


def main():
    init_database()

    """Run bot."""
    updater = Updater(TOKEN)
    add_schedule_jobs(updater.bot)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(MessageHandler(Filters.all, do_on_any_message), group=1)
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", start))
    dp.add_handler(CallbackQueryHandler(button, pass_chat_data=True))
    dp.add_handler(CommandHandler("request", request_turn,
                                  pass_args=True,
                                  pass_job_queue=True,
                                  pass_chat_data=True))
    dp.add_handler(CommandHandler("sched", send_turn_list,
                                  pass_args=True,
                                  pass_job_queue=True,
                                  pass_chat_data=True))
    dp.add_handler(CommandHandler("rm", request_turn_removal,
                                  pass_job_queue=True,
                                  pass_chat_data=True))
    dp.add_handler(CommandHandler("remindersHere", set_main_chat_for_user))
    dp.add_handler(CommandHandler("stopReminders", unset_main_chat_for_user))
    dp.add_handler(CommandHandler("myTurns", send_user_turn_list))
    dp.add_handler(MessageHandler(Filters.command, unknown))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Block until you press Ctrl-C or the process receives SIGINT, SIGTERM or
    # SIGABRT. This should be used most of the time, since start_polling() is
    # non-blocking and will stop the bot gracefully.
    updater.idle()

    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)


if __name__ == '__main__':
    main()
