#!/bin/python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from moodle_db_create import Group, User, Base
engine = create_engine('sqlite:///config/moodleusers.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

groupname="ldkf"
chatid=8047779
#check if user is already in DB

def fill_db(chatid, first_name, title):
	if chatid>0:
		#chat mit user
		if session.query(User).filter(User.id==chatid).first() is None:
			#insert user in db
			new_user=User(id=chatid, first_name=first_name)
			session.add(new_user)
			session.commit()
			return True
		else:
			return False
	else:
		#Gruppenchat
		if session.query(Group).filter(Group.id==chatid).first() is None:
			#insert group in db
			new_group=Group(id=chatid, title=title)
			session.add(new_group)
			session.commit()
			return True
		else:
			return False

#grp=session.query(Group).filter(Group.id==-8047779).first()
#session.delete(grp)
#session.commit()

def delete_user(chatid):
	if chatid>0:
		user=session.query(User).filter(User.id==chatid).first()
		if user is None:
			return False
		else:
			#delete entry
			session.delete(user)
			session.commit()
			return True
	else:
		group=session.query(Group).filter(Group.id==chatid).first()
		if group is None:
			return False
		else:
			#delete entry
			session.delete(group)
			session.commit()
			return True
			

print(delete_user(8047779))			
			
print("All entries:")
groups=session.query(Group).all()
for group in groups:
	print("Group-id: "+str(group.id)+" group-name: "+group.title)
users=session.query(User).all()
for user in users:
	print("user-id: "+str(user.id)+" first-name: "+user.first_name)
	
session.close()