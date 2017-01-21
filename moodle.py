#!/usr/bin/env python
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
from moodle_db_create import Base, Group, User
import re, requests, telegram, urllib, configparser
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from time import gmtime, strftime

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
    groups = session.query(Group).all()
    for group in groups:
        chatids.append(group.id)
    users = session.query(User).all()
    for user in users:
        chatids.append(user.id)
    session.close()
    return chatids

def moodle_login():
    s = requests.Session()
    login = s.get("https://www.moodle.tum.de/Shibboleth.sso/Login?providerId=https%3A%2F%2Ftumidp.lrz.de%2Fidp%2Fshibboleth&target=https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php", allow_redirects=True)
    auth = s.post("https://tumidp.lrz.de/idp/Authn/UserPassword", allow_redirects=True, data={"j_password": config['DEFAULT']['Password'], "j_username": config['DEFAULT']['Username']}, cookies=login.cookies)
    resp = re.search(r"SAMLResponse\" value=\"(.*)\"/>", auth.text)
    s.cookies = requests.utils.add_dict_to_cookiejar(s.cookies, {"_shibstate_123":"https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php"})
    final = s.post("https://www.moodle.tum.de/Shibboleth.sso/SAML2/POST", allow_redirects=True, data={"SAMLResponse":resp.groups()[0], "RelayState":"cookie:123"})
    return requests.utils.dict_from_cookiejar(s.cookies)["MoodleSession"]
def moodle_list(cookies):
    url = "https://www.moodle.tum.de/my/"
    response = requests.get(url, cookies=cookies).text
    return re.findall(r"href=\"https://www\.moodle\.tum\.de/course/view\.php\?id=([0-9]*)\"", response, re.MULTILINE)
def moodle_get(id, cookies):
    r = requests.get("https://www.moodle.tum.de/course/view.php?id=" + str(id), cookies=cookies)
    soup = BeautifulSoup(r.content, "lxml")
    cont = soup.select(".course-content")
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
#cookies={"MoodleSession":"9e0b66b738f0210ed96ec6d56e0d958a"}
pages = moodle_list(cookies)
message = u""
chatids = getchatids()
counter = 0
for course in pages:
    if not course in ignore_courses:
        cont = moodle_get(course, cookies)
        new = moodle_compare_extract(course, cont[0])
        if new["change"]:
            moodle_save(course, cont[0])
            message += "Neue Inhalte im " + cont[1] + ": \n"
            counter += 1
            if len(new["links"]) > 0:
                for link in new["links"]:
                    message += "<a href=\"" + link[0] + "\">" + link[1] + "</a>\n"
                    counter += 1
                    if(counter > 38):
                        counter = 0
                        for chatid in chatids:
                            bot.sendMessage(chat_id=chatid, text=message, parse_mode=telegram.ParseMode.HTML)
						
                        message = ""
            else:
                message = u' '.join([message, u'Änderungen erkannt.\n'])
				
#print(message)
#while(len(message)>4096):
#	bot.sendMessage(chat_id=chatid, text=message[:4096], parse_mode=telegram.ParseMode.HTML)
#	message=message[4096:]
if len(message) > 0:
	for chatid in chatids:
		bot.sendMessage(chat_id=chatid, text=message, parse_mode=telegram.ParseMode.HTML)