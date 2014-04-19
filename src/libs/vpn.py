# -*- coding:utf-8 -*-

"""F*CK!

BJFU JWXT restricts outside-campus access starting April 14th, 2014.  VPN is
required to access to JWXT outside campus.  This piece of code is used to
handle VPN connection to make less changes to alpha and the main logic.
"""

import re
import time

import requests


LOGIN_URL = "https://vpn.bjfu.edu.cn/dana-na/auth/url_default/login.cgi"
LOGOUT_URL = "https://vpn.bjfu.edu.cn/dana-na/auth/logout.cgi"


class Session(requests.Session):
    """A wrapper for requests.Session adding VPN support.

    Connect to VPN automatically when created and provide useful interfaces.
    """
    def __init__(self, username="***REMOVED***", password="***REMOVED***"):
        super(Session, self).__init__()
        self.username = username
        self.password = password

        p = {
            "tz_offset": "480",
            "username": self.username,
            "realm": "Users",
            "password": self.password,
            "btnSubmit.x": "0",
            "btnSubmit.y": "0",
            "btnSubmit": "Sign In"
        }
        r = self.post(LOGIN_URL, p, verify=False)

        if "user-confirm" in r.url:
            pattern = 'taStr" type="hidden" name="FormDataStr" value="(.*?)">'
            p = {
                "btnContinue": "继续会话",
                "FormDataStr": re.search(pattern, r.content).group(1)
            }
            self.post(LOGIN_URL, p, verify=False)

    def logout(self):
        self.get(LOGOUT_URL, verify=False)

    @property
    def expired(self):
        return int(time.time()) - int(self.cookies.get("DSLastAccess", 0)) > 480
