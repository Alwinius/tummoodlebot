#!/usr/bin/env python
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import requests, re
import urllib

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

id=31297

cont=moodle_get(id, {"MoodleSession":"34c5436d53ceabe762242ee35dee5d5b"})[0]

ao=open(str(id)+".txt", "r")
old=ao.read()
old=urllib.parse.unquote_plus(old)
if old==cont:
	print("No changes since last check!")
else:
	for i in range(len(old)):
	#das ist der Anfang
		if not cont.startswith(old[:i]):
			#erstmal das ende finden
			for e in range(len(cont)):
				if not cont.endswith(old[-e-1:]):
					diff=cont[i-1:-e]
					print(diff)
					print(str(i)+" "+str(e))
					#print(urllib.parse.quote_plus(cont[11040:11060]))
					#print(urllib.parse.quote_plus(old[11040:11060]))
					break
			entries=list()
			#Änderung in einem Link prüfen
			match=re.search(r"(^.*?</a>)", diff)
			if match is not None:
				match=match.groups()[0]
				counter=0
				while(re.search(r"(.*<a.*<\/a>)", match) is None):
					match=cont[i-counter]+match
					counter+=1
				diff=cont[i-counter:-e]
			for part in diff.split("<a"):	
				if "href" in part:
					print("test")
					url=re.search(r'(https:\/\/www\.moodle\.tum\.de\/mod.+?)\"', part)
					name=re.search(r'\"instancename\">(.+?)<span', part)
					if url is not None and name is not None:
						url=url.groups(1)
						name=name.groups(1)
						list=(url[0],name[0])
						print(list)
					elif url is not None and name is None:
						name=re.search(r'\"instancename\">(.+)', part)
						if name is not None:
							url=url.groups(1)
							name=name.groups(1)
							list=(url[0],name[0])
							print(list)
			break
	#print("New changes!")