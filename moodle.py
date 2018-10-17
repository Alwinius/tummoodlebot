#!/usr/bin/env python3
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
import json
from time import sleep
from shutil import move
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
current_semester = config["DEFAULT"]["CurrentSemester"]

bot = telegram.Bot(token=config['DEFAULT']['BotToken'])


def send(chat_id, message):
    button_list = [[InlineKeyboardButton("🛡️ Ben. deaktivieren", callback_data="5$0"),
                    InlineKeyboardButton("📆 Sem. wählen", callback_data="4"),
                    InlineKeyboardButton("🔍 Kurse anzeigen", callback_data="1")]]
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
        user = session.query(UUser).filter(UUser.id == chat_id).first()
        user.id = e.new_chat_id
        session.commit()
        session.close()
        return True


def download(url, session=requests):
    r = session.get(url, stream=True)
    filename = parse.unquote(r.url.split('/')[-1])
    print("Downloading "+filename)
    with open(filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
    return filename


class Moodleuser:
    def __init__(self, username, password):
        self._username = username
        self.__password = password
        self._session = self.__Login()  # login
        self._courses = self.__ListCourses()  # courselist + name
        for course in self._courses[0]:
            if not course[1] in ignore_courses and course[2] == current_semester:
                Course({"id": course[1], "name": course[0], "semester": course[2], "location": "moodle", "session": self._session})

    def __Login(self):
        s = requests.Session()
        s.get(
            "https://www.moodle.tum.de/Shibboleth.sso/Login?providerId=https%3A%2F%2Ftumidp.lrz.de%2Fidp%2Fshibboleth&target=https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php",
            allow_redirects=True)
        headers = {'Content-Type': 'application/x-www-form-urlencoded', "Origin": "https://tumidp.lrz.de",
                   "Connection": "keep-alive", "Content-Length": "74"}
        auth = s.post("https://tumidp.lrz.de/idp/profile/SAML2/Redirect/SSO?execution=e1s1", headers=headers,
                      data={"j_username": self._username, "j_password": self.__password, "_eventId_proceed": "",
                            "donotcache": "1"}, allow_redirects=False)
        resp = re.search(r"SAMLResponse\" value=\"(.*)\"/>", auth.text)
        s.cookies = requests.utils.add_dict_to_cookiejar(s.cookies, {
            "_shibstate_123": "https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php"})
        s.post("https://www.moodle.tum.de/Shibboleth.sso/SAML2/POST", allow_redirects=True,
               data={"SAMLResponse": resp.groups()[0], "RelayState": "cookie:123"})
        return s

    def __ListCourses(self):
        url = "https://www.moodle.tum.de/my/?lang=de"
        response = self._session.get(url).text
        if response.find("<title>Meine Startseite</title>") > -1:
            courselist = re.findall(
                r"<a title=\"(.*?)\" href=\"https://www\.moodle\.tum\.de/course/view\.php\?id=([0-9]*)\">.*?coc-metainfo\">\((.*?)  \|",
                response, re.MULTILINE)
            fullname = re.search(r'<span class="usertext mr-1">(.*)</span>', response).groups(1)[0]
            return [courselist, fullname]
        else:
            return [[], ""]


class Course:
    def __init__(self, course):
        self._courseid = course["id"]
        self._coursename = course["name"]
        print(" - " + self._coursename)
        self._session = course["session"] if "session" in course else requests.session()
        self._changes = []
        self._semester = course["semester"]
        self._location= course["location"]
        self._url = course["url"] if "url" in course else ""
        if course["location"] == "moodle":
            self.__GetContent()
            # Jetzt mit der DB abgleichen
            session = DBSession()
            courseentry = session.query(CCourse).filter(CCourse.id == course["id"]).first()
            if not courseentry:
                # create course
                new_course = CCourse(id=self._courseid, name=self._coursename, semester=course["semester"], location="moodle")
                session.add(new_course)
                session.commit()
                os.mkdir(config['DEFAULT']['CopyDir'] + re.sub('[^\w\-_\. ()\[\]]', '_', self._coursename))
            else:
                if courseentry.location != "moodle":
                    # Obacht, jetzt kommen spezial-Sachen f�r moodle-kurse
                    self._location=courseentry.location
                    if self._location == "moodle_basic":
                        # Jetzt suchen wir nur noch Links nach Dateien ab
                        # Also suchen wir erstmal alle Links raus
                        soup=BeautifulSoup(self.__content, "lxml")
                        a = soup("a")
                        session = DBSession()
                        for b in a:
                            myobject = type("Block", (object,), {})() # this is a horrible hack, I know
                            myobject._title = b.text
                            myobject._url = b["href"]
                            myobject._course = self._courseid
                            myobject._session = self._session
                            myobject._cont = ""
                            l = Link(myobject)
                            for lin in l._values:
                                if lin is not None and "t.me" in lin["url"]:
                                    self._changes.append(lin)
                else:
                    # jetzt splitten und den rest
                    self.__blocks = self.__Split()
            session.close()
        else:
            # jetzt kommt der neue Teil
            if course["location"] == "default":
                self._parsepdf()

        # Hier kommt jetzt die Ausgabe oder sowas von allen Änderungen, die in self._changes gespeichert sind
        self.__PropagateChanges()

    def _parsepdf(self):
        jar = requests.cookies.RequestsCookieJar()
        jar.set("ASP.NET_SessionId","5o3qqu33jod31m55qjyx13rs", domain="www.wsi.tum.de", path="/")
        r = requests.get(self._url, cookies=jar)
        soup = BeautifulSoup(r.content, "lxml")
        a = soup("a")
        session = DBSession()
        for b in a:
            if "href" in b.attrs and re.search(r".pdf$", b["href"]) is not None:
                name = b.text if b.text.strip() != "" else parse.unquote(b["href"].split('/')[-1])
                ret = processfile({"url":parse.urljoin(self._url, b["href"]), "title":name, "id":self._courseid, "session":self._session,
                                 "course":self._courseid})
                if ret is not None:
                    self._changes.append(ret)


    def __GetContent(self):
        r = self._session.get("https://www.moodle.tum.de/course/view.php?id=" + str(self._courseid) + "&lang=de")
        soup = BeautifulSoup(r.content, "lxml")
        if "<title>Kurs:" in r.text:
            cont = soup.select(".course-content")
            cont = re.sub(r'( (?:aria\-owns=\"|id=\")random[0-9a-f]*_group\")', "", str(cont))
            cont = re.sub(r"(<img.*?>)", "", cont)
            cont = re.sub(r"(<span class=\"accesshide \">.*?</span>)", "", cont)
            cont = re.sub(r"(<span class=\"accesshide \" >.*?</span>)", "", cont)
            cont = re.sub(r"( current\")", "\"", cont)
            self.__content = cont
        else:
            self.__content = ""
            self._semester = ""

    def __Split(self):
        content = self.__content
        # split in blocks first
        soup = BeautifulSoup(content, "lxml")
        blocks = soup.select(".mod-indent")
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
        # Prepare message
        if len(self._changes) > 0:
            counter = 0
            if self._location == "moodle" or self._location == "moodle_basic":
                message = {0: "Änderungen im Kurs <a href=\"https://www.moodle.tum.de/course/view.php?id=" + str(
                    self._courseid) + "\">" + self._coursename + "</a> erkannt:"}
            elif self._location == "default":
                message = {0: "Änderungen im Kurs <a href=\"" + str(
                    self._url) + "\">" + self._coursename + "</a> erkannt:"}
            for entry in self._changes:
                if entry["type"] == "url":
                    toadd = "\n<a href=\"" + entry["url"] + "\">" + entry["title"] + "</a>"
                    if len(entry["contentafterlink"]) > 0:
                        toadd += " - " + entry["contentafterlink"]
                elif entry["type"] == "text":
                    toadd = "\n" + entry["cont"]
                else:
                    toadd = ""
                if len(message[counter] + toadd) > 4096:
                    counter += 1
                    message[counter] = toadd
                else:
                    message[counter] = message[counter] + toadd
            # fetch users and send message to all of them
            session = DBSession()
            users = session.query(UUser).filter(UUser.notifications == True, UUser.semester == self._semester)
            for user in users:
                user.counter += 1
                session.commit()
                for key, msg in message.items():
                   send(user.id, msg)
            #This is for debugging onlyr
            #for key, msg in message.items():
            #    print(msg)
            session.close()


class Block:
    def __init__(self, block, course, session):
        self.__content = block
        self._course = course
        self._session = session
        self._changelist = {"type": "none"}
        self.__block = self.__AnalyseBlock()

    def __AnalyseBlock(self):
        soup = self.__content
        if "activityinstance" in soup.get('class', []):
            activityinstance = soup
            self.__type = "url"
            try:
                self._url = activityinstance.select("a")[0].get('href')
            except IndexError:
                return False
            self._title = activityinstance.select(".instancename")[0].find(text=True, recursive=False)
            try:
                self._cont = soup.parent.select(".contentafterlink")[0].text
            except (AttributeError, IndexError):
                self._cont = ""
                # Erstellen den Link-Objekts später, um wiederholte Downloads zu verhindern
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
        # speichern bzw abgleichen mit DB
        session = DBSession()
        blockentry = session.query(BBlock).filter(BBlock.url == self._url, BBlock.cont == self._cont,
                                                  BBlock.title == self._title).first()
        if not blockentry:
            # create block
            # print("Adding " + self._url + " " + self._title + " " + self._cont)
            new_block = BBlock(url=self._url, cont=self._cont, type=self.__type, course=self._course, title=self._title)
            session.add(new_block)
            session.commit()
            ## Hier die Änderung registrieren -> Bei Dateien 
            if self.__type == "url":
                link = Link(self)
                # speichern als Link zu message/Datei
                self._changelist = {"type": "url",
                                    "values": link._values}  # {"type":"url", "title":self._title, "url":link._url, "contentafterlink":self._cont}}
            else:
                # speichern des Blockinhalts
                self._changelist = {"type": "text", "values": [{"type": "text", "cont": self._cont}]}
        if not not blockentry and re.match(r"https:\/\/www\.moodle\.tum\.de\/mod\/(folder|lti)\/.*?id=([0-9]*)",
                                           self._url) is not None:
            # Scan von Ordnern
            link = Link(self)
            # speichern als Link zu message/Datei
            self._changelist = {"type":"url", "values": link._values }
        session.close()


class Link:
    def __init__(self, blockself):
        self._url = blockself._url
        self._title = blockself._title
        self._firsttitle = self._title
        self._course = blockself._course
        self._cont = blockself._cont
        self._session = blockself._session
        self._errorcounter = 0
        self._ftitle = blockself._firsttitle if hasattr(blockself, "_firsttitle") else ""
        normallink = re.match(r"https:\/\/www\.moodle\.tum\.de\/mod\/(.*?)\/.*?id=([0-9]*)", self._url)
        dllink = re.match(r"https://www\.moodle\.tum\.de/pluginfile\.php/([0-9]*)/mod_folder/content/0/(.*)", self._url)
        if normallink is not None:
            self._urltype = normallink.groups(1)[0]
            self._id = int(normallink.groups(1)[1])
            if self._urltype == "resource":
                # zusätzliche Verarbeitung als Datei
                r=processfile({"url": self._url, "title": self._title, "_ftitle": self._ftitle, "cont": self._cont,
                     "id": self._id, "session": self._session, "course": self._course})
                self._values=[r] if r is not None else []
            elif self._urltype == "folder":
                # Parse as folder
                self.__ParseFolder()
            elif self._urltype == "lti":
                # videoordner
                self.__PrepareVideoFolder()
            else:  # URL entspricht Muster ist aber nicht folder oder ressource
                self._urltype = "unknown"
                self._id = 0
                self._values = [{"type": "url", "title": self._title, "url": self._url, "contentafterlink": self._cont}]
        elif dllink is not None:
            self._id = dllink.groups(1)[0]
            l = processfile({"url":self._url, "title":self._title, "_ftitle":self._ftitle, "cont":self._cont,
                                        "id":self._id, "session":self._session, "course":self._course})
            self._values = [l] if l is not None else []
        else:  # Link entspricht nicht dem Schema
            self._values = []

    def __ParseFolder(self):
        # Download filelist
        self._values = []
        try:
            r = self._session.get("https://www.moodle.tum.de/mod/folder/view.php?id=" + str(self._id))
        except requests.exceptions.ChunkedEncodingError:
            self._errorcounter += 1
            if self._errorcounter < 10:
                self.__ParseFolder(self)
            else:
                raise NameError('Parsing of folder failed more than 10 times, url:https://www.moodle.tum.de/mod/folder/view.php?id='+str(self._id))
        soup = BeautifulSoup(r.text, "lxml")
        files = soup.select(".fp-filename-icon")
        for file in files:
            try:
                self._url = re.sub(r"\?forcedownload=1$", "", file.select("a")[0].get('href'))
                self._title = self._firsttitle + " - " + file.select(".fp-filename")[0].text
                # initialize new Link element
                link = Link(self)
                if link._values != []:
                    self._values += link._values
            except IndexError:
                pass

    def __PrepareVideoFolder(self):
        # check if already in db would be too complicated
        self._values = []
        # save that to db now
        session = DBSession()
        course = session.query(CCourse).filter(CCourse.id == self._course).first()
        course.videoidentifier = re.sub(r"view", "launch", self._url)
        session.commit()
        session.close()


def processfile(file):
    session = DBSession()
    fileentry = session.query(FFile).filter(FFile.id == file["id"], FFile.title == file["title"]).first()
    if not fileentry:
        # file is not yet saved
        # check first if the file is downloadable
        test=file["session"].head(file["url"])
        if test.status_code != 200 and test.status_code!=303:
            return None
        # now download
        filename = download(file["url"], file["session"])
        sleep(3)
        # check file size
        if os.path.getsize(filename) < 50 * 1024 * 1024:
            # upload to telegram and delete
            coursename = session.query(CCourse).filter(CCourse.id == file["course"]).one()
            resp = bot.sendDocument(chat_id=config["DEFAULT"]["FilesChannelId"], document=open(filename, 'rb'),
                                    caption=coursename.name + " - " + file["title"], timeout=60)
            path = config['DEFAULT']['CopyDir'] + re.sub('[^\w\-_\. ()\[\]]', '_', coursename.name)
            if not os.path.exists(path):
                os.mkdir(path)
            if "_ftitle" in file and file["_ftitle"] != "":
                fullpath = path + "/" + re.sub(
                    '[^\w\-_\. ()\[\]]', '_', file["_ftitle"])
                if not os.path.exists(fullpath):
                    os.mkdir(fullpath)
                move(filename, fullpath + "/" + filename)
            else:
                move(filename, path + "/" + filename)
            # in DB speichern
            file["url"] = "https://t.me/" + config["DEFAULT"]["FilesChannelName"] + "/" + str(resp.message_id)
            new_file = FFile(id=file["id"], course=file["course"], title=file["title"], message_id=resp.message_id,
                             date=datetime.now(), url=file["url"])
            session.add(new_file)
            session.commit()
            file["title"] += " (Telegram-Cloud)"
        else:
            new_file = FFile(id=file["id"], course=file["course"], title=file["title"], message_id="0",
                             date=datetime.now(), url=file["url"])
            session.add(new_file)
            session.commit()
            file["title"] += " (Moodle)"
            os.remove(filename)
        # Speichern der Änderungen für Rückgabe
        values = {"type": "url", "title": file["title"], "url": file["url"],
                   "contentafterlink": file["cont"] if "cont" in file else ""}
    else:
        values = None
    session.close()
    return values

def ParseVideoFolder(dbsess, s, course):
    if course.videoidentifier is None or course.videoidentifier == "":
        return False
    if "https://www.moodle.tum.de" in course.videoidentifier:
        resp = s.get(course.videoidentifier)
        soup = BeautifulSoup(resp.text, "lxml")
        oauth = soup.select("input")
        values = {}
        for inp in oauth:
            values[inp.get('name')] = inp.get('value')
        r = s.post(soup.select("form")[0].get("action"), data=values)
    else:
        r = s.get("https://streams.tum.de/Mediasite/Catalog/catalogs/" + course.videoidentifier)
    courseid = re.search(r"CatalogId: '([a-f|0-9|-]*)',", r.text).groups(1)[0]
    reqbody = {"IsViewPage": True, "CatalogId": courseid, "CurrentFolderId": courseid, "ItemsPerPage": 200,
               "PageIndex": 0, "CatalogSearchType": "SearchInFolder"}
    medialist = s.post("https://streams.tum.de/Mediasite/Catalog/Data/GetPresentationsForFolder", data=reqbody).json()
    for media in medialist["PresentationDetailsList"]:
        medium = dbsess.query(MMedia).filter(MMedia.playerurl == media["PlayerUrl"]).first()
        if not medium:
            print("  - " + media["Name"])
            # find file path(s)
            header = {"Content-Type": "application/json; charset=utf-8"}
            data = {"getPlayerOptionsRequest": {"ResourceId": media["Id"], "QueryString": "?catalog=" + courseid}}
            realvid = s.post("https://streams.tum.de/Mediasite/PlayerService/PlayerService.svc/json/GetPlayerOptions",
                             data=json.dumps(data), headers=header).json()
            videos = []
            if not realvid["d"]["Presentation"] is None:
                for stream in realvid["d"]["Presentation"]["Streams"]:
                    for vid in stream['VideoUrls']:
                        if vid["MediaType"] == "MP4":
                            videos.append(vid["Location"][:-68])
                videos.append("")
                mp4url1 = videos[0]
                mp4url2 = videos[1]
            else:
                mp4url1 = ""
                mp4url2 = ""
            # create entry
            datetim = datetime.strptime(media["FullStartDate"], "%m/%d/%Y %H:%M:%S")
            new_medium = MMedia(name=media["Name"], playerurl=media["PlayerUrl"], date=datetim, course=course.id,
                                mp4url1=mp4url1, mp4url2=mp4url2)
            dbsess.add(new_medium)
            dbsess.commit()


def ProcessVideos(user, password, s):
    sess = DBSession()
    courses = sess.query(CCourse).filter(CCourse.semester == current_semester).all()
    s.get("https://streams.tum.de/Mediasite/Login/")
    login = s.post("https://streams.tum.de/Mediasite/Login/",
                   data={"UserName": user, "Password": password, "RememberMe": "false"}, allow_redirects=False)
    if login.status_code == 302:
        for course in courses:
            print(" - " + course.name)
            ParseVideoFolder(sess, s, course)
    else:
        raise Exception("Login failed on Mediasite")
    sess.close()


def processothercontent():
    sess = DBSession()
    courses = sess.query(CCourse).filter(CCourse.location != "moodle", CCourse.semester == current_semester).all()
    for course in courses:
        Course(course.__dict__)

print("Processing Moodle:")
moodle = Moodleuser(config['DEFAULT']['Username'], config['DEFAULT']['Password'])
# process all content outside of Moodle
print("Processing other content: ")
processothercontent()

# finally process all videos
print("Processing Videos:")
ProcessVideos(config['DEFAULT']['Username'], config['DEFAULT']['Password'], moodle._session)
