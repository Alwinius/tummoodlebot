#!/bin/python
# -*- coding: utf-8 -*-
from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
import logging, configparser, telegram
from sqlalchemy import create_engine, distinct
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text
from moodle_db_create import User, Base, FFile
engine = create_engine('sqlite:///config/moodleusers.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

config = configparser.ConfigParser()
config.read('config/config.ini')
updater = Updater(token=config['DEFAULT']['BotToken'])
dispatcher = updater.dispatcher

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)
			
def start(bot, update):
    session = DBSession()
    entry=session.query(User).filter(User.id==update.message.chat_id).first()
    if not entry:
        bot.sendMessage(chat_id=update.message.chat_id, text="Hallo, ich bin der TUM-Moodlebot. Ich benachrichtige alle registrierten Nutzer oder Gruppen Ã¼ber Ã„nderungen in entsprechenden Moodle-Kursen. Du kannst Benachrichtigungen mit /start oder /stop aktivieren bzw. deaktivieren. Wenn du eine Datei direkt von mir zugesendet haben möchtest, wähle zuerst über die Tastatur den Kurs aus.")
        new_user = User(id=update.message.chat_id, first_name=update.message.chat.first_name, last_name=update.message.chat.last_name, username=update.message.chat.username, title=update.message.chat.title, notifications=True, current_selection="0")
        bot.sendMessage(chat_id=update.message.chat_id, text="Benachrichtigungen aktiv.")
        session.add(new_user)
        session.commit()
    else:
        if entry.notifications:
            bot.sendMessage(chat_id=update.message.chat_id, text="Benachrichtigungen bereits aktiv.")
        else:
            entry.notifications=True
            session.commit()
            bot.sendMessage(chat_id=update.message.chat_id, text="Benachrichtigungen aktiviert.")
    session.close()
def stop(bot, update):
    session = DBSession()
    entry=session.query(User).filter(User.id==update.message.chat_id).first()
    if not entry:
        bot.sendMessage(chat_id=update.message.chat_id, text="Hallo, ich bin der TUM-Moodlebot. Ich benachrichtige alle registrierten Nutzer oder Gruppen Ã¼ber Ã„nderungen in entsprechenden Moodle-Kursen. Du kannst Benachrichtigungen mit /start oder /stop aktivieren bzw. deaktivieren. Wenn du eine Datei direkt von mir zugesendet haben möchtest, wähle zuerst über die Tastatur den Kurs aus.")
        new_user = User(id=update.message.chat_id, first_name=update.message.chat.first_name, last_name=update.message.chat.last_name, username=update.message.chat.username, title=update.message.chat.title, notifications=False, current_selection=0)
        bot.sendMessage(chat_id=update.message.chat_id, text="Benachrichtigungen nicht aktiv.")
        session.add(new_user)
        session.commit()
    else:
        if not entry.notifications:
            bot.sendMessage(chat_id=update.message.chat_id, text="Benachrichtigungen bereits inaktiv.")
        else:
            entry.notifications=False
            session.commit()
            bot.sendMessage(chat_id=update.message.chat_id, text="Benachrichtigungen deaktiviert.")    
    session.close()

start_handler = CommandHandler('start', start)
stop_handler = CommandHandler('stop', stop)
dispatcher.add_handler(start_handler)	
dispatcher.add_handler(stop_handler)

def echo(bot, update):
    session = DBSession()
    entry=session.query(User).filter(User.id==update.message.chat_id).first()
    if (not not entry) and entry.current_selection=="0":
        courses=session.execute(text("SELECT DISTINCT course FROM files")).fetchall()
        custom_keyboard=[]
        for course in courses:
            custom_keyboard.append([course.course])
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.sendMessage(chat_id=update.message.chat_id, text="Benachrichtigungen können mit /start und /stop bearbeitet werden. Dateien können direkt über die Tastatur ausgewählt werden.", reply_markup=reply_markup)
        entry.current_selection=1
        session.commit()
    elif (not not entry) and entry.current_selection=="1":
        files=session.query(FFile).filter(FFile.course==update.message.text) # unbedingt prüfen, ob überhaupt ergebnisse vorhanden sind
        custom_keyboard=[]
        for ffile in files:
            #print(ffile.name)
            custom_keyboard.append([ffile.name])
        custom_keyboard.append(["Zurück"])
        reply_markup = telegram.ReplyKeyboardMarkup(custom_keyboard)
        bot.sendMessage(chat_id=update.message.chat_id, text="test", reply_markup=reply_markup)
    session.close()
	
echo_handler = MessageHandler(Filters.text, echo)
dispatcher.add_handler(echo_handler)

updater.start_webhook(listen='localhost', port=4214, webhook_url=config['DEFAULT']['WebHookUrl'])
updater.idle()
updater.stop()
