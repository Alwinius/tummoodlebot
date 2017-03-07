#!/bin/python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from moodle_db_create import Base, User, FFile
engine = create_engine('sqlite:///moodleusers-old.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()			
			
print("All entries:")
users=session.query(User).all()
for user in users:
	print("id: "+str(user.id)+" first-name: "+user.first_name+" last-name: "+user.last_name+" username: "+user.username+" title: "+user.title)
files=session.query(FFile).all()
for ffile in files:
	print("id: "+str(ffile.id)+" name: "+ffile.name+" message-id: "+ffile.message_id+" course: "+ffile.course+" date: "+str(ffile.date))
	
session.close()