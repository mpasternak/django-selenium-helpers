# -*- encoding: utf-8 -*-
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse

from django.conf import settings
from django.test.testcases import LiveServerTestCase

from selenium import webdriver
from selenium.common.exceptions import InvalidSelectorException, NoSuchElementException
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

SELENIUM_DRIVER = getattr(settings, 'SELENIUM_DRIVER', 'Firefox')
WEB_DRIVER = getattr(webdriver, SELENIUM_DRIVER)

TIMEOUT = 5000

def MyWebDriver(base, **kwargs):
    return type('MyWebDriver', (_MyWebDriver, base), kwargs)


def wd(base=None):
    if base is None:
        return MyWebDriver(WEB_DRIVER)
    return MyWebDriver(base)


class MyWebElement(WebElement):
    """WebElement with some support for jquery selectors.
    """

    def __repr__(self):
        """Return a pretty name for an element"""

        id = self.get_attribute('id')
        class_ = self.get_attribute('class')

        if len(id) > 0:
            return '#' + id
        elif len(class_) > 0:
            return '.'.join([self.tag_name] + class_.split(' '))
        else:
            return self.tag_name

    def children(self, arg=None):
        """Same as $(elem).children()
        """
        return self.parent.execute_script(
            '''return $(arguments[0]).children(arguments[1]).get();''',
            self, arg)

    def jq_parent(self):
        return self.parent.execute_script(
            '''return $(arguments[0]).parent();''',
            self)

    def prop(self, arg, value=None):
        """Same as $(elem).prop()
        """
        if value is None:
            return self.parent.execute_script(
                '''return $(arguments[0]).prop(arguments[1]);''',
                self, arg)

        return self.parent.execute_script(
            '''return $(arguments[0]).prop(arguments[1], arguments[2]);''',
            self, arg, value)

    def trigger(self, arg):
        """Same as $(elem).trigger()
        """
        return self.parent.execute_script(
            '''return $(arguments[0]).trigger(arguments[1]).get();''',
            self, arg)

    def jq_parent(self):
        """Same as $(elem).parent()
        """
        return self.parent.execute_script(
            '''return $(arguments[0]).parent().get();''', self)[0]

    def attr(self, name, value=None):
        """Same as $(elem).attr()
        """
        if value is not None:
            return self.parent.execute_script(
                '''$(arguments[0]).attr(arguments[1], arguments[2]);''',
                self, name, value)

        return self.parent.execute_script(
            '''return $(arguments[0]).attr(arguments[1]);''', self, name)

    def val(self, arg=None):
        """Same as $(elem).val()
        """
        if arg is not None:
            return self.parent.execute_script(
                '''return $(arguments[0]).val(arguments[1]);''', self, arg)

        return self.parent.execute_script(
            '''return $(arguments[0]).val();''', self)

    def text(self):
        """Same as $(elem).text()
        """
        return self.parent.execute_script(
            '''return $(arguments[0]).text();''', self)

    def change(self):
        return self.parent.execute_script(
            '''return $(arguments[0]).change();''', self)

    def find_elements_by_jquery(self, jq):
        """Same as $(elem).find(...)
        """
        return self.parent.execute_script(
            '''return $(arguments[0]).find('%s').get();''' % jq, self)

    def jq_is(self, arg):
        """Same as $(elem).is(...)
        """
        return self.parent.execute_script(
            '''return $(arguments[0]).is('%s');''' % arg, self)

    def visible(self):
        return self.jq_is(":visible")

    def hidden(self):
        return self.jq_is(":hidden")

    def find_element_by_jquery(self, jq):
        """Find exactly one element by jquery.
        """
        elems = self.find_elements_by_jquery(jq)
        if len(elems) == 1:
            return elems[0]
        else:
            raise InvalidSelectorException(
                "jQuery selector returned %i elements, expected 1" % len(elems))

    def css(self, arg):
        return self.parent.execute_script(
            '''return $(arguments[0]).css('%s');''' % arg, self)


class _MyWebDriver(object):
    def create_web_element(self, element_id):
        return MyWebElement(self, element_id)

    def ready_state(self):
        return self.execute_script("return document.readyState;")

    def wait_for_reload(self):
        WebDriverWait(self, TIMEOUT).until(lambda x: self.ready_state() == "complete")

    def find_elements_by_jquery(self, jq):
        return self.execute_script('''return $('%s').get();''' % jq)

    def find_element_by_jquery(self, jq):
        elems = self.find_elements_by_jquery(jq)
        if len(elems) == 1:
            return elems[0]
        else:
            raise InvalidSelectorException(
                "jQuery selector returned %i elements, expected 1" % len(elems))

    def wait_for_selector(self, selector, displayed=None):
        def f(selenium):
            element = selenium.find_element_by_css_selector(selector)
            if displayed is not None:
                return element.is_displayed() == displayed
            return True

        WebDriverWait(self, TIMEOUT).until(
            lambda driver: f(driver))

    def wait_for_id(self, id, displayed=None):
        def f(selenium):
            element = selenium.find_element_by_id(id)
            if displayed is not None:
                return element.is_displayed() == displayed
            return True

        WebDriverWait(self, TIMEOUT).until(
            lambda driver: f(driver))

    def assertPopupContains(self, text, accept=True):
        """Switch to popup, assert it contains at least a part
        of the text, close the popup. Error otherwise.
        """
        alert = self.switch_to_alert()
        self.assertIn(text, alert.text)
        if accept:
            alert.accept()

    def login_via_admin(self, username, password, prefix):
        """Performs user authorisation via default Django admin interface."""
        #from selenium.webdriver import Firefox
        self.get(prefix + reverse('admin:index'))
        self.find_element_by_id("id_username").send_keys(username)
        self.find_element_by_id("id_password").send_keys(password + Keys.RETURN)

        try:
            if 'grappelli' in settings.INSTALLED_APPS:
                self.wait_for_id("content-related")
            else:
                self.wait_for_id('content')

        except NoSuchElementException:
            raise Exception("Cannot login via admin")

        if "Please enter the correct" in self.page_source:
            raise Exception("Cannot login via admin")

    def logout_admin(self, prefix):
        self.get(prefix + reverse("admin:logout"))


class SeleniumTestCaseBase(LiveServerTestCase):
    """
    A base test case for Selenium, providing hepler methods for generating
    clients and logging in profiles.
    """

    url = None
    pageClass = wd()

    def open(self, url):
        self.page.get("%s%s" % (self.live_server_url, url))
        self.page.wait_for_reload()

    def get_page_kwargs(self, **kwargs):
        ret = {}
        if SELENIUM_DRIVER == "Remote":
            ret.update({
                'desired_capabilities': getattr(
                    DesiredCapabilities,
                    getattr(
                        settings, "SELENIUM_DESIRED_CAPABILITIES", "FIREFOX")),
                'command_executor': getattr(
                    settings,
                    "SELENIUM_COMMAND_EXECUTOR",
                    "http://127.0.0.1:4444/wd/hub/"
                )
            })

        if kwargs:
            ret.update(kwargs)

        return ret

    def get_page(self, *args, **kw):
        """
        :rtype: selenium.webdriver.Remote
        """
        for key, value in self.get_page_kwargs().items():
            if key not in kw:
                kw[key] = value

        return self.pageClass(*args, **kw)

    def reload(self):
        self.open(self.url)

    def login_via_admin(self, username, password, then=None):
        self.page.login_via_admin(username, password, prefix=self.live_server_url)
        if then:
            self.open(then)
            return
        self.reload()

    def setUp(self):
        self.page = self.get_page()
        self.reload()


class SeleniumTestCase(SeleniumTestCaseBase):
    """One browser window PER test case"""

    def tearDown(self):
        self.page.quit()


class SeleniumAdminMixin:
    userClass = User
    username = 'test'
    password = 'test'
    email = 'foo@example.com'
    create_user = True

    def _create_user(self):
        self.userClass.objects.create_superuser(
            username=self.username,
            password=self.password,
            email=self.email)

    def login(self):
        if self.create_user:
            self._create_user()
        self.login_via_admin(self.username, self.password, then=self.url)


class SeleniumAdminTestCase(SeleniumAdminMixin, SeleniumTestCaseBase):
    def setUp(self):
        self.page = self.get_page()
        self.login()


_global_page = None


def get_global_page(pageClass, *args, **kw):
    global _global_page
    if _global_page is None:
        _global_page = pageClass(*args, **kw)
    else:
        for key, value in kw.items():
            if key not in ['desired_capabilities']:
                setattr(_global_page, key, value)
    return _global_page


def quit_global_page():
    global _global_page
    _global_page.quit()
    _global_page = None


class SeleniumGlobalBrowserTestCase(SeleniumTestCaseBase):
    def get_page(self, *args, **kw):
        for key, value in self.get_page_kwargs().items():
            if key not in kw:
                kw[key] = value

        return get_global_page(self.pageClass, *args, **kw)


class SeleniumAdminGlobalBrowserTestCase(SeleniumAdminMixin,
                                         SeleniumGlobalBrowserTestCase):
    logout_on_teardown = True

    def setUp(self):
        self.page = self.get_page()
        self.login()


    def tearDown(self):
        if self.logout_on_teardown:
            self.page.logout_admin(self.live_server_url)