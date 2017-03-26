#!/bin/python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import configparser
from datetime import datetime
from moodle_db_create import BBlock
from moodle_db_create import Base
from moodle_db_create import CCourse
from moodle_db_create import FFile
from moodle_db_create import MMedia
from moodle_db_create import UUser
import os
import re
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import telegram
from telegram import InlineKeyboardButton
from telegram import InlineKeyboardMarkup
from telegram.error import ChatMigrated
from telegram.error import NetworkError
from telegram.error import TimedOut
from telegram.error import Unauthorized
from urllib import parse

engine = create_engine('sqlite:///config/moodleusers.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

config = configparser.ConfigParser()
config.read('config/config.ini')
ignore_courses = []

bot = telegram.Bot(token=config['DEFAULT']['BotToken'])

def send(chat_id, message):
    button_list = [[InlineKeyboardButton("🛡️ Benachrichtigungen deaktivieren", callback_data="5$0"), InlineKeyboardButton("📆 Semester auswählen", callback_data="4"), InlineKeyboardButton("🔍 Kurse anzeigen", callback_data="1")]]
    reply_markup = InlineKeyboardMarkup(button_list)
    try:
        bot.sendMessage(chat_id=chat_id, text=message, parse_mode=telegram.ParseMode.HTML, reply_markup=reply_markup)
    except Unauthorized:
        session = DBSession()
        user = session.query(UUser).filter(UUser.id == chat_id).first()
        user.notifications = False
        session.commit()
        session.close()
        return True
    except (TimedOut, NetworkError):
        return send(chat_id, message)
    except ChatMigrated as e:
        session = DBSession()
        user = session.query(UUser).filter(UUser.id == user_id).first()
        user.id = e.new_chat_id
        session.commit()
        session.close()
        return True

class Moodleuser:
    def __init__(self, username, password):
        self._username = username
        self.__password = password
        self._session = self.__Login() #login
        self._courses = self.__ListCourses() #courselist + name
        for course in self._courses[0]:
            if not course[0] in ignore_courses:
                a = Course(course[0], course[1], self._session)
		
    def __Login(self):
        s = requests.Session()
        s.get("https://www.moodle.tum.de/Shibboleth.sso/Login?providerId=https%3A%2F%2Ftumidp.lrz.de%2Fidp%2Fshibboleth&target=https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php", allow_redirects=True)
        headers = {'Content-Type': 'application/x-www-form-urlencoded', "Origin": "https://tumidp.lrz.de", "Connection": "keep-alive", "Content-Length":"74"}
        auth = s.post("https://tumidp.lrz.de/idp/profile/SAML2/Redirect/SSO?execution=e1s1", headers=headers, data={"j_username": self._username, "j_password": self.__password, "_eventId_proceed": "", "donotcache":"1"}, allow_redirects=False)
        resp = re.search(r"SAMLResponse\" value=\"(.*)\"/>", auth.text)
        s.cookies = requests.utils.add_dict_to_cookiejar(s.cookies, {"_shibstate_123":"https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php"})
        s.post("https://www.moodle.tum.de/Shibboleth.sso/SAML2/POST", allow_redirects=True, data={"SAMLResponse":resp.groups()[0], "RelayState":"cookie:123"})
        return s
	
    def __ListCourses(self):
        url = "https://www.moodle.tum.de/my/?lang=de"
        response = self._session.get(url).text
        if response.find("<title>Meine Startseite</title>") > -1:
            courselist = re.findall(r"href=\"https://www\.moodle\.tum\.de/course/view\.php\?id=([0-9]*)\">(.*?)<", response, re.MULTILINE)
            fullname = re.search(r"userpic defaultuserpic\" width=\"60\" height=\"60\" />(.*?)<", response).groups(1)[0]
            return [courselist, fullname]
        else:
            return [[], ""]
			
class Course:
    def __init__(self, courseid, coursename, sess):
        self._courseid = courseid
        self._coursename = coursename
        self._session = sess
        self._changes = list()
        self.__GetContent()
        # Jetzt mit der DB abgleichen
        session = DBSession()
        courseentry = session.query(CCourse).filter(CCourse.id == courseid).first()
        if not courseentry:
            #create course
            new_course = CCourse(id=self._courseid, name=self._coursename, semester=self._semester)
            session.add(new_course)
            session.commit()
        session.close()
        #jetzt splitten und den rest
        self.__blocks = self.__Split()
        #Hier kommt jetzt die Ausgabe oder sowas von allen Änderungen, die in self.__changes gespeichert sind
        self.__PropagateChanges()
		
    def __GetContent(self):
        r = self._session.get("https://www.moodle.tum.de/course/view.php?id=" + str(self._courseid) + "&lang=de")
        soup = BeautifulSoup(r.content, "lxml")
        if "<title>Kurs:" in r.text:
            cont = soup.select(".course-content")
            cont = re.sub(r'( (?:aria\-owns=\"|id=\")random[0-9a-f]*_group\")', "", str(cont))
            cont = re.sub(r"(<img.*?>)", "", cont)
            cont = re.sub(r"(<span class=\"accesshide \">Diese Woche</span>)", "", cont)
            cont = re.sub(r"(<span class=\"accesshide \" >Diese Woche</span>)", "", cont)
            cont = re.sub(r"( current\")", "\"", cont)
            self.__content = cont
            self._semester = soup.select('span[itemprop="title"]')[1].string
        else:
            self.__content = ""
            self._semester = ""
		
    def __Split(self):
        content = self.__content
        #split in blocks first
        soup = BeautifulSoup(content, "lxml")
        blocks = soup.select(".mod-indent") # hier müssen wir auch noch die Physik-Blöcke mit aufnehmen
        blocks2 = soup.select(".summary p")
        bl = list()
        for block in blocks2:
            b = Block(block, self._courseid, self._session)
            bl.append(b)
            if b._changelist["type"] != "none":
            	for change in b._changelist["values"]:
                    self._changes.append(change)
        for block in blocks:
            b = Block(block.next_sibling.contents[0], self._courseid, self._session)
            bl.append(b)
            if b._changelist["type"] != "none":
                for change in b._changelist["values"]:
                    self._changes.append(change)
        return bl
		
    def __PropagateChanges(self):
        #Prepare message
        if len(self._changes) > 0:
            counter = 0
            message = {0:"Änderungen im Kurs <a href=\"https://www.moodle.tum.de/course/view.php?id=" + str(self._courseid) + "\">" + self._coursename + "</a> erkannt:"}
            for entry in self._changes:
                if entry["type"] == "url":
                    print(entry)
                    toadd = "\n<a href=\"" + entry["url"] + "\">" + entry["title"] + "</a>"
                    if len(entry["contentafterlink"]) > 0:
                        toadd += " - " + entry["contentafterlink"]
                elif entry["type"] == "text":
                    print(entry)
                    toadd = "\n" + entry["cont"]
                else:
                    toadd = ""
                if len(message[counter] + toadd) > 4096:
                    counter += 1
                    message[counter] = toadd
                else:
                    message[counter] = message[counter] + toadd
            #fetch users and send message to all of them
            session = DBSession()
            users = session.query(UUser).filter(UUser.notifications == True, UUser.semester == self._semester)
            for user in users:
                user.counter += 1
                session.commit()
                for key, msg in message.items():
                    send(user.id, msg)
            session.close()
		
		
class Block:
    def __init__(self, block, course, session):
        self.__content = block
        self._course = course
        self._session = session
        self._changelist = {"type":"none"}
        self.__block = self.__AnalyseBlock()
		
    def __AnalyseBlock(self):
        soup = self.__content
        if "activityinstance" in soup.get('class', []):
            activityinstance = soup
            self.__type = "url"
            self._url = activityinstance.select("a")[0].get('href')
            self._title = activityinstance.select(".instancename")[0].find(text=True, recursive=False)
            try:
                self._cont = soup.parent.select(".contentafterlink")[0].text
            except (AttributeError, IndexError): 
                self._cont = ""
            #Erstellen den Link-Objekts später, um wiederholte Downloads zu verhindern
        elif "contentwithoutlink" in soup.get('class', []):
            self.__type = "contentwithoutlink"
            self._url = ""
            self._title = ""
            self._cont = soup.text
        else:
            self.__type = "unknown"
            self._url = ""
            self._cont = soup.text
            self._title = ""
        #speichern bzw abgleichen mit DB
        session = DBSession()
        blockentry = session.query(BBlock).filter(BBlock.url == self._url, BBlock.cont == self._cont, BBlock.title == self._title).first()
        if not blockentry:
            #create block
            print("Adding " + self._url + " " + self._title + " " + self._cont)
            new_block = BBlock(url=self._url, cont=self._cont, type=self.__type, course=self._course, title=self._title)
            session.add(new_block)
            session.commit()
            ## Hier die Änderung registrieren -> Bei Dateien 
            if self.__type == "url":
                link = Link(self)
                #speichern als Link zu message/Datei
                self._changelist = {"type":"url", "values": link._values} #{"type":"url", "title":self._title, "url":link._url, "contentafterlink":self._cont}}
            else:
                #speichern des Blockinhalts
                self._changelist = {"type":"text", "values": [{"type":"text", "cont":self._cont}]}
        if not not blockentry and re.match(r"https:\/\/www\.moodle\.tum\.de\/mod\/(folder|lti)\/.*?id=([0-9]*)", self._url) is not None:
            #Scan von Ordnern
            link = Link(self)
            #speichern als Link zu message/Datei
            self._changelist = {"type":"url", "values": link._values}
        session.close()
		
class Link:
    def __init__(self, blockself):
        self._url = blockself._url
        self._title = blockself._title
        self._firsttitle = self._title
        self._course = blockself._course
        self._cont = blockself._cont
        self._session = blockself._session
        normallink = re.match(r"https:\/\/www\.moodle\.tum\.de\/mod\/(.*?)\/.*?id=([0-9]*)", self._url)
        dllink = re.match(r"https://www\.moodle\.tum\.de/pluginfile\.php/([0-9]*)/mod_folder/content/0/(.*)", self._url)
        if normallink is not None:
            self._urltype = normallink.groups(1)[0]
            self._id = int(normallink.groups(1)[1])
            if self._urltype == "resource":
                #zusätzliche Verarbeitung als Datei
                self.__ProcessFile()
            elif self._urltype == "folder":
                #Parse as folder    
                self.__ParseFolder()
            elif self._urltype == "lti": 
                #videoordner
                self.__ParseVideoFolder()
            else: #URL entspricht Muster ist aber nicht folder oder ressource
                self._urltype = "unknown"
                self._id = 0
                self._values = [{"type": "url", "title": self._title, "url": self._url, "contentafterlink":self._cont}]
        elif dllink is not None: 
            self._id = dllink.groups(1)[0]
            self.__ProcessFile()
        else: #Link entspricht nicht dem Schema
            self._values = []
        
    def __Download(self):
        print("Downloading from " + str(self._url))
        r = self._session.get(self._url, stream=True)
        filename = parse.unquote(r.url.split('/')[-1])
        with open(filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024): 
                if chunk: # filter out keep-alive new chunks
                    f.write(chunk)
        return filename
    
    def __ProcessFile(self):
        session = DBSession()
        fileentry = session.query(FFile).filter(FFile.id == self._id, FFile.title == self._title).first()
        if not fileentry:
            #Datei ist noch nicht gespeichert
            filename = self.__Download()
            #Dateigröße checken
            if os.path.getsize(filename) < 50 * 1024 * 1024:
                #zu Telegram hochladen & löschen
                coursename = session.query(CCourse).filter(CCourse.id == self._course).one()
                resp = bot.sendDocument(chat_id=-1001114864097, document=open(filename, 'rb'), caption=coursename.name + " - " + self._title)
                os.remove(filename)
                #in DB speichern
                new_file = FFile(id=self._id, course=self._course, title=self._title, message_id=resp.message_id, date=datetime.now())
                self._url = "https://t.me/tummoodle/" + str(resp.message_id)        
                session.add(new_file)
                session.commit()
            else:
                os.remove(filename)
                self._url = "https://www.moodle.tum.de/mod/resource/view.php?id=" + str(self._id)
            #Speichern der Änderungen für Rückgabe
            self._values = [{"type": "url", "title": self._title, "url": self._url, "contentafterlink":self._cont}]
        else: 
        #    self._url = "https://t.me/tummoodle/" + str(fileentry.message_id) #Nicht mehr aktiv, da Titel bei Änderung auch geändert, so würde jeder Ordner immer augegeben werden
            self._values = []
        session.close()
        
    def __ParseVideoFolder(self):
        resp = self._session.get(re.sub(r"view", "launch", self._url))
        soup = BeautifulSoup(resp.text, "lxml")
        oauth = soup.select("input")
        values = {}
        for inp in oauth:
            values[inp.get('name')] = inp.get('value')
        r = self._session.post(soup.select("form")[0].get("action"), data=values)
        courseid = re.search(r"CatalogId: '([a-f|0-9|-]*)',", r.text).groups(1)[0]
        reqbody = {"IsViewPage":True, "CatalogId":courseid, "CurrentFolderId":courseid, "ItemsPerPage":200, "PageIndex":0, "CatalogSearchType":"SearchInFolder"}
        medialist = self._session.post("https://streams.tum.de/Mediasite/Catalog/Data/GetPresentationsForFolder", data=reqbody).json()
        self._values = []
        session = DBSession()
        for media in medialist["PresentationDetailsList"]:
            medium = session.query(MMedia).filter(MMedia.playerurl == media["PlayerUrl"]).first()
            if not medium:
                #create course
                datetim = datetime.strptime(media["FullStartDate"], "%m/%d/%Y %H:%M:%S")
                new_medium = MMedia(name=media["Name"], playerurl=media["PlayerUrl"], date=datetim, course=self._course)
                session.add(new_medium)
                session.commit()
        session.close()            
            
    def __ParseFolder(self):
        #Download filelist
        r = self._session.get("https://www.moodle.tum.de/mod/folder/view.php?id=" + str(self._id))
        soup = BeautifulSoup(r.text, "lxml")
        files = soup.select(".fp-filename-icon")
        self._values = []
        for file in files:
            try:
                self._url = re.sub(r"\?forcedownload=1", "", file.select("a")[0].get('href'))
                self._title = self._firsttitle + " - " + file.select(".fp-filename")[0].text
                #initialize new Link element
                link = Link(self)
                self._values += link._values
            except IndexError:
                pass

            
			
Moodleuser(config['DEFAULT']['Username'], config['DEFAULT']['Password'])