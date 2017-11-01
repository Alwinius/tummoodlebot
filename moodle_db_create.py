#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import create_engine
from sqlalchemy.orm import relationship
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
    # for tummoodlebot 2.0
    semester = Column(String(250), nullable=True)
    counter = Column(Integer, nullable=True)
    current_selection = Column(Integer, nullable=True)


class FFile(Base):
    # von moodle.py eingetragen
    __tablename__ = 'file'
    id = Column(Integer, primary_key=True)
    title = Column(String(250), primary_key=True)
    message_id = Column(String(250), nullable=True)  # dont ask why I made this a string
    url = Column(String(1000), nullable=True)
    course = Column(Integer, ForeignKey('course.id'))
    date = Column(DateTime, nullable=False)
    coursedata = relationship("CCourse", back_populates="files")


class BBlock(Base):
    # von moodle.py eingetragen
    __tablename__ = 'block'
    type = Column(String(250), nullable=False)
    title = Column(String(500), primary_key=True)
    url = Column(String(2000), primary_key=True)
    course = Column(Integer, ForeignKey('course.id'))
    cont = Column(String(2500), primary_key=True)


class CCourse(Base):
    # von moodle.py erstellt -> aus der Übersichtsseite oder beim Scan der Kursseite
    __tablename__ = 'course'
    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    semester = Column(String(250), nullable=True)
    videoidentifier = Column(String(250), nullable=True)
    files = relationship("FFile", back_populates="coursedata")
    media = relationship("MMedia", back_populates="coursedata")
    location = Column(String(250), nullable=False)
    url = Column(String(2500), nullable=True)


class MMedia(Base):
    __tablename__ = 'media'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(250), nullable=False)
    playerurl = Column(String(2000))
    date = Column(DateTime, nullable=False)
    course = Column(Integer, ForeignKey('course.id'))
    coursedata = relationship("CCourse", back_populates="media")
    mp4url1 = Column(String(2000))
    mp4url2 = Column(String(2000))


engine = create_engine('sqlite:///config/moodleusers.sqlite')
Base.metadata.create_all(engine)
