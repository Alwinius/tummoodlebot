import urllib.parse
id="31297-new"
old=open(str(id)+".txt", "r")
old2=old.read()
old.close()
new=open(str(id)+".txt", "w")
new.write(urllib.parse.quote_plus(old2))
new.close()