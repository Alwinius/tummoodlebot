#!/bin/python
# -*- coding: utf-8 -*-
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UUser(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    notifications = Column(Boolean(), nullable=False)
    #for tummoodlebot 2.0
    current_selection = Column(String(250), nullable=True)
    user_group = Column(String(250), nullable=True)

class FFile(Base):
    #von moodle.py eingetragen
    __tablename__ = 'file'
    id = Column(Integer, primary_key=True)
    title = Column(String(250), primary_key=True)
    message_id = Column(String(250), nullable=False)
    course = Column(Integer, ForeignKey('course.id'))
    date = Column(DateTime, nullable=False)
    
class BBlock(Base):
    #von moodle.py eingetragen
    __tablename__ = 'block'
    type = Column(String(250), nullable=False)
    title = Column(String(500), primary_key=True)
    url = Column(String(2000), primary_key=True)
    course = Column(Integer, ForeignKey('course.id'))
    cont = Column(String(2500), primary_key=True)
	
class CCourse(Base):
    #von moodle.py erstellt -> aus der Übersichtsseite oder beim Scan der Kursseite
    __tablename__ = 'course'
    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    semester = Column(String(250), nullable=True)
    

class MMedia(Base):
    __tablename__ = 'media'
    name = Column(String(250), nullable=False)
    playerurl=Column(String(2000), primary_key=True)
    date = Column(DateTime, nullable=False)
    course = Column(Integer, ForeignKey('course.id'))

engine = create_engine('sqlite:///config/moodleusers.sqlite')
Base.metadata.create_all(engine)	