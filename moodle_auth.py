import requests, re, configparser
from moodle_db_create import Base, User, FFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from moodle_modules import moodle_login

config = configparser.ConfigParser()
config.read('config/config.ini')

print(moodle_login())