import requests, re

s=requests.Session()
login=s.get("https://www.moodle.tum.de/Shibboleth.sso/Login?providerId=https%3A%2F%2Ftumidp.lrz.de%2Fidp%2Fshibboleth&target=https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php", allow_redirects=True)
auth=s.post("https://tumidp.lrz.de/idp/Authn/UserPassword", allow_redirects=True, data={"j_password": "", "j_username": ""}, cookies=	login.cookies)
resp=re.search(r"SAMLResponse\" value=\"([a-zA-Z0-9\+]*)=", auth.text)
s.cookies=requests.utils.add_dict_to_cookiejar(s.cookies, {"_shibstate_123":"https%3A%2F%2Fwww.moodle.tum.de%2Fauth%2Fshibboleth%2Findex.php"})
final=s.post("https://www.moodle.tum.de/Shibboleth.sso/SAML2/POST", allow_redirects=True, data={"SAMLResponse":resp.groups()[0]+"=", "RelayState":"cookie:123"})
print(requests.utils.dict_from_cookiejar(s.cookies)["MoodleSession"])