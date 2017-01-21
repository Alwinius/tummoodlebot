import requests, re
from bs4 import BeautifulSoup

id=30169
cookies={"MoodleSession":"357a674cf161de047e5a6bbd90d1cb4b"}

r=requests.get("https://www.moodle.tum.de/course/view.php?id="+str(id), cookies=cookies)
soup=BeautifulSoup(r.content, "lxml")
cont=soup.select(".course-content")
cont=re.sub(r'( (?:aria\-owns=\"|id=\")random[0-9a-f]*_group\")', "", str(cont))
cont=re.sub(r"(<img.*?>)","", cont)
cont=re.sub(r"(<span class=\"accesshide \">Diese Woche</span>)", "", cont)
cont=re.sub(r"(current\")", "\"", cont)
title=soup.title.string[6:]
