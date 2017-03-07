# created by Alwin Ebermann (alwin@alwin.net.au)
# -*- coding: utf-8 -*-
import requests, telegram, configparser, os
from moodle_db_create import Base, User, FFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from moodle_modules import save_file_to_db

engine = create_engine('sqlite:///config/moodleusers.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()
config = configparser.ConfigParser()
config.read('config/config.ini')
cookies={"MoodleSession":"dfb3b65f7b27d706a37a5527d73ce115"}
bot = telegram.Bot(token=config['DEFAULT']['BotToken'])

print(save_file_to_db(cookies, "https://www.moodle.tum.de/mod/resource/view.php?id=508673", "Zentralübung 3", "Analysis 1", session))
