#!/bin/python
import os, sys
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine

Base = declarative_base()

class User(Base):
	__tablename__='user'
	id=Column(Integer, primary_key=True)
	first_name=Column(String(250), nullable=False)
	username=Column(String(250), nullable=True)

class Group(Base):
	__tablename__='group'
	id=Column(Integer, primary_key=True)
	title=Column(String(250), nullable=False)
	
engine = create_engine('sqlite:///config/moodleusers.db')
Base.metadata.create_all(engine)
	
	
#{'message': {'date': 1484417985, 'group_chat_created': False, 'new_chat_title': '', 'delete_chat_photo': False, 'from': {'id': 8047779, 'type': '', 'first_name': 'Alwin', 'username': 'Alwinius', 'last_name': ''}, 'photo': [], 'caption': '', 'migrate_from_chat_id': 0, 'supergroup_chat_created': False, 'new_chat_photo': [], 'message_id': 53, 'entities': [{'type': 'bot_command', 'offset': 0, 'length': 19}], 'text': '/start@tummoodlebot', 'channel_chat_created': False, 'migrate_to_chat_id': 0, 'chat': {'id': -34410571, 'last_name': '', 'type': 'group', 'title': 'LDKF-Admin-Spielgruppe', 'username': '', 'first_name': '', 'all_members_are_admins': False}}, 'update_id': 212239504}

#{'message': {'date': 1484418006, 'group_chat_created': False, 'new_chat_title': '', 'delete_chat_photo': False, 'from': {'id': 8047779, 'type': '', 'first_name': 'Alwin', 'username': 'Alwinius', 'last_name': ''}, 'photo': [], 'caption': '', 'migrate_from_chat_id': 0, 'supergroup_chat_created': False, 'new_chat_photo': [], 'message_id': 55, 'entities': [], 'text': 'test', 'channel_chat_created': False, 'migrate_to_chat_id': 0, 'chat': {'id': 8047779, 'last_name': '', 'type': 'private', 'title': '', 'username': 'Alwinius', 'first_name': 'Alwin', 'all_members_are_admins': False}}, 'update_id': 212239505}