from bs4 import BeautifulSoup
import requests, re, urllib

def moodle_list(cookies):
	url="https://www.moodle.tum.de/my/"
	response=requests.get(url, cookies=cookies).text
	return re.findall(r"href=\"https://www\.moodle\.tum\.de/course/view\.php\?id=([0-9]*)\"", response, re.MULTILINE)
	
def moodle_get(id, cookies):
	r=requests.get("https://www.moodle.tum.de/course/view.php?id="+str(id), cookies=cookies)
	soup=BeautifulSoup(r.content, "lxml")
	cont=soup.select(".course-content")
	cont=re.sub(r'( (?:aria\-owns=\"|id=\")random[0-9a-f]*_group\")', "", str(cont))
	cont=re.sub(r"(<img.*?>)","", cont)
	cont=re.sub(r"(<span class=\"accesshide \">Diese Woche</span>)", "", cont)
	cont=re.sub(r"(current\")", "\"", cont)
	title=soup.title.string
	return [cont, title]
def moodle_save(id, cont):
	an=open(str(id)+".txt", "w", newline='\n')
	an.write(str(urllib.parse.quote_plus(cont)))
	an.close()

cookies={"MoodleSession":"d200fa8a8a77e525aa7151e9bab1205a"}
liste=moodle_list(cookies)
#cont=moodle_get(30683, cookies)[0]
#moodle_save(30683, cont)



for fil in liste:
	page=moodle_get(fil, cookies)
	moodle_save(fil, page[0])