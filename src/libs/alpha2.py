# -*- coding:utf-8 -*-

import re
import logging
import functools

import requests


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
    '''Providing userful methods and storage for a user.'''
    def __init__(self, ucode, upass, mcode=None, mpass=None):
        self.usercode = ucode
        self.password = upass
        self.mobileno = mcode
        self.mobilepass = mpass

        self.name = None
        self.courses = {}
        self.GPA = None
        self.current_GPA = None
        self.rank = None
        self.verified = False

        self._session = None

        self.login()
        self.get_name()
        if self.name:
            self.get_data()
            self.logout()

    @session_required
    def _open(self, url, data=None):
        '''Loop until successfully response.'''
        o = self._session.get
        if data:
            o = self._session.post

        while True:
            try:
                r = o(url, data=data)
            except:
                continue
            return r

    def login(self):
        self._session = requests.session()

        payload = {
            "type": "Logon", "B1": u" 提　交 ".encode("gb2312"),
            "UserCode"      : self.usercode,
            "UserPassword"  : self.password
        }
        self._open("http://jwxt.bjfu.edu.cn/jwxt/logon.asp", data=payload)

    def get_name(self):
        r = self._open("http://jwxt.bjfu.edu.cn/jwxt/menu.asp")

        m = re.search(u'''.* MenuItem\( "注销 (.+?)", .*''', r.content.decode("gb2312"))

        if m:
            self.name = m.groups()[0]
            logging.info('Name got - %s' % self.name)
            return self.name

    def get_current_GPA(self):
        '''Save & return current term GPA.'''
        r = self._open("http://jwxt.bjfu.edu.cn/jwxt/Student/StudentGraduateInfo.asp")

        m = re.search(u"<p>在本查询时间段，(.+?)、必修课取", r.content.decode("gb2312"))
        if m:
            self.current_GPA = u"本学期" + m.groups()[0]
            return self.current_GPA

    def get_data(self):
        '''Return newly-released courses.'''
        payload = {
            "order":"xn", "by":"DESC", "year":"0", "term":"0",
            "keyword":"", "Submit1":u" 查 询 ".encode("gb2312")
        }
        r = self._open("http://jwxt.bjfu.edu.cn/jwxt/Student/StudentGraduateInfo.asp", data=payload)

        data = r.content
        # import BeautifulSoup to parse the data we got
        from BeautifulSoup import BeautifulSoup
        soup = BeautifulSoup(data)

        l = soup.findAll('tr', height='25')
        # save the GPA & rank calculated by JWXT
        self.GPA = u"全学程" + l[-3].contents[1].contents[1].string.split(u"，")[1].split(u"、")[0]
        self.get_current_GPA()
        self.rank = l[-1].contents[1].contents[2].string if u"全学程" in l[-1].contents[1].contents[2].string else l[-1].contents[1].contents[3].string

        del l[0]    # 删除冗余数据
        del l[-4:]  # 删除冗余数据

        new_courses = {}
        for i in l:
            # normal courses
            if i.contents[1].string != u"&nbsp;" and i.contents[3].get("colspan") != u"5":
                course = Course(
                    subject = i.contents[1].string.replace(u' ', u''),
                    score   = unicode(i.contents[3].contents[0].string),
                    point   = i.contents[11].string,
                    term    = i.contents[13].string + i.contents[15].string
                )
            # practical courses
            # generally do not display score unless ranked
            elif i.contents[3].get('colspan') == u'5':
                course = Course(
                    subject = i.contents[1].string.replace(u' ', u''),
                    score   = u'待评价',
                    point   = u'-',
                    term    = i.contents[5].string + i.contents[7].string
                )
            if course.term + course.subject not in self.courses.keys():
                    logging.info(u"A new course - %s", course.term+course.subject)
                    new_courses[course.term+course.subject] = course

        # self.courses.update(new_courses)
        return new_courses

    def update(self):
        '''Return newly-released courses'''
        self.login()
        new_courses = self.get_data()
        self.courses.update(new_courses)
        logging.info(u"%d more courses released - %s" % (len(new_courses), self.name))
        self.logout()
        return new_courses

    def logout(self):
        self._open("http://jwxt.bjfu.edu.cn/jwxt/logoff.asp")
        self._session = None


def session_required(method):
    '''Decorate methods with this to require that the session exists.'''
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self._session:
            self.login()
        return method(self, *args, **kwargs)
    return wrapper

if __name__ == "__main__":
    logging.basicConfig(format="%(asctime)s - %(levelname)-8s %(message)s", level=logging.DEBUG)
    logging.info("Initializing")
    # for k, v in u.courses.items():
        # print k, v
    # print "user init done"
    # print u.get_data()
    # u.get_data = tmp
    # print u.update()