# created by Alwin Ebermann (alwin@alwin.net.au)

import requests, telegram, configparser, os, re
from moodle_db_create import Base, User, FFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

config = configparser.ConfigParser()
config.read('config/config.ini')

def save_file_to_db(cookies, url, name, course, session, bot):
    #compare if file is already in db 
    entry=session.query(FFile).filter(FFile.course==course, FFile.name==name).first()
    if not entry:
        #download from moodle
        filename=download_file(url, cookies)
        #send somewhere, save message id
        resp=bot.sendDocument(chat_id=-23546166, document=open(filename, 'rb'), caption=course+" - "+name)
        os.remove(filename)
        #write everything into the db
        new_file = FFile(course=course[6:], name=name, message_id=resp.document.file_id, date=datetime.now())
        session.add(new_file)
        session.commit()
        return [True, resp.document.file_id]
    else:
        return [False, entry.message_id]

def download_file(url, cookies):
    r = requests.get(url, stream=True, cookies=cookies)
    with open(r.url.split('/')[-1], 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024): 
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
    return r.url.split('/')[-1]
    
def moodle_login():
	s=requests.Session()
	login=s.get("https://www.moodle.tum.de/Shibboleth.sso/Login?providerId=https%3A%2F%2Ftumidp.lrz.de%2Fidp%2Fshibboleth&target=https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php", allow_redirects=True)
	headers = {'Content-Type': 'application/x-www-form-urlencoded', "Origin": "https://tumidp.lrz.de", "Connection": "keep-alive", "Content-Length":"74"}
	auth=requests.post("https://tumidp.lrz.de/idp/profile/SAML2/Redirect/SSO?execution=e1s1", headers=headers, data={"j_username": config['DEFAULT']['Username'], "j_password": config['DEFAULT']['Password'],  "_eventId_proceed": "", "donotcache":"1"}, allow_redirects=False, cookies={"JSESSIONID":s.cookies["JSESSIONID"]})
	resp=re.search(r"SAMLResponse\" value=\"(.*)\"/>", auth.text)
	s.cookies=requests.utils.add_dict_to_cookiejar(s.cookies, {"_shibstate_123":"https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php"})
	final=s.post("https://www.moodle.tum.de/Shibboleth.sso/SAML2/POST", allow_redirects=True, data={"SAMLResponse":resp.groups()[0], "RelayState":"cookie:123"})
	return requests.utils.dict_from_cookiejar(s.cookies)["MoodleSession"]

def sendtoall(users, message, bot):
    for chatid in users:
        bot.sendMessage(chat_id=chatid, text=message, parse_mode=telegram.ParseMode.HTML)
def sendfiletoall(users, file_id, caption, bot):
    for chatid in users:
        bot.sendDocument(chat_id=chatid, caption=caption, document=file_id, disable_notification=True)