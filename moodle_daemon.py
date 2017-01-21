#!/bin/python

from telegram.ext import Updater
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler, Filters
import logging, configparser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from moodle_db_create import Group, User, Base
engine = create_engine('sqlite:///config/moodleusers.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

config = configparser.ConfigParser()
config.read('config/config.ini')
updater = Updater(token=config['DEFAULT']['BotToken'])
dispatcher = updater.dispatcher

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.DEBUG)

def fill_db(chatid, first_name, title, session):
    if chatid > 0:
        #chat mit user
        if session.query(User).filter(User.id == chatid).first() is None:
            #insert user in db
            new_user = User(id=chatid, first_name=first_name)
            session.add(new_user)
            session.commit()
            return True
        else:
            return False
    else:
        #Gruppenchat
        if session.query(Group).filter(Group.id == chatid).first() is None:
            #insert group in db
            new_group = Group(id=chatid, title=title)
            session.add(new_group)
            session.commit()
            return True
        else:
            return False

def delete_user(chatid, session):
    if chatid > 0:
        user = session.query(User).filter(User.id == chatid).first()
        if user is None:
            return False
        else:
            #delete entry
            session.delete(user)
            session.commit()
            return True
    else:
        group = session.query(Group).filter(Group.id == chatid).first()
        if group is None:
            return False
        else:
            #delete entry
            session.delete(group)
            session.commit()
            return True
			
def start(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id, text="Hallo, ich bin der TUM-Moodlebot. Ich benachrichtige alle registrierten Nutzer oder Gruppen über Änderungen in entsprechenden Moodle-Kursen. Du kannst meine Dienste mit /start und /stop aktivieren und deaktivieren.")
    session = DBSession()
    if(fill_db(update.message.chat_id, update.message.chat.first_name, update.message.chat.title, session)):
        bot.sendMessage(chat_id=update.message.chat_id, text="Chat zur DB hinzugefügt.")
    else:
        bot.sendMessage(chat_id=update.message.chat_id, text="Chat breits in DB.")
    session.close()
def stop(bot, update):
    session = DBSession()
    if(delete_user(update.message.chat_id, session)):
        bot.sendMessage(chat_id=update.message.chat_id, text="Chat aus DB gelöscht.")
    else:
        bot.sendMessage(chat_id=update.message.chat_id, text="Chat nicht in DB.")
    session.close()

start_handler = CommandHandler('start', start)
stop_handler = CommandHandler('stop', stop)
dispatcher.add_handler(start_handler)	
dispatcher.add_handler(stop_handler)

def echo(bot, update):
    bot.sendMessage(chat_id=update.message.chat_id, text="Im Moment kann ich noch nicht auf Dinge antworten.")
	
echo_handler = MessageHandler(Filters.text, echo)
dispatcher.add_handler(echo_handler)

updater.start_webhook(listen='localhost', port=4213, webhook_url=config['DEFAULT']['BotToken'])
updater.idle()
updater.stop()
