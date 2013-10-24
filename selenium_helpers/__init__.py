# -*- encoding: utf-8 -*-
import inspect
from django.core.urlresolvers import reverse
from django.conf import settings

from django.test import LiveServerTestCase
from django.conf import settings

from selenium import webdriver
from selenium.common.exceptions import InvalidSelectorException, NoSuchElementException
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.wait import WebDriverWait

WEB_DRIVER = getattr(
    webdriver, getattr(settings, 'SELENIUM_DRIVER', 'Firefox'))


def MyWebDriver(base, **kwargs):
    return type('MyWebDriver', (_MyWebDriver, base), kwargs)


def wd():
    return MyWebDriver(WEB_DRIVER)


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

    def children(self, arg):
        """Same as $(elem).children()
        """
        return self.parent.execute_script(
            '''return $(arguments[0]).children(arguments[1]).get();''',
            self, arg)

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
                '''return $(arguments[0]).attr(arguments[1], arguments[2]);''',
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

        WebDriverWait(self, 10).until(
            lambda driver: f(driver))

    def wait_for_id(self, id, displayed=None):
        def f(selenium):
            element = selenium.find_element_by_id(id)
            if displayed is not None:
                return element.is_displayed() == displayed
            return True

        WebDriverWait(self, 10).until(
            lambda driver: f(driver))

def get_selected_option(field):
    """Returns first selected <option> tag from a <select> field

    :param field:
    :ptype field: selenium.webdriver.remote.WebElement
    """

    for element in field.find_elements_by_tag_name('option'):
        if element.is_selected():
            return element


def select_option_by_text(field, value):
    """Selects an option from a <select> field basing on its text value,
    <option value="something">THE VALUE PASSED TO THIS FUNCTION</option>

    :param field: SELECT tag
    :param value: value, that should be set
    :ptype value: str
    """

    for el in field.find_elements_by_tag_name('option'):
        if el.text() == value:
            el.click()
            return

    raise Exception("Label %r not found in select %r" % (value, field))


class SeleniumTestCase(LiveServerTestCase):
    """
    A base test case for Selenium, providing hepler methods for generating
    clients and logging in profiles.
    """

    url = None
    pageClass = wd()

    def open(self, url):
        self.page.get("%s%s" % (self.live_server_url, url))

    def get_page(self):
        """
        :rtype: selenium.webdriver.Remote
        """

        kw = dict()

        args = inspect.getargspec(self.pageClass.__init__).args

        if 'command_executor' in args:
            kw['command_executor'] = 'http://%s/wd/hub' % getattr(
                settings, "SELENIUM_HOST", "127.0.0.1:4444")

        arg_cap_name = 'capabilities'
        if 'desired_capabilities' in args:
            arg_cap_name = 'desired_' + arg_cap_name
        kw[arg_cap_name] = getattr(settings, "SELENIUM_CAPABILITIES", {})

        return self.pageClass(**kw)

    def setUp(self):
        self.page = self.get_page()
        self.reload()

    def reload(self):
        self.open(self.url)

    def tearDown(self):
        self.page.quit()

    def login_via_admin(self, username, password, then=None):
        """Performs user authorisation via default Django admin interface."""
        self.open(reverse('admin:index'))
        self.page.find_element_by_id("id_username").send_keys(username)
        self.page.find_element_by_id("id_password").send_keys(password)
        self.page.find_element_by_css_selector('input[type="submit"]').click()

        try:
            if 'grappelli' in settings.INSTALLED_APPS:
                self.page.wait_for_id("content-related")
            else:
                self.page.wait_for_id('content')

        except NoSuchElementException:
            raise Exception("Cannot login via admin")
            self.page.quit()

        if then:
            self.open(then)

    def assertPopupContains(self, text):
        """Switch to popup, assert it contains at least a part
        of the text, close the popup. Error otherwise.
        """
        alert = self.page.switch_to_alert()
        self.assertIn(text, alert.text)
        alert.accept()
