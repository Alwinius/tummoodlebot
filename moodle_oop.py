#!/bin/python3
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import configparser
from datetime import datetime
from moodle_db_create import BBlock
from moodle_db_create import Base
from moodle_db_create import CCourse
from moodle_db_create import FFile
from moodle_db_create import UUser
import os
import re
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import telegram
from urllib import parse

engine = create_engine('sqlite:///config/moodleusers.sqlite')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)

config = configparser.ConfigParser()
config.read('config/config.ini')
ignore_courses = []

bot = telegram.Bot(token=config['DEFAULT']['BotToken'])

class Moodleuser:
    def __init__(self, username, password):
        self._username = username
        self.__password = password
        self._cookie = {"MoodleSession":self.__Login()} #login
        self._courses = self.__ListCourses() #courselist + name
        for course in self._courses[0]:
            if not course[0] in ignore_courses:
                a = Course(self._cookie, course[0], course[1])
		
    def __Login(self):
        s = requests.Session()
        login = s.get("https://www.moodle.tum.de/Shibboleth.sso/Login?providerId=https%3A%2F%2Ftumidp.lrz.de%2Fidp%2Fshibboleth&target=https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php", allow_redirects=True)
        headers = {'Content-Type': 'application/x-www-form-urlencoded', "Origin": "https://tumidp.lrz.de", "Connection": "keep-alive", "Content-Length":"74"}
        auth = s.post("https://tumidp.lrz.de/idp/profile/SAML2/Redirect/SSO?execution=e1s1", headers=headers, data={"j_username": self._username, "j_password": self.__password, "_eventId_proceed": "", "donotcache":"1"}, allow_redirects=False)
        resp = re.search(r"SAMLResponse\" value=\"(.*)\"/>", auth.text)
        s.cookies = requests.utils.add_dict_to_cookiejar(s.cookies, {"_shibstate_123":"https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php"})
        final = s.post("https://www.moodle.tum.de/Shibboleth.sso/SAML2/POST", allow_redirects=True, data={"SAMLResponse":resp.groups()[0], "RelayState":"cookie:123"})
        return requests.utils.dict_from_cookiejar(s.cookies)["MoodleSession"]
	
    def __ListCourses(self):
        url = "https://www.moodle.tum.de/my/?lang=de"
        response = requests.get(url, cookies=self._cookie).text
        if response.find("<title>Meine Startseite</title>") > -1:
            courselist = re.findall(r"href=\"https://www\.moodle\.tum\.de/course/view\.php\?id=([0-9]*)\">(.*?)<", response, re.MULTILINE)
            fullname = re.search(r"userpic defaultuserpic\" width=\"60\" height=\"60\" />(.*?)<", response).groups(1)[0]
            return [courselist, fullname]
        else:
            return [[], ""]
			
class Course:
    def __init__(self, cookie, courseid, coursename):
        self._courseid = courseid
        self._coursename = coursename
        self._cookie = cookie
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
        r = requests.get("https://www.moodle.tum.de/course/view.php?id=" + str(self._courseid) + "&lang=de", cookies=self._cookie)
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
            b = Block(block, self._courseid, self._cookie)
            bl.append(b)
            if b._changelist["type"] != "none":
            	for change in b._changelist["values"]:
                    self._changes.append(change)
        for block in blocks:
            b = Block(block.next_sibling.contents[0], self._courseid, self._cookie)
            bl.append(b)
            if b._changelist["type"] != "none":
                for change in b._changelist["values"]:
                    self._changes.append(change)
        return bl
		
    def __PropagateChanges(self):
        #Prepare message
        if len(self._changes) > 0:
            counter = 0
            message = {0:"Änderungen im Kurs <a href=\"https://www.moodle.tum.de/course/view.php?id=" + self._courseid + "\">" + self._coursename + "</a> erkannt:"}
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
                try:
                    message[counter]=message[counter]+toadd
                except KeyError:
                    message[counter]=toadd
            #fetch users and send message to all of them
            session = DBSession()
            chatids = list()
            users = session.query(UUser).filter(UUser.notifications == True)
            for user in users:
                chatids.append(user.id)
                for key, msg in message.items():
                    bot.sendMessage(chat_id=user.id, text=msg, parse_mode=telegram.ParseMode.HTML)
                    #catch errors here
            session.close()
		
		
class Block:
    def __init__(self, block, course, cookie):
        self.__content = block
        self._course = course
        self._cookie = cookie
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
        if not not blockentry and re.match(r"https:\/\/www\.moodle\.tum\.de\/mod\/folder\/.*?id=([0-9]*)", self._url) is not None:
            #Scan von Ordnern
            link = Link(self)
            #speichern als Link zu message/Datei
            self._changelist = {"type":"url", "values": link._values}
        session.close()
		
class Link:
    def __init__(self, blockself):
        self._url=blockself._url
        self._title=blockself._title
        self._firsttitle=self._title
        self._course=blockself._course
        self._cont=blockself._cont
        self._cookie=blockself._cookie
        normallink = re.match(r"https:\/\/www\.moodle\.tum\.de\/mod\/(.*?)\/.*?id=([0-9]*)", self._url)
        dllink=re.match(r"https://www\.moodle\.tum\.de/pluginfile\.php/([0-9]*)/mod_folder/content/0/(.*)", self._url)
        if normallink is not None:
            self._urltype = normallink.groups(1)[0]
            self._id = int(normallink.groups(1)[1])
            if self._urltype == "resource":
                #zusätzliche Verarbeitung als Datei
                self.__ProcessFile()
            elif self._urltype=="folder":
                #Parse as folder    
                self.__ParseFolder()
            else: #URL entspricht Muster ist aber nicht folder oder ressource
                self._urltype = "unknown"
                self._id = 0
                self._values=[{"type": "url", "title": self._title, "url": self._url, "contentafterlink":self._cont}]
        elif dllink is not None: 
                self._id=dllink.groups(1)[0]
                self.__ProcessFile()
        else: #Link entspricht nicht dem Schema
            self._values=[]
        
    def __Download(self):
        print("Downloading from " + str(self._url))
        r = requests.get(self._url, stream=True, cookies=self._cookie)
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
            self._values=[{"type": "url", "title": self._title, "url": self._url, "contentafterlink":self._cont}]
        else: 
        #    self._url = "https://t.me/tummoodle/" + str(fileentry.message_id)
            self._values=[]
        session.close()
    
    def __ParseFolder(self):
        #Download filelist
        r=requests.get("https://www.moodle.tum.de/mod/folder/view.php?id=" + str(self._id), cookies=self._cookie)
        soup=BeautifulSoup(r.text, "lxml")
        files=soup.select(".fp-filename-icon")
        self._values=[]
        for file in files:
            try:
                self._url=re.sub(r"\?forcedownload=1", "", file.select("a")[0].get('href'))
                self._title=self._firsttitle+" - "+file.select(".fp-filename")[0].text
                #initialize new Link element
                link=Link(self)
                self._values+=link._values
            except IndexError:
                pass

            
			
alwin = Moodleuser(config['DEFAULT']['Username'], config['DEFAULT']['Password'])

#physik = Course(alwin._cookie, 31297, "Physik für Elektroingenieure")