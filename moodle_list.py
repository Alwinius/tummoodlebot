#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests, re

cookies={"MoodleSession":"357a674cf161de047e5a6bbd90d1cb4b"}
url="https://www.moodle.tum.de/my/"

response=requests.get(url, cookies=cookies).text
							
result=re.findall(r"title=\"(.*?)\" href=\"https://www\.moodle\.tum\.de/course/view\.php\?id=([0-9]*)\"", response, re.MULTILINE)

print result