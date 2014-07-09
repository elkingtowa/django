# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import re
import datetime
import unittest

from django.conf import settings, global_settings
from django.core import mail
from django.core.checks import Error
from django.core.files import temp as tempfile
from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import (NoReverseMatch,
    get_script_prefix, reverse, set_script_prefix)
# Register auth models with the admin.
from django.contrib.auth import get_permission_codename
from django.contrib.admin import ModelAdmin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.models import LogEntry, DELETION
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.contrib.admin.tests import AdminSeleniumWebDriverTestCase
from django.contrib.admin.utils import quote
from django.contrib.admin.validation import ModelAdminValidator
from django.contrib.admin.views.main import IS_POPUP_VAR
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.models import Group, User, Permission
from django.contrib.contenttypes.models import ContentType
from django.forms.utils import ErrorList
from django.template.response import TemplateResponse
from django.test import TestCase, skipUnlessDBFeature
from django.test.utils import patch_logger
from django.test import modify_settings, override_settings
from django.utils import formats
from django.utils import translation
from django.utils.cache import get_max_age
from django.utils.encoding import iri_to_uri, force_bytes, force_text
from django.utils.html import escape
from django.utils.http import urlencode
from django.utils.six.moves.urllib.parse import parse_qsl, urljoin, urlparse
from django.utils._os import upath
from django.utils import six

# local test models
from .models import (Article, BarAccount, CustomArticle, EmptyModel, FooAccount,
    Gallery, ModelWithStringPrimaryKey, Person, Persona, Picture, Podcast,
    Section, Subscriber, Vodcast, Language, Collector, Widget, Grommet,
    DooHickey, FancyDoodad, Whatsit, Category, Post, Plot, FunkyTag, Chapter,
    Book, Promo, WorkHour, Employee, Question, Answer, Inquisition, Actor,
    FoodDelivery, RowLevelChangePermissionModel, Paper, CoverLetter, Story,
    OtherStory, ComplexSortedPerson, PluggableSearchPerson, Parent, Child, AdminOrderedField,
    AdminOrderedModelMethod, AdminOrderedAdminMethod, AdminOrderedCallable,
    Report, MainPrepopulated, RelatedPrepopulated, UnorderedObject,
    Simple, UndeletableObject, UnchangeableObject, Choice, ShortMessage,
    Telegram, Pizza, Topping, FilteredManager, City, Restaurant, Worker,
    ParentWithDependentChildren, Character, FieldOverridePost, Color2)
from .admin import site, site2, CityAdmin


ERROR_MESSAGE = "Please enter the correct username and password \
for a staff account. Note that both fields may be case-sensitive."
ADMIN_VIEW_TEMPLATES_DIR = settings.TEMPLATE_DIRS + (os.path.join(os.path.dirname(upath(__file__)), 'templates'),)


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class SeleniumAdminViewsFirefoxTests(AdminSeleniumWebDriverTestCase):

    available_apps = ['admin_views'] + AdminSeleniumWebDriverTestCase.available_apps
    fixtures = ['admin-views-users.xml']
    webdriver_class = 'selenium.webdriver.firefox.webdriver.WebDriver'

    def test_aprepopulated_fields(self):
        """
        Ensure that the JavaScript-automated prepopulated fields work with the
        main form and with stacked and tabular inlines.
        Refs #13068, #9264, #9983, #9784.
        """
        self.admin_login(username='super', password='secret', login_url='/test_admin/admin/')
        self.selenium.get('%s%s' % (self.live_server_url,
            '/test_admin/admin/admin_views/mainprepopulated/add/'))

        # Main form ----------------------------------------------------------
        self.selenium.find_element_by_css_selector('#id_pubdate').send_keys('2012-02-18')
        self.get_select_option('#id_status', 'option two').click()
        self.selenium.find_element_by_css_selector('#id_name').send_keys(' this is the mAin nÀMë and it\'s awεšome')
        slug1 = self.selenium.find_element_by_css_selector('#id_slug1').get_attribute('value')
        slug2 = self.selenium.find_element_by_css_selector('#id_slug2').get_attribute('value')
        self.assertEqual(slug1, 'main-name-and-its-awesome-2012-02-18')
        self.assertEqual(slug2, 'option-two-main-name-and-its-awesome')

        # Stacked inlines ----------------------------------------------------
        # Initial inline
#        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-0-pubdate').send_keys('2011-12-17')
#        self.get_select_option('#id_relatedprepopulated_set-0-status', 'option one').click()
#        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-0-name').send_keys(' here is a sŤāÇkeð   inline !  ')
#        slug1 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-0-slug1').get_attribute('value')
#        slug2 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-0-slug2').get_attribute('value')
#        self.assertEqual(slug1, 'here-stacked-inline-2011-12-17')
#        self.assertEqual(slug2, 'option-one-here-stacked-inline')

#        # Add an inline
#        self.selenium.find_elements_by_link_text('Add another Related prepopulated')[0].click()
#        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-1-pubdate').send_keys('1999-01-25')
#        self.get_select_option('#id_relatedprepopulated_set-1-status', 'option two').click()
#        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-1-name').send_keys(' now you haVe anöther   sŤāÇkeð  inline with a very ... loooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooog text... ')
#        slug1 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-1-slug1').get_attribute('value')
#        slug2 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-1-slug2').get_attribute('value')
#        self.assertEqual(slug1, 'now-you-have-another-stacked-inline-very-loooooooo')  # 50 characters maximum for slug1 field
#        self.assertEqual(slug2, 'option-two-now-you-have-another-stacked-inline-very-looooooo')  # 60 characters maximum for slug2 field

#        # Tabular inlines ----------------------------------------------------
#        # Initial inline
#        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-0-pubdate').send_keys('1234-12-07')
#        self.get_select_option('#id_relatedprepopulated_set-2-0-status', 'option two').click()
#        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-0-name').send_keys('And now, with a tÃbűlaŘ inline !!!')
#        slug1 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-0-slug1').get_attribute('value')
#        slug2 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-0-slug2').get_attribute('value')
#        self.assertEqual(slug1, 'and-now-tabular-inline-1234-12-07')
#        self.assertEqual(slug2, 'option-two-and-now-tabular-inline')

#        # Add an inline
#        self.selenium.find_elements_by_link_text('Add another Related prepopulated')[1].click()
#        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-1-pubdate').send_keys('1981-08-22')
#        self.get_select_option('#id_relatedprepopulated_set-2-1-status', 'option one').click()
#        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-1-name').send_keys('a tÃbűlaŘ inline with ignored ;"&*^\%$#@-/`~ characters')
#        slug1 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-1-slug1').get_attribute('value')
#        slug2 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-1-slug2').get_attribute('value')
#        self.assertEqual(slug1, 'tabular-inline-ignored-characters-1981-08-22')
#        self.assertEqual(slug2, 'option-one-tabular-inline-ignored-characters')

#        # Save and check that everything is properly stored in the database
#        self.selenium.find_element_by_xpath('//input[@value="Save"]').click()
#        self.wait_page_loaded()
#        self.assertEqual(MainPrepopulated.objects.all().count(), 1)
#        MainPrepopulated.objects.get(
#            name=' this is the mAin nÀMë and it\'s awεšome',
#            pubdate='2012-02-18',
#            status='option two',
#            slug1='main-name-and-its-awesome-2012-02-18',
#            slug2='option-two-main-name-and-its-awesome',
#        )
#        self.assertEqual(RelatedPrepopulated.objects.all().count(), 4)
#        RelatedPrepopulated.objects.get(
#            name=' here is a sŤāÇkeð   inline !  ',
#            pubdate='2011-12-17',
#            status='option one',
#            slug1='here-stacked-inline-2011-12-17',
#            slug2='option-one-here-stacked-inline',
#        )
#        RelatedPrepopulated.objects.get(
#            name=' now you haVe anöther   sŤāÇkeð  inline with a very ... loooooooooooooooooo',  # 75 characters in name field
#            pubdate='1999-01-25',
#            status='option two',
#            slug1='now-you-have-another-stacked-inline-very-loooooooo',
#            slug2='option-two-now-you-have-another-stacked-inline-very-looooooo',
#        )
#        RelatedPrepopulated.objects.get(
#            name='And now, with a tÃbűlaŘ inline !!!',
#            pubdate='1234-12-07',
#            status='option two',
#            slug1='and-now-tabular-inline-1234-12-07',
#            slug2='option-two-and-now-tabular-inline',
#        )
#        RelatedPrepopulated.objects.get(
#            name='a tÃbűlaŘ inline with ignored ;"&*^\%$#@-/`~ characters',
#            pubdate='1981-08-22',
#            status='option one',
#            slug1='tabular-inline-ignored-characters-1981-08-22',
#            slug2='option-one-tabular-inline-ignored-characters',
#        )

    def test_populate_existing_object(self):
        """
        Ensure that the prepopulation works for existing objects too, as long
        as the original field is empty.
        Refs #19082.
        """
        # Slugs are empty to start with.
        item = MainPrepopulated.objects.create(
            name=' this is the mAin nÀMë',
            pubdate='2012-02-18',
            status='option two',
            slug1='',
            slug2='',
        )
        self.admin_login(username='super',
                         password='secret',
                         login_url='/test_admin/admin/')

        object_url = '%s%s' % (
            self.live_server_url,
            '/test_admin/admin/admin_views/mainprepopulated/{}/'.format(item.id))

        self.selenium.get(object_url)
        self.selenium.find_element_by_css_selector('#id_name').send_keys(' the best')

        # The slugs got prepopulated since they were originally empty
        slug1 = self.selenium.find_element_by_css_selector('#id_slug1').get_attribute('value')
        slug2 = self.selenium.find_element_by_css_selector('#id_slug2').get_attribute('value')
        self.assertEqual(slug1, 'main-name-best-2012-02-18')
        self.assertEqual(slug2, 'option-two-main-name-best')

        # Save the object
        self.selenium.find_element_by_xpath('//input[@value="Save"]').click()
        self.wait_page_loaded()

        self.selenium.get(object_url)
#        self.selenium.find_element_by_css_selector('#id_name').send_keys(' hello')

        # The slugs got prepopulated didn't change since they were originally not empty
#        slug1 = self.selenium.find_element_by_css_selector('#id_slug1').get_attribute('value')
#        slug2 = self.selenium.find_element_by_css_selector('#id_slug2').get_attribute('value')
#        self.assertEqual(slug1, 'main-name-best-2012-02-18')
#        self.assertEqual(slug2, 'option-two-main-name-best')

    def test_collapsible_fieldset(self):
        """
        Test that the 'collapse' class in fieldsets definition allows to
        show/hide the appropriate field section.
        """
        self.admin_login(username='super', password='secret', login_url='/test_admin/admin/')
        self.selenium.get('%s%s' % (self.live_server_url,
            '/test_admin/admin/admin_views/article/add/'))
        self.assertFalse(self.selenium.find_element_by_id('id_title').is_displayed())
        self.selenium.find_elements_by_link_text('Show')[0].click()
        self.assertTrue(self.selenium.find_element_by_id('id_title').is_displayed())
        self.assertEqual(
            self.selenium.find_element_by_id('fieldsetcollapser0').text,
            "Hide"
        )

    def test_first_field_focus(self):
        """JavaScript-assisted auto-focus on first usable form field."""
        # First form field has a single widget
        self.admin_login(username='super', password='secret', login_url='/test_admin/admin/')
        self.selenium.get('%s%s' % (self.live_server_url,
            '/test_admin/admin/admin_views/picture/add/'))
        self.assertEqual(
            self.selenium.switch_to_active_element(),
            self.selenium.find_element_by_id('id_name')
        )

        # First form field has a MultiWidget
#        self.selenium.get('%s%s' % (self.live_server_url,
#            '/test_admin/admin/admin_views/reservation/add/'))
#        self.assertEqual(
#            self.selenium.switch_to_active_element(),
#            self.selenium.find_element_by_id('id_start_date_0')
#        )
