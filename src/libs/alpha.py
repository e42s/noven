# -*- coding:utf-8 -*-

import re
import logging
import functools

import requests

ALL_TERMS = True
LOGIN_URL = "http://jwxt.bjfu.edu.cn/jwxt/logon.asp"
NAME_URL = "http://jwxt.bjfu.edu.cn/jwxt/menu.asp"
DATA_URL = "http://jwxt.bjfu.edu.cn/jwxt/Student/StudentGraduateInfo.asp"
LOGOUT_URL = "http://jwxt.bjfu.edu.cn/jwxt/logoff.asp"


def session_required(method):
    """Decorate methods with this to require that the session exists."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self._session:
            self._login()
        return method(self, *args, **kwargs)
    return wrapper


class AuthError(Exception):
    """Wrong usercode or password."""


class Course(dict):
    """Wrapper for a course.

    :subject
    :score
    :point
    :term
    """
    PROPERTIES = ("subject", "score", "point", "term")

    def __getattr__(self, property):
        if property in self.PROPERTIES:
            return self[property]
        else:
            return object.__getattribute__(self, property)

    def __eq__(self, other):
        for k, v in self.items():
            if v != other[k]:
                return False
        return True


class User(object):
    """Providing userful methods and storage for a user."""
    global LOGIN_URL
    global LOGOUT_URL
    global NAME_URL
    global DATA_URL

    TPL_NEW_COURSES = u"""Hello，{{ u.name }}！有{{ len(new_courses) }}门课出分了：{{ u"、".join([u"%s(%s)" % (v.subject, v.score) for v in new_courses.values()]) }}。当前学期您的学分积为{{ u.current_GPA }}，全学程您的学分积为{{ u.GPA }}，{{ u.rank }}。"""
    TPL_WELCOME = u"""Hello，{{ u.name }}！全学程您的学分积为{{ u.GPA }}，{{ u.rank }}，共修过{{ len(u.courses) }}门课。加油！"""
    TPL_NO_UPDATE = u"""Hello，{{ u.name }}！最近没有新课程出分。当前学期您的学分积为{{ u.current_GPA }}，全学程您的学分积为{{ u.GPA }}，{{ u.rank }}。"""

    def __init__(self, ucode, upass, mcode=None, mpass=None, wid=None):
        self.usercode = ucode
        self.password = upass
        self.mobileno = mcode
        self.mobilepass = mpass

        self.wx_id = wid
        self.wx_push = {}

        self.name = None
        self.courses = {}
        self.GPA = u"0"
        self.current_GPA = u"0"
        self.rank = u"暂无排名"
        self.verified = False

        self._session = None

        self._login()
        self._get_name()
        self._logout()

    @session_required
    def _open(self, url, data=None):
        """Loop until a response got.

        It will return a response eventually unless the URL is unreachable and
        the thread will be dead.
        """
        o = self._session.post if data else self._session.get

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
        r = self._open(LOGIN_URL, data=payload)
        t = r.content.decode("gb2312")

        # `requests.Session` can NOT be serialized properly in KVDB. We must
        # clean it up before save.
        if u"密码不正确,请重新输入！" in t:
            self._logout()
            raise AuthError("Wrong password.")
        if u"用户不存在！" in t:
            self._logout()
            raise AuthError("Wrong usercode.")

    def _logout(self):
        # Session should be cleared in case of bad things.
        self._session = None
        pass

    def _get_name(self):
        """Save and return the user's true name."""
        r = self._open(NAME_URL)

        pattern = u""".* MenuItem\( "注销 (.+?)", .*"""
        m = re.search(pattern, r.content.decode("gbk"))
        if m:
            self.name = m.groups()[0]
            logging.debug("%s - [alpha] Name found: %s", self.usercode, self.name)
            return self.name

    def _get_GPA(self, r, all=False):
        """Save and return all-term GPA or current-term GPA respectly.

        If `all`, the result will be saved to `GPA`. Otherwise, the result
        will be saved to `current_GPA`.
        """
        pattern = u"<p>在本查询时间段，你的学分积为(.+?)、必修课取"
        m = re.search(pattern, r.content.decode("gb2312"))
        if m:
            if all:
                self.GPA = m.group(1)
                logging.debug("%s - [alpha] GPA updated: %s", self.usercode, self.GPA)
                return self.GPA
            else:
                self.current_GPA = m.group(1)
                logging.debug("%s - [alpha] Current GPA updated: %s", self.usercode, self.current_GPA)
                return self.current_GPA

    def _get_courses(self, r):
        """Save and return newly-released courses, save rank as well.
        """
        # Import BeautifulSoup to deal with the data we got.
        from BeautifulSoup import BeautifulSoup
        soup = BeautifulSoup(r.content)

        l = soup.findAll('tr', height='25')
        if not l:
            # IndexError sometimes occurs when saving rank.  It appears that
            # malformed response we received is to blame, i.e. `r.content` is
            # not completed.
            logging.error("%s - [alpha] Something wrong with the returning data.", self.usercode)
            return {}

        # Save the rank calculated by JWXT.
        # If failed, turn to default.  Most probably, the user is in his first term.
        try:
            self.rank = l[-1].contents[1].contents[2].string[5:] \
                if u"全学程" in l[-1].contents[1].contents[2].string \
                else l[-1].contents[1].contents[3].string[5:]
        except IndexError as e:
            logging.error("%s - Can't get rank for the user.", self.usercode)

        logging.debug("%s - [alpha] Rank saved: %s", self.usercode, self.rank)

        # Delete unnecessary data.
        del l[0]
        del l[-4:]

        new_courses = {}
        courses = self.courses.values()
        for i in l:
            if len(i.contents) < 4:
                logging.debug("%s - [alpha] Too few `i.contents`.", self.usercode)
                continue
            # Normal cases.
            if i.contents[1].string != u"&nbsp;" and i.contents[3].get("colspan") != u"5":
                # When [期末] is empty, we turn to [备注].
                score = unicode(i.contents[3].contents[0].string) \
                    if i.contents[3].contents[0].string \
                    else i.contents[9].contents[0].string

                course = Course(
                    subject = i.contents[1].string.replace(u' ', u''),
                    score   = score,
                    point   = i.contents[11].string,
                    term    = i.contents[13].string + i.contents[15].string
                )

                key = course.term + course.subject
                if course not in courses:
                    new_courses[key] = course
                    logging.debug("%s - [alpha] A new course: %s", self.usercode, key)
            # Special cases.
            # If the course is released before Rating System being closed,
            # score will not be displayed.
            elif i.contents[3].get('colspan') == u'5':
                course = Course(
                    subject = i.contents[1].string.replace(u' ', u''),
                    score   = u'待评价',
                    point   = u'-',
                    term    = i.contents[5].string + i.contents[7].string
                )

                key = course.term + course.subject
                if not self.courses.has_key(key):
                    new_courses[key] = course
                    logging.debug("%s - [alpha] A new course: %s", self.usercode, key)
            else:
                # If no course was created, we should simply continue in case
                # of encountering NameError later.
                continue

        # Save newly-released courses.
        self.courses.update(new_courses)
        return new_courses

    def _fetch_now(self):
        return self._open(DATA_URL)

    def _fetch_all(self):
        payload = {
            "order":"xn", "by":"DESC", "year":"0", "term":"0",
            "keyword":"", "Submit1":u" 查 询 ".encode("gb2312")
            }
        return self._open(DATA_URL, data=payload)

    def init(self):
        """Initialize the User's data.
        """
        self._login()

        # Initializing data.
        # Get `courses` and `GPA`
        r = self._fetch_all()

        # If user not regisered yet, then we can't fetch any data.
        # Remember to ogout before raise.
        if u"你还没有学期注册，无法使用本模块！" in r.content.decode("gb2312"):
            self._logout()
            raise Exception("User not registered.")

        self._get_courses(r)
        self._get_GPA(r, ALL_TERMS)

        # Get `current_GPA`
        r = self._fetch_now()
        self._get_GPA(r)

        logging.info("%s - Initiated: [Name] %s [Courses] %d [GPA] %s [c_GPA] %s",
            self.usercode, self.name, len(self.courses), self.GPA, self.current_GPA)

        self._logout()

    def update(self):
        """Update & return newly-released courses for external call.
        """
        self._login()

        # Get `new_courses`
        r = self._fetch_all()

        # If user not regisered yet, then we can't fetch any data.
        # Remember to ogout before raise.
        if u"你还没有学期注册，无法使用本模块！" in r.content.decode("gb2312"):
            self._logout()
            raise Exception("User not registered.")

        new_courses = self._get_courses(r)
        self._get_GPA(r, ALL_TERMS)

        # Only if we got new courses should we update GPAs.
        if new_courses:
            r = self._fetch_now()
            self._get_GPA(r)

            logging.info("%s - Updated: [Name] %s [Courses] %d [GPA] %s [c_GPA] %s",
                self.usercode, self.name, len(new_courses), self.GPA, self.current_GPA)

        self._logout()
        return new_courses


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname).1s [%(asctime).19s] %(message)s", level=logging.DEBUG)
    logging.getLogger("requests").setLevel(logging.WARNING)
