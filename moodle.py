#!/usr/bin/env python
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from moodle_db_create import Base, User, FFile
import re, requests, telegram, urllib, configparser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from time import gmtime, strftime
from moodle_modules import save_file_to_db, moodle_login, sendtoall, sendfiletoall

#chatid=8047779
config = configparser.ConfigParser()
config.read('config/config.ini')
bot = telegram.Bot(token=config['DEFAULT']['BotToken'])
ignore_courses = ["31213"]

def getchatids():
    engine = create_engine('sqlite:///config/moodleusers.db')
    Base.metadata.bind = engine
    DBSession = sessionmaker(bind=engine)
    session = DBSession()
    chatids = []
    users = session.query(User).filter(User.notifications==True)
    for user in users:
        chatids.append(user.id)
    session.close()
    return chatids

def moodle_list(cookies):
    url = "https://www.moodle.tum.de/my/"
    response = requests.get(url, cookies=cookies).text
    return re.findall(r"href=\"https://www\.moodle\.tum\.de/course/view\.php\?id=([0-9]*)\"", response, re.MULTILINE)
def moodle_get(id, cookies):
    r = requests.get("https://www.moodle.tum.de/course/view.php?id=" + str(id), cookies=cookies)
    soup = BeautifulSoup(r.content, "lxml")
    cont = soup.select(".course-content < .weeks")
    cont = re.sub(r'( (?:aria\-owns=\"|id=\")random[0-9a-f]*_group\")', "", str(cont))
    cont = re.sub(r"(<img.*?>)", "", cont)
    cont = re.sub(r"(<span class=\"accesshide \">Diese Woche</span>)", "", cont)
    cont = re.sub(r"(<span class=\"accesshide \" >Diese Woche</span>)", "", cont)
    cont = re.sub(r"( current\")", "\"", cont)
    title = soup.title.string
    return [cont, title]
def moodle_save(id, cont):
    an = open(str(id) + ".txt", "w")
    an.write(str(urllib.parse.quote_plus(cont)))
    an.close()
def moodle_compare_extract(id, cont):
    ao = open(str(id) + ".txt", "r")
    old = ao.read()
    old = urllib.parse.unquote_plus(old)
    if old == cont:
        return {"change":False, "links":[]}
    else:
        for i in range(len(old)):
        #das ist der Anfang
            if not cont.startswith(old[:i]):
                #erstmal das ende finden
                for e in range(len(cont)):
                    if not cont.endswith(old[-e-1:]):
                        diff = cont[i-1:-e]
                        break
                entries = list()
                #Änderung in einem Link prüfen
                match = re.search(r"(^.*?</a>)", diff)
                if match is not None:
                    match = match.groups()[0]
                    counter = 0
                    while(re.search(r"(.*<a.*<\/a>)", match) is None):
                        match = cont[i-counter] + match
                        counter += 1
                    diff = cont[i-counter:-e]
                #Logging of the result
                log = open("moodle.log", "a")
                if len(diff) > 0:
                    log.write(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + " New change found in :" + id + "\n" + urllib.parse.quote_plus(diff) + "\n\n")
                else:
                    log.write(strftime("%Y-%m-%d %H:%M:%S", gmtime()) + " New unidentified change found in :" + id + "\n" + urllib.parse.quote_plus(old) + "\n\n")
                log.close()
                for part in diff.split("<a"):
                    if "href" in part:
                        url = re.search(r'(https:\/\/www\.moodle\.tum\.de\/mod.+?)\"', part)
                        name = re.search(r'\"instancename\">(.+?)<', part)
                        if url is not None and name is not None:
                            url = url.groups(1)
                            name = name.groups(1)
                            entries.append((url[0], name[0]))
                        elif url is not None and name is None:
                            name = re.search(r'\"instancename\">(.+)', part)
                            if name is not None:
                                url = url.groups(1)
                                name = name.groups(1)
                                entries.append((url[0], name[0]))								
                return {"change":True, "links":entries}
        return {"change":False, "links":[]}

cookies = {"MoodleSession":moodle_login()}
#cookies={"MoodleSession":"478cec338043640feb0c0e06f9f0e79e"}
pages = moodle_list(cookies)
chatids = getchatids()
newfiles=[]
engine = create_engine('sqlite:///config/moodleusers.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()
for course in pages:
    if not course in ignore_courses:
        cont = moodle_get(course, cookies)
        new = moodle_compare_extract(course, cont[0])
        if new["change"]:
            #moodle_save(course, cont[0])
            if len(new["links"]) > 0:
                for link in new["links"]:
                    file=save_file_to_db(cookies, link[0], link[1], cont[1], session, bot)
                    if(file[0]): 
                        newfiles.append({"file_id":file[1], "name":link[1], "course": cont[1]})
                    else:
                        newfiles.append({"file_id":"", "course":cont[1], "courseid":course})
            else:
                newfiles.append({"file_id":"", "course":cont[1], "courseid":course})
session.close()
oldcourse=""        
for newfile in newfiles:
    if newfile["course"]!=oldcourse:
        #Bearbeitung eines neuen Kurses
        oldcourse=newfile["course"]
        if newfile["file_id"]=="":
            #Wenn keine Datei gefunden wurde
            sendtoall(chatids, "Änderungen im Kurs <a href=\"https://www.moodle.tum.de/course/view.php?id="+newfile["courseid"]+"\">"+newfile["course"][6:]+"</a> erkannt.", bot)
        else:
            sendtoall(chatids, "Neue Dateien im "+newfile["course"]+":", bot)
            sendfiletoall(chatids, newfile["file_id"], newfile["course"][6:]+" - "+newfile["name"], bot)
    else:
        #Wenn das nicht der erste Eintrag eines neuen Kurses ist
        if not newfile["file_id"]==0:
            sendfiletoall(chatids, newfile["file_id"], newfile["course"][6:]+" - "+newfile["name"], bot)