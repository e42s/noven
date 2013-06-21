# -*- coding:utf-8 -*-

import re
import logging
import functools

import requests


LOGIN_URL = "http://jwxt.bjfu.edu.cn/jwxt/logon.asp"
NAME_URL = "http://jwxt.bjfu.edu.cn/jwxt/menu.asp"
DATA_URL = "http://jwxt.bjfu.edu.cn/jwxt/Student/StudentGraduateInfo.asp"
LOGOUT_URL = "http://jwxt.bjfu.edu.cn/jwxt/logoff.asp"


def session_required(method):
    '''Decorate methods with this to require that the session exists.'''
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self._session:
            self._login()
        return method(self, *args, **kwargs)
    return wrapper


class Course(dict):
    '''A wrapper of the basic properties of a course.'''
    @property
    def subject(self):
        return self[u"subject"]

    @property
    def score(self):
        return self[u"score"]

    @property
    def point(self):
        return self[u"point"]

    @property
    def term(self):
        return self[u"term"]


class User(object):
    u'''Providing userful methods and storage for a user.'''
    global LOGIN_URL
    global LOGOUT_URL
    global NAME_URL
    global DATA_URL

    def __init__(self, ucode, upass, mcode=None, mpass=None, wid=None):
        self.usercode = ucode
        self.password = upass
        self.mobileno = mcode
        self.mobilepass = mpass

        self.wx_id = wid
        self.wx_push = {}

        self.name = None
        self.courses = {}
        self.GPA = None
        self.current_GPA = None
        self.rank = None
        self.verified = False

        self._session = None

        self._login()
        self.get_name()
        self._logout()

    @session_required
    def _open(self, url, data=None):
        '''Loop until a response got.'''
        o = self._session.post if data else self._session.get

        # It will return a response eventually unless the url is unreachable
        # and the thread will be dead.
        while True:
            try:
                r = o(url, data=data)
            except:
                continue
            return r

    def _login(self):
        self._session = requests.session()

        payload = {
            "type": "Logon", "B1": u" 提　交 ".encode("gb2312"),
            "UserCode"      : self.usercode,
            "UserPassword"  : self.password
        }
        self._open(LOGIN_URL, data=payload)

    def _logout(self):
        # Session should be cleared in case of bad things.
        self._session = None
        pass

    def get_name(self):
        r = self._open(NAME_URL)

        pattern = u'''.* MenuItem\( "注销 (.+?)", .*'''
        m = re.search(pattern, r.content.decode("gb2312"))
        if m:
            self.name = m.groups()[0]
            logging.info('Name got - %s' % self.name)
            return self.name

    def get_data(self, all=None):
        '''Save & return newly-released courses.'''
        r = self._open(DATA_URL)

        # Get current term GPA & all terms GPA.
        pattern = u"<p>在本查询时间段，你的学分积为(.+?)、必修课取"
        m = re.search(pattern, r.content.decode("gb2312"))
        if m:
            self.current_GPA = m.groups()[0]
        pattern = u"全学程你的学分积为(.+?)</p>"
        m = re.search(pattern, r.content.decode("gb2312"))
        if m:
            self.GPA = m.groups()[0]

        r = all if all else r
        # Import BeautifulSoup to deal with the data we got.
        from BeautifulSoup import BeautifulSoup
        soup = BeautifulSoup(r.content)

        l = soup.findAll('tr', height='25')
        # Save the rank calculated by JWXT.
        self.rank = l[-1].contents[1].contents[2].string[5:] \
            if u"全学程" in l[-1].contents[1].contents[2].string \
            else l[-1].contents[1].contents[3].string[5:]

        del l[0]    # 删除冗余数据
        del l[-4:]  # 删除冗余数据

        new_courses = {}
        for i in l:
            # Normal courses
            if i.contents[1].string != u"&nbsp;" and i.contents[3].get("colspan") != u"5":
                course = Course(
                    subject = i.contents[1].string.replace(u' ', u''),
                    score   = unicode(i.contents[3].contents[0].string),
                    point   = i.contents[11].string,
                    term    = i.contents[13].string + i.contents[15].string
                )
            # Practical courses
            # Generally do not display scores unless been ranked.
            elif i.contents[3].get('colspan') == u'5':
                course = Course(
                    subject = i.contents[1].string.replace(u' ', u''),
                    score   = u'待评价',
                    point   = u'-',
                    term    = i.contents[5].string + i.contents[7].string
                )
            if course and course.term + course.subject not in self.courses.keys():
                logging.info(u"A new course - %s", course.term+course.subject)
                new_courses[course.term+course.subject] = course

                # In case of logging too many times.
                course = None

        # Save newly-released courses.
        self.courses.update(new_courses)
        return new_courses

    def init_data(self):
        self._login()

        # We should fetch all terms data and pass it over at first run.
        payload = {
            "order":"xn", "by":"DESC", "year":"0", "term":"0",
            "keyword":"", "Submit1":u" 查 询 ".encode("gb2312")
        }
        r = self._open(DATA_URL, data=payload)
        self.get_data(all=r)

        self._logout()

    def update(self):
        '''Update & return newly-released courses for external call.'''
        self._login()

        new_courses = self.get_data()
        logging.info(u"%d more courses released - %s" % (len(new_courses), self.name))

        self._logout()
        return new_courses


if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s - %(levelname)-8s %(message)s", level=logging.DEBUG)
    logging.info("Initializing")
    u.get_data()
    print u.GPA
    print u.current_GPA
    # for k, v in u.courses.items():
        # print k, v
    # print "user init done"
    # print u.get_data()
    # u.get_data = tmp
    # print u.update()
