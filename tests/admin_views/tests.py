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
                   ROOT_URLCONF="admin_views.urls",
                   USE_I18N=True, USE_L10N=False, LANGUAGE_CODE='en')
class AdminViewBasicTestCase(TestCase):
    fixtures = ['admin-views-users.xml', 'admin-views-colors.xml',
                'admin-views-fabrics.xml', 'admin-views-books.xml']

    # Store the bit of the URL where the admin is registered as a class
    # variable. That way we can test a second AdminSite just by subclassing
    # this test case and changing urlbit.
    urlbit = 'admin'

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()
        formats.reset_format_cache()

    def assertContentBefore(self, response, text1, text2, failing_msg=None):
        """
        Testing utility asserting that text1 appears before text2 in response
        content.
        """
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.index(force_bytes(text1)) < response.content.index(force_bytes(text2)),
            failing_msg)


class AdminViewBasicTest(AdminViewBasicTestCase):
    def test_trailing_slash_required(self):
        """
        If you leave off the trailing slash, app should redirect and add it.
        """
        response = self.client.get('/test_admin/%s/admin_views/article/add' % self.urlbit)
        self.assertRedirects(response,
            '/test_admin/%s/admin_views/article/add/' % self.urlbit,
            status_code=301)

    def test_basic_add_GET(self):
        """
        A smoke test to ensure GET on the add_view works.
        """
        response = self.client.get('/test_admin/%s/admin_views/section/add/' % self.urlbit)
        self.assertIsInstance(response, TemplateResponse)
        self.assertEqual(response.status_code, 200)

    def test_add_with_GET_args(self):
        response = self.client.get('/test_admin/%s/admin_views/section/add/' % self.urlbit, {'name': 'My Section'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="My Section"',
            msg_prefix="Couldn't find an input with the right value in the response")

    def test_basic_edit_GET(self):
        """
        A smoke test to ensure GET on the change_view works.
        """
        response = self.client.get('/test_admin/%s/admin_views/section/1/' % self.urlbit)
        self.assertIsInstance(response, TemplateResponse)
        self.assertEqual(response.status_code, 200)

    def test_basic_edit_GET_string_PK(self):
        """
        Ensure GET on the change_view works (returns an HTTP 404 error, see
        #11191) when passing a string as the PK argument for a model with an
        integer PK field.
        """
        response = self.client.get('/test_admin/%s/admin_views/section/abc/' % self.urlbit)
        self.assertEqual(response.status_code, 404)

    def test_basic_inheritance_GET_string_PK(self):
        """
        Ensure GET on the change_view works on inherited models (returns an
        HTTP 404 error, see #19951) when passing a string as the PK argument
        for a model with an integer PK field.
        """
        response = self.client.get('/test_admin/%s/admin_views/supervillain/abc/' % self.urlbit)
        self.assertEqual(response.status_code, 404)

    def test_basic_add_POST(self):
        """
        A smoke test to ensure POST on add_view works.
        """
        post_data = {
            "name": "Another Section",
            # inline data
            "article_set-TOTAL_FORMS": "3",
            "article_set-INITIAL_FORMS": "0",
            "article_set-MAX_NUM_FORMS": "0",
        }
        response = self.client.post('/test_admin/%s/admin_views/section/add/' % self.urlbit, post_data)
        self.assertEqual(response.status_code, 302)  # redirect somewhere

    def test_popup_add_POST(self):
        """
        Ensure http response from a popup is properly escaped.
        """
        post_data = {
            '_popup': '1',
            'title': 'title with a new\nline',
            'content': 'some content',
            'date_0': '2010-09-10',
            'date_1': '14:55:39',
        }
        response = self.client.post('/test_admin/%s/admin_views/article/add/' % self.urlbit, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dismissAddAnotherPopup')
        self.assertContains(response, 'title with a new\\u000Aline')

    # Post data for edit inline
    inline_post_data = {
        "name": "Test section",
        # inline data
        "article_set-TOTAL_FORMS": "6",
        "article_set-INITIAL_FORMS": "3",
        "article_set-MAX_NUM_FORMS": "0",
        "article_set-0-id": "1",
        # there is no title in database, give one here or formset will fail.
        "article_set-0-title": "Norske bostaver æøå skaper problemer",
        "article_set-0-content": "&lt;p&gt;Middle content&lt;/p&gt;",
        "article_set-0-date_0": "2008-03-18",
        "article_set-0-date_1": "11:54:58",
        "article_set-0-section": "1",
        "article_set-1-id": "2",
        "article_set-1-title": "Need a title.",
        "article_set-1-content": "&lt;p&gt;Oldest content&lt;/p&gt;",
        "article_set-1-date_0": "2000-03-18",
        "article_set-1-date_1": "11:54:58",
        "article_set-2-id": "3",
        "article_set-2-title": "Need a title.",
        "article_set-2-content": "&lt;p&gt;Newest content&lt;/p&gt;",
        "article_set-2-date_0": "2009-03-18",
        "article_set-2-date_1": "11:54:58",
        "article_set-3-id": "",
        "article_set-3-title": "",
        "article_set-3-content": "",
        "article_set-3-date_0": "",
        "article_set-3-date_1": "",
        "article_set-4-id": "",
        "article_set-4-title": "",
        "article_set-4-content": "",
        "article_set-4-date_0": "",
        "article_set-4-date_1": "",
        "article_set-5-id": "",
        "article_set-5-title": "",
        "article_set-5-content": "",
        "article_set-5-date_0": "",
        "article_set-5-date_1": "",
    }

    def test_basic_edit_POST(self):
        """
        A smoke test to ensure POST on edit_view works.
        """
        response = self.client.post('/test_admin/%s/admin_views/section/1/' % self.urlbit, self.inline_post_data)
        self.assertEqual(response.status_code, 302)  # redirect somewhere

    def test_edit_save_as(self):
        """
        Test "save as".
        """
        post_data = self.inline_post_data.copy()
        post_data.update({
            '_saveasnew': 'Save+as+new',
            "article_set-1-section": "1",
            "article_set-2-section": "1",
            "article_set-3-section": "1",
            "article_set-4-section": "1",
            "article_set-5-section": "1",
        })
        response = self.client.post('/test_admin/%s/admin_views/section/1/' % self.urlbit, post_data)
        self.assertEqual(response.status_code, 302)  # redirect somewhere

    def test_change_list_sorting_callable(self):
        """
        Ensure we can sort on a list_display field that is a callable
        (column 2 is callable_year in ArticleAdmin)
        """
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit, {'o': 2})
        self.assertContentBefore(response, 'Oldest content', 'Middle content',
            "Results of sorting on callable are out of order.")
        self.assertContentBefore(response, 'Middle content', 'Newest content',
            "Results of sorting on callable are out of order.")

    def test_change_list_sorting_model(self):
        """
        Ensure we can sort on a list_display field that is a Model method
        (column 3 is 'model_year' in ArticleAdmin)
        """
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit, {'o': '-3'})
        self.assertContentBefore(response, 'Newest content', 'Middle content',
            "Results of sorting on Model method are out of order.")
        self.assertContentBefore(response, 'Middle content', 'Oldest content',
            "Results of sorting on Model method are out of order.")

    def test_change_list_sorting_model_admin(self):
        """
        Ensure we can sort on a list_display field that is a ModelAdmin method
        (column 4 is 'modeladmin_year' in ArticleAdmin)
        """
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit, {'o': '4'})
        self.assertContentBefore(response, 'Oldest content', 'Middle content',
            "Results of sorting on ModelAdmin method are out of order.")
        self.assertContentBefore(response, 'Middle content', 'Newest content',
            "Results of sorting on ModelAdmin method are out of order.")

    def test_change_list_sorting_model_admin_reverse(self):
        """
        Ensure we can sort on a list_display field that is a ModelAdmin
        method in reverse order (i.e. admin_order_field uses the '-' prefix)
        (column 6 is 'model_year_reverse' in ArticleAdmin)
        """
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit, {'o': '6'})
        self.assertContentBefore(response, '2009', '2008',
            "Results of sorting on ModelAdmin method are out of order.")
        self.assertContentBefore(response, '2008', '2000',
            "Results of sorting on ModelAdmin method are out of order.")
        # Let's make sure the ordering is right and that we don't get a
        # FieldError when we change to descending order
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit, {'o': '-6'})
        self.assertContentBefore(response, '2000', '2008',
            "Results of sorting on ModelAdmin method are out of order.")
        self.assertContentBefore(response, '2008', '2009',
            "Results of sorting on ModelAdmin method are out of order.")

    def test_change_list_sorting_multiple(self):
        p1 = Person.objects.create(name="Chris", gender=1, alive=True)
        p2 = Person.objects.create(name="Chris", gender=2, alive=True)
        p3 = Person.objects.create(name="Bob", gender=1, alive=True)
        link1 = reverse('admin:admin_views_person_change', args=(p1.pk,))
        link2 = reverse('admin:admin_views_person_change', args=(p2.pk,))
        link3 = reverse('admin:admin_views_person_change', args=(p3.pk,))

        # Sort by name, gender
        # This hard-codes the URL because it'll fail if it runs against the
        # 'admin2' custom admin (which doesn't have the Person model).
        response = self.client.get('/test_admin/admin/admin_views/person/', {'o': '1.2'})
        self.assertContentBefore(response, link3, link1)
        self.assertContentBefore(response, link1, link2)

        # Sort by gender descending, name
        response = self.client.get('/test_admin/admin/admin_views/person/', {'o': '-2.1'})
        self.assertContentBefore(response, link2, link3)
        self.assertContentBefore(response, link3, link1)

    def test_change_list_sorting_preserve_queryset_ordering(self):
        """
        If no ordering is defined in `ModelAdmin.ordering` or in the query
        string, then the underlying order of the queryset should not be
        changed, even if it is defined in `Modeladmin.get_queryset()`.
        Refs #11868, #7309.
        """
        p1 = Person.objects.create(name="Amy", gender=1, alive=True, age=80)
        p2 = Person.objects.create(name="Bob", gender=1, alive=True, age=70)
        p3 = Person.objects.create(name="Chris", gender=2, alive=False, age=60)
        link1 = reverse('admin:admin_views_person_change', args=(p1.pk,))
        link2 = reverse('admin:admin_views_person_change', args=(p2.pk,))
        link3 = reverse('admin:admin_views_person_change', args=(p3.pk,))

        # This hard-codes the URL because it'll fail if it runs against the
        # 'admin2' custom admin (which doesn't have the Person model).
        response = self.client.get('/test_admin/admin/admin_views/person/', {})
        self.assertContentBefore(response, link3, link2)
        self.assertContentBefore(response, link2, link1)

    def test_change_list_sorting_model_meta(self):
        # Test ordering on Model Meta is respected

        l1 = Language.objects.create(iso='ur', name='Urdu')
        l2 = Language.objects.create(iso='ar', name='Arabic')
        link1 = reverse('admin:admin_views_language_change', args=(quote(l1.pk),))
        link2 = reverse('admin:admin_views_language_change', args=(quote(l2.pk),))

        response = self.client.get('/test_admin/admin/admin_views/language/', {})
        self.assertContentBefore(response, link2, link1)

        # Test we can override with query string
        response = self.client.get('/test_admin/admin/admin_views/language/', {'o': '-1'})
        self.assertContentBefore(response, link1, link2)

    def test_change_list_sorting_override_model_admin(self):
        # Test ordering on Model Admin is respected, and overrides Model Meta
        dt = datetime.datetime.now()
        p1 = Podcast.objects.create(name="A", release_date=dt)
        p2 = Podcast.objects.create(name="B", release_date=dt - datetime.timedelta(10))
        link1 = reverse('admin:admin_views_podcast_change', args=(p1.pk,))
        link2 = reverse('admin:admin_views_podcast_change', args=(p2.pk,))

        response = self.client.get('/test_admin/admin/admin_views/podcast/', {})
        self.assertContentBefore(response, link1, link2)

    def test_multiple_sort_same_field(self):
        # Check that we get the columns we expect if we have two columns
        # that correspond to the same ordering field
        dt = datetime.datetime.now()
        p1 = Podcast.objects.create(name="A", release_date=dt)
        p2 = Podcast.objects.create(name="B", release_date=dt - datetime.timedelta(10))
        link1 = reverse('admin:admin_views_podcast_change', args=(quote(p1.pk),))
        link2 = reverse('admin:admin_views_podcast_change', args=(quote(p2.pk),))

        response = self.client.get('/test_admin/admin/admin_views/podcast/', {})
        self.assertContentBefore(response, link1, link2)

        p1 = ComplexSortedPerson.objects.create(name="Bob", age=10)
        p2 = ComplexSortedPerson.objects.create(name="Amy", age=20)
        link1 = reverse('admin:admin_views_complexsortedperson_change', args=(p1.pk,))
        link2 = reverse('admin:admin_views_complexsortedperson_change', args=(p2.pk,))

        response = self.client.get('/test_admin/admin/admin_views/complexsortedperson/', {})
        # Should have 5 columns (including action checkbox col)
        self.assertContains(response, '<th scope="col"', count=5)

        self.assertContains(response, 'Name')
        self.assertContains(response, 'Colored name')

        # Check order
        self.assertContentBefore(response, 'Name', 'Colored name')

        # Check sorting - should be by name
        self.assertContentBefore(response, link2, link1)

    def test_sort_indicators_admin_order(self):
        """
        Ensures that the admin shows default sort indicators for all
        kinds of 'ordering' fields: field names, method on the model
        admin and model itself, and other callables. See #17252.
        """
        models = [(AdminOrderedField, 'adminorderedfield'),
                  (AdminOrderedModelMethod, 'adminorderedmodelmethod'),
                  (AdminOrderedAdminMethod, 'adminorderedadminmethod'),
                  (AdminOrderedCallable, 'adminorderedcallable')]
        for model, url in models:
            model.objects.create(stuff='The Last Item', order=3)
            model.objects.create(stuff='The First Item', order=1)
            model.objects.create(stuff='The Middle Item', order=2)
            response = self.client.get('/test_admin/admin/admin_views/%s/' % url, {})
            self.assertEqual(response.status_code, 200)
            # Should have 3 columns including action checkbox col.
            self.assertContains(response, '<th scope="col"', count=3, msg_prefix=url)
            # Check if the correct column was selected. 2 is the index of the
            # 'order' column in the model admin's 'list_display' with 0 being
            # the implicit 'action_checkbox' and 1 being the column 'stuff'.
            self.assertEqual(response.context['cl'].get_ordering_field_columns(), {2: 'asc'})
            # Check order of records.
            self.assertContentBefore(response, 'The First Item', 'The Middle Item')
            self.assertContentBefore(response, 'The Middle Item', 'The Last Item')

    def test_limited_filter(self):
        """Ensure admin changelist filters do not contain objects excluded via limit_choices_to.
        This also tests relation-spanning filters (e.g. 'color__value').
        """
        response = self.client.get('/test_admin/%s/admin_views/thing/' % self.urlbit)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<div id="changelist-filter">',
            msg_prefix="Expected filter not found in changelist view")
        self.assertNotContains(response, '<a href="?color__id__exact=3">Blue</a>',
            msg_prefix="Changelist filter not correctly limited by limit_choices_to")

    def test_relation_spanning_filters(self):
        response = self.client.get('/test_admin/%s/admin_views/chapterxtra1/' %
                                   self.urlbit)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<div id="changelist-filter">')
        filters = {
            'chap__id__exact': dict(
                values=[c.id for c in Chapter.objects.all()],
                test=lambda obj, value: obj.chap.id == value),
            'chap__title': dict(
                values=[c.title for c in Chapter.objects.all()],
                test=lambda obj, value: obj.chap.title == value),
            'chap__book__id__exact': dict(
                values=[b.id for b in Book.objects.all()],
                test=lambda obj, value: obj.chap.book.id == value),
            'chap__book__name': dict(
                values=[b.name for b in Book.objects.all()],
                test=lambda obj, value: obj.chap.book.name == value),
            'chap__book__promo__id__exact': dict(
                values=[p.id for p in Promo.objects.all()],
                test=lambda obj, value: obj.chap.book.promo_set.filter(id=value).exists()),
            'chap__book__promo__name': dict(
                values=[p.name for p in Promo.objects.all()],
                test=lambda obj, value: obj.chap.book.promo_set.filter(name=value).exists()),
        }
        for filter_path, params in filters.items():
            for value in params['values']:
                query_string = urlencode({filter_path: value})
                # ensure filter link exists
                self.assertContains(response, '<a href="?%s">' % query_string)
                # ensure link works
                filtered_response = self.client.get(
                    '/test_admin/%s/admin_views/chapterxtra1/?%s' % (
                        self.urlbit, query_string))
                self.assertEqual(filtered_response.status_code, 200)
                # ensure changelist contains only valid objects
                for obj in filtered_response.context['cl'].queryset.all():
                    self.assertTrue(params['test'](obj, value))

    def test_incorrect_lookup_parameters(self):
        """Ensure incorrect lookup parameters are handled gracefully."""
        response = self.client.get('/test_admin/%s/admin_views/thing/' % self.urlbit, {'notarealfield': '5'})
        self.assertRedirects(response, '/test_admin/%s/admin_views/thing/?e=1' % self.urlbit)

        # Spanning relationships through an inexistant related object (Refs #16716)
        response = self.client.get('/test_admin/%s/admin_views/thing/' % self.urlbit, {'notarealfield__whatever': '5'})
        self.assertRedirects(response, '/test_admin/%s/admin_views/thing/?e=1' % self.urlbit)

        response = self.client.get('/test_admin/%s/admin_views/thing/' % self.urlbit, {'color__id__exact': 'StringNotInteger!'})
        self.assertRedirects(response, '/test_admin/%s/admin_views/thing/?e=1' % self.urlbit)

        # Regression test for #18530
        response = self.client.get('/test_admin/%s/admin_views/thing/' % self.urlbit, {'pub_date__gte': 'foo'})
        self.assertRedirects(response, '/test_admin/%s/admin_views/thing/?e=1' % self.urlbit)

    def test_isnull_lookups(self):
        """Ensure is_null is handled correctly."""
        Article.objects.create(title="I Could Go Anywhere", content="Versatile", date=datetime.datetime.now())
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit)
        self.assertContains(response, '4 articles')
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit, {'section__isnull': 'false'})
        self.assertContains(response, '3 articles')
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit, {'section__isnull': '0'})
        self.assertContains(response, '3 articles')
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit, {'section__isnull': 'true'})
        self.assertContains(response, '1 article')
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit, {'section__isnull': '1'})
        self.assertContains(response, '1 article')

    def test_logout_and_password_change_URLs(self):
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit)
        self.assertContains(response, '<a href="/test_admin/%s/logout/">' % self.urlbit)
        self.assertContains(response, '<a href="/test_admin/%s/password_change/">' % self.urlbit)

    def test_named_group_field_choices_change_list(self):
        """
        Ensures the admin changelist shows correct values in the relevant column
        for rows corresponding to instances of a model in which a named group
        has been used in the choices option of a field.
        """
        link1 = reverse('admin:admin_views_fabric_change', args=(1,), current_app=self.urlbit)
        link2 = reverse('admin:admin_views_fabric_change', args=(2,), current_app=self.urlbit)
        response = self.client.get('/test_admin/%s/admin_views/fabric/' % self.urlbit)
        fail_msg = "Changelist table isn't showing the right human-readable values set by a model field 'choices' option named group."
        self.assertContains(response, '<a href="%s">Horizontal</a>' % link1, msg_prefix=fail_msg, html=True)
        self.assertContains(response, '<a href="%s">Vertical</a>' % link2, msg_prefix=fail_msg, html=True)

    def test_named_group_field_choices_filter(self):
        """
        Ensures the filter UI shows correctly when at least one named group has
        been used in the choices option of a model field.
        """
        response = self.client.get('/test_admin/%s/admin_views/fabric/' % self.urlbit)
        fail_msg = "Changelist filter isn't showing options contained inside a model field 'choices' option named group."
        self.assertContains(response, '<div id="changelist-filter">')
        self.assertContains(response,
            '<a href="?surface__exact=x">Horizontal</a>', msg_prefix=fail_msg, html=True)
        self.assertContains(response,
            '<a href="?surface__exact=y">Vertical</a>', msg_prefix=fail_msg, html=True)

    def test_change_list_null_boolean_display(self):
        Post.objects.create(public=None)
        # This hard-codes the URl because it'll fail if it runs
        # against the 'admin2' custom admin (which doesn't have the
        # Post model).
        response = self.client.get("/test_admin/admin/admin_views/post/")
        self.assertContains(response, 'icon-unknown.gif')

    def test_i18n_language_non_english_default(self):
        """
        Check if the JavaScript i18n view returns an empty language catalog
        if the default language is non-English but the selected language
        is English. See #13388 and #3594 for more details.
        """
        with self.settings(LANGUAGE_CODE='fr'), translation.override('en-us'):
            response = self.client.get('/test_admin/admin/jsi18n/')
            self.assertNotContains(response, 'Choisir une heure')

    def test_i18n_language_non_english_fallback(self):
        """
        Makes sure that the fallback language is still working properly
        in cases where the selected language cannot be found.
        """
        with self.settings(LANGUAGE_CODE='fr'), translation.override('none'):
            response = self.client.get('/test_admin/admin/jsi18n/')
            self.assertContains(response, 'Choisir une heure')

    def test_L10N_deactivated(self):
        """
        Check if L10N is deactivated, the JavaScript i18n view doesn't
        return localized date/time formats. Refs #14824.
        """
        with self.settings(LANGUAGE_CODE='ru', USE_L10N=False), translation.override('none'):
            response = self.client.get('/test_admin/admin/jsi18n/')
            self.assertNotContains(response, '%d.%m.%Y %H:%M:%S')
            self.assertContains(response, '%Y-%m-%d %H:%M:%S')

    def test_disallowed_filtering(self):
        with patch_logger('django.security.DisallowedModelAdminLookup', 'error') as calls:
            response = self.client.get("/test_admin/admin/admin_views/album/?owner__email__startswith=fuzzy")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(len(calls), 1)

        # Filters are allowed if explicitly included in list_filter
        response = self.client.get("/test_admin/admin/admin_views/thing/?color__value__startswith=red")
        self.assertEqual(response.status_code, 200)
        response = self.client.get("/test_admin/admin/admin_views/thing/?color__value=red")
        self.assertEqual(response.status_code, 200)

        # Filters should be allowed if they involve a local field without the
        # need to whitelist them in list_filter or date_hierarchy.
        response = self.client.get("/test_admin/admin/admin_views/person/?age__gt=30")
        self.assertEqual(response.status_code, 200)

        e1 = Employee.objects.create(name='Anonymous', gender=1, age=22, alive=True, code='123')
        e2 = Employee.objects.create(name='Visitor', gender=2, age=19, alive=True, code='124')
        WorkHour.objects.create(datum=datetime.datetime.now(), employee=e1)
        WorkHour.objects.create(datum=datetime.datetime.now(), employee=e2)
        response = self.client.get("/test_admin/admin/admin_views/workhour/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'employee__person_ptr__exact')
        response = self.client.get("/test_admin/admin/admin_views/workhour/?employee__person_ptr__exact=%d" % e1.pk)
        self.assertEqual(response.status_code, 200)

    def test_allowed_filtering_15103(self):
        """
        Regressions test for ticket 15103 - filtering on fields defined in a
        ForeignKey 'limit_choices_to' should be allowed, otherwise raw_id_fields
        can break.
        """
        # Filters should be allowed if they are defined on a ForeignKey pointing to this model
        response = self.client.get("/test_admin/admin/admin_views/inquisition/?leader__name=Palin&leader__age=27")
        self.assertEqual(response.status_code, 200)

    def test_popup_dismiss_related(self):
        """
        Regression test for ticket 20664 - ensure the pk is properly quoted.
        """
        actor = Actor.objects.create(name="Palin", age=27)
        response = self.client.get("/test_admin/admin/admin_views/actor/?%s" % IS_POPUP_VAR)
        self.assertContains(response, "opener.dismissRelatedLookupPopup(window, &#39;%s&#39;)" % actor.pk)

    def test_hide_change_password(self):
        """
        Tests if the "change password" link in the admin is hidden if the User
        does not have a usable password set.
        (against 9bea85795705d015cdadc82c68b99196a8554f5c)
        """
        user = User.objects.get(username='super')
        user.set_unusable_password()
        user.save()

        response = self.client.get('/test_admin/admin/')
        self.assertNotContains(response, reverse('admin:password_change'),
            msg_prefix='The "change password" link should not be displayed if a user does not have a usable password.')

    def test_change_view_with_show_delete_extra_context(self):
        """
        Ensured that the 'show_delete' context variable in the admin's change
        view actually controls the display of the delete button.
        Refs #10057.
        """
        instance = UndeletableObject.objects.create(name='foo')
        response = self.client.get('/test_admin/%s/admin_views/undeletableobject/%d/' %
                                   (self.urlbit, instance.pk))
        self.assertNotContains(response, 'deletelink')

    def test_allows_attributeerror_to_bubble_up(self):
        """
        Ensure that AttributeErrors are allowed to bubble when raised inside
        a change list view.

        Requires a model to be created so there's something to be displayed

        Refs: #16655, #18593, and #18747
        """
        Simple.objects.create()
        with self.assertRaises(AttributeError):
            self.client.get('/test_admin/%s/admin_views/simple/' % self.urlbit)

    def test_changelist_with_no_change_url(self):
        """
        ModelAdmin.changelist_view shouldn't result in a NoReverseMatch if url
        for change_view is removed from get_urls

        Regression test for #20934
        """
        UnchangeableObject.objects.create()
        response = self.client.get('/test_admin/admin/admin_views/unchangeableobject/')
        self.assertEqual(response.status_code, 200)
        # Check the format of the shown object -- shouldn't contain a change link
        self.assertContains(response, '<th class="field-__str__">UnchangeableObject object</th>', html=True)

    def test_invalid_appindex_url(self):
        """
        #21056 -- URL reversing shouldn't work for nonexistent apps.
        """
        good_url = '/test_admin/admin/admin_views/'
        confirm_good_url = reverse('admin:app_list',
                                   kwargs={'app_label': 'admin_views'})
        self.assertEqual(good_url, confirm_good_url)

        with self.assertRaises(NoReverseMatch):
            reverse('admin:app_list', kwargs={'app_label': 'this_should_fail'})
        with self.assertRaises(NoReverseMatch):
            reverse('admin:app_list', args=('admin_views2',))

    def test_proxy_model_content_type_is_used_for_log_entries(self):
        """
        Log entries for proxy models should have the proxy model's content
        type.

        Regression test for #21084.
        """
        color2_content_type = ContentType.objects.get_for_model(Color2, for_concrete_model=False)

        # add
        color2_add_url = reverse('admin:admin_views_color2_add')
        self.client.post(color2_add_url, {'value': 'orange'})

        color2_addition_log = LogEntry.objects.all()[0]
        self.assertEqual(color2_content_type, color2_addition_log.content_type)

        # change
        color_id = color2_addition_log.object_id
        color2_change_url = reverse('admin:admin_views_color2_change', args=(color_id,))

        self.client.post(color2_change_url, {'value': 'blue'})

        color2_change_log = LogEntry.objects.all()[0]
        self.assertEqual(color2_content_type, color2_change_log.content_type)

        # delete
        color2_delete_url = reverse('admin:admin_views_color2_delete', args=(color_id,))
        self.client.post(color2_delete_url)

        color2_delete_log = LogEntry.objects.all()[0]
        self.assertEqual(color2_content_type, color2_delete_log.content_type)


@override_settings(TEMPLATE_DIRS=ADMIN_VIEW_TEMPLATES_DIR)
class AdminCustomTemplateTests(AdminViewBasicTestCase):
    def test_extended_bodyclass_template_change_form(self):
        """
        Ensure that the admin/change_form.html template uses block.super in the
        bodyclass block.
        """
        response = self.client.get('/test_admin/%s/admin_views/section/add/' % self.urlbit)
        self.assertContains(response, 'bodyclass_consistency_check ')

    def test_extended_bodyclass_template_change_password(self):
        """
        Ensure that the auth/user/change_password.html template uses block
        super in the bodyclass block.
        """
        user = User.objects.get(username='super')
        response = self.client.get('/test_admin/%s/auth/user/%s/password/' % (self.urlbit, user.id))
        self.assertContains(response, 'bodyclass_consistency_check ')

    def test_extended_bodyclass_template_index(self):
        """
        Ensure that the admin/index.html template uses block.super in the
        bodyclass block.
        """
        response = self.client.get('/test_admin/%s/' % self.urlbit)
        self.assertContains(response, 'bodyclass_consistency_check ')

    def test_extended_bodyclass_change_list(self):
        """
        Ensure that the admin/change_list.html' template uses block.super
        in the bodyclass block.
        """
        response = self.client.get('/test_admin/%s/admin_views/article/' % self.urlbit)
        self.assertContains(response, 'bodyclass_consistency_check ')

    def test_extended_bodyclass_template_login(self):
        """
        Ensure that the admin/login.html template uses block.super in the
        bodyclass block.
        """
        self.client.logout()
        response = self.client.get('/test_admin/%s/login/' % self.urlbit)
        self.assertContains(response, 'bodyclass_consistency_check ')

    def test_extended_bodyclass_template_delete_confirmation(self):
        """
        Ensure that the admin/delete_confirmation.html template uses
        block.super in the bodyclass block.
        """
        group = Group.objects.create(name="foogroup")
        response = self.client.get('/test_admin/%s/auth/group/%s/delete/' % (self.urlbit, group.id))
        self.assertContains(response, 'bodyclass_consistency_check ')

    def test_extended_bodyclass_template_delete_selected_confirmation(self):
        """
        Ensure that the admin/delete_selected_confirmation.html template uses
        block.super in bodyclass block.
        """
        group = Group.objects.create(name="foogroup")
        post_data = {
            'action': 'delete_selected',
            'selected_across': '0',
            'index': '0',
            '_selected_action': group.id
        }
        response = self.client.post('/test_admin/%s/auth/group/' % (self.urlbit), post_data)
        self.assertContains(response, 'bodyclass_consistency_check ')

    def test_filter_with_custom_template(self):
        """
        Ensure that one can use a custom template to render an admin filter.
        Refs #17515.
        """
        response = self.client.get("/test_admin/admin/admin_views/color2/")
        self.assertTemplateUsed(response, 'custom_filter_template.html')


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
                   ROOT_URLCONF="admin_views.urls")
class AdminViewFormUrlTest(TestCase):
    fixtures = ["admin-views-users.xml"]
    urlbit = "admin3"

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_change_form_URL_has_correct_value(self):
        """
        Tests whether change_view has form_url in response.context
        """
        response = self.client.get('/test_admin/%s/admin_views/section/1/' % self.urlbit)
        self.assertTrue('form_url' in response.context, msg='form_url not present in response.context')
        self.assertEqual(response.context['form_url'], 'pony')

    def test_initial_data_can_be_overridden(self):
        """
        Tests that the behavior for setting initial
        form data can be overridden in the ModelAdmin class.

        Usually, the initial value is set via the GET params.
        """
        response = self.client.get('/test_admin/%s/admin_views/restaurant/add/' % self.urlbit, {'name': 'test_value'})
        # this would be the usual behaviour
        self.assertNotContains(response, 'value="test_value"')
        # this is the overridden behaviour
        self.assertContains(response, 'value="overridden_value"')


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
                   ROOT_URLCONF="admin_views.urls")
class AdminJavaScriptTest(TestCase):
    fixtures = ['admin-views-users.xml']

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_js_minified_only_if_debug_is_false(self):
        """
        Ensure that the minified versions of the JS files are only used when
        DEBUG is False.
        Refs #17521.
        """
        with override_settings(DEBUG=False):
            response = self.client.get(
                '/test_admin/%s/admin_views/section/add/' % 'admin')
            self.assertNotContains(response, 'jquery.js')
            self.assertContains(response, 'jquery.min.js')
            self.assertNotContains(response, 'prepopulate.js')
            self.assertContains(response, 'prepopulate.min.js')
            self.assertNotContains(response, 'actions.js')
            self.assertContains(response, 'actions.min.js')
            self.assertNotContains(response, 'collapse.js')
            self.assertContains(response, 'collapse.min.js')
            self.assertNotContains(response, 'inlines.js')
            self.assertContains(response, 'inlines.min.js')
        with override_settings(DEBUG=True):
            response = self.client.get(
                '/test_admin/%s/admin_views/section/add/' % 'admin')
            self.assertContains(response, 'jquery.js')
            self.assertNotContains(response, 'jquery.min.js')
            self.assertContains(response, 'prepopulate.js')
            self.assertNotContains(response, 'prepopulate.min.js')
            self.assertContains(response, 'actions.js')
            self.assertNotContains(response, 'actions.min.js')
            self.assertContains(response, 'collapse.js')
            self.assertNotContains(response, 'collapse.min.js')
            self.assertContains(response, 'inlines.js')
            self.assertNotContains(response, 'inlines.min.js')


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class SaveAsTests(TestCase):
    fixtures = ['admin-views-users.xml', 'admin-views-person.xml']

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_save_as_duplication(self):
        """Ensure save as actually creates a new person"""
        post_data = {'_saveasnew': '', 'name': 'John M', 'gender': 1, 'age': 42}
        self.client.post('/test_admin/admin/admin_views/person/1/', post_data)
        self.assertEqual(len(Person.objects.filter(name='John M')), 1)
        self.assertEqual(len(Person.objects.filter(id=1)), 1)

    def test_save_as_display(self):
        """
        Ensure that 'save as' is displayed when activated and after submitting
        invalid data aside save_as_new will not show us a form to overwrite the
        initial model.
        """
        response = self.client.get('/test_admin/admin/admin_views/person/1/')
        self.assertTrue(response.context['save_as'])
        post_data = {'_saveasnew': '', 'name': 'John M', 'gender': 3, 'alive': 'checked'}
        response = self.client.post('/test_admin/admin/admin_views/person/1/', post_data)
        self.assertEqual(response.context['form_url'], '/test_admin/admin/admin_views/person/add/')


@override_settings(ROOT_URLCONF="admin_views.urls")
class CustomModelAdminTest(AdminViewBasicTestCase):
    urlbit = "admin2"

    def test_custom_admin_site_login_form(self):
        self.client.logout()
        response = self.client.get('/test_admin/admin2/', follow=True)
        self.assertIsInstance(response, TemplateResponse)
        self.assertEqual(response.status_code, 200)
        login = self.client.post('/test_admin/admin2/login/', {
            REDIRECT_FIELD_NAME: '/test_admin/admin2/',
            'username': 'customform',
            'password': 'secret',
        }, follow=True)
        self.assertIsInstance(login, TemplateResponse)
        self.assertEqual(login.status_code, 200)
        self.assertContains(login, 'custom form error')

    def test_custom_admin_site_login_template(self):
        self.client.logout()
        response = self.client.get('/test_admin/admin2/', follow=True)
        self.assertIsInstance(response, TemplateResponse)
        self.assertTemplateUsed(response, 'custom_admin/login.html')
        self.assertContains(response, 'Hello from a custom login template')

    def test_custom_admin_site_logout_template(self):
        response = self.client.get('/test_admin/admin2/logout/')
        self.assertIsInstance(response, TemplateResponse)
        self.assertTemplateUsed(response, 'custom_admin/logout.html')
        self.assertContains(response, 'Hello from a custom logout template')

    def test_custom_admin_site_index_view_and_template(self):
        try:
            response = self.client.get('/test_admin/admin2/')
        except TypeError:
            self.fail('AdminSite.index_template should accept a list of template paths')
        self.assertIsInstance(response, TemplateResponse)
        self.assertTemplateUsed(response, 'custom_admin/index.html')
        self.assertContains(response, 'Hello from a custom index template *bar*')

    def test_custom_admin_site_app_index_view_and_template(self):
        response = self.client.get('/test_admin/admin2/admin_views/')
        self.assertIsInstance(response, TemplateResponse)
        self.assertTemplateUsed(response, 'custom_admin/app_index.html')
        self.assertContains(response, 'Hello from a custom app_index template')

    def test_custom_admin_site_password_change_template(self):
        response = self.client.get('/test_admin/admin2/password_change/')
        self.assertIsInstance(response, TemplateResponse)
        self.assertTemplateUsed(response, 'custom_admin/password_change_form.html')
        self.assertContains(response, 'Hello from a custom password change form template')

    def test_custom_admin_site_password_change_done_template(self):
        response = self.client.get('/test_admin/admin2/password_change/done/')
        self.assertIsInstance(response, TemplateResponse)
        self.assertTemplateUsed(response, 'custom_admin/password_change_done.html')
        self.assertContains(response, 'Hello from a custom password change done template')

    def test_custom_admin_site_view(self):
        self.client.login(username='super', password='secret')
        response = self.client.get('/test_admin/%s/my_view/' % self.urlbit)
        self.assertEqual(response.content, b"Django is a magical pony!")

    def test_pwd_change_custom_template(self):
        self.client.login(username='super', password='secret')
        su = User.objects.get(username='super')
        try:
            response = self.client.get('/test_admin/admin4/auth/user/%s/password/' % su.pk)
        except TypeError:
            self.fail('ModelAdmin.change_user_password_template should accept a list of template paths')
        self.assertEqual(response.status_code, 200)


def get_perm(Model, perm):
    """Return the permission object, for the Model"""
    ct = ContentType.objects.get_for_model(Model)
    return Permission.objects.get(content_type=ct, codename=perm)


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class AdminViewPermissionsTest(TestCase):
    """Tests for Admin Views Permissions."""

    fixtures = ['admin-views-users.xml']

    def setUp(self):
        """Test setup."""
        # Setup permissions, for our users who can add, change, and delete.
        # We can't put this into the fixture, because the content type id
        # and the permission id could be different on each run of the test.

        opts = Article._meta

        # User who can add Articles
        add_user = User.objects.get(username='adduser')
        add_user.user_permissions.add(get_perm(Article,
            get_permission_codename('add', opts)))

        # User who can change Articles
        change_user = User.objects.get(username='changeuser')
        change_user.user_permissions.add(get_perm(Article,
            get_permission_codename('change', opts)))

        # User who can delete Articles
        delete_user = User.objects.get(username='deleteuser')
        delete_user.user_permissions.add(get_perm(Article,
            get_permission_codename('delete', opts)))

        delete_user.user_permissions.add(get_perm(Section,
            get_permission_codename('delete', Section._meta)))

        # login POST dicts
        self.super_login = {
            REDIRECT_FIELD_NAME: '/test_admin/admin/',
            'username': 'super',
            'password': 'secret',
        }
        self.super_email_login = {
            REDIRECT_FIELD_NAME: '/test_admin/admin/',
            'username': 'super@example.com',
            'password': 'secret',
        }
        self.super_email_bad_login = {
            REDIRECT_FIELD_NAME: '/test_admin/admin/',
            'username': 'super@example.com',
            'password': 'notsecret',
        }
        self.adduser_login = {
            REDIRECT_FIELD_NAME: '/test_admin/admin/',
            'username': 'adduser',
            'password': 'secret',
        }
        self.changeuser_login = {
            REDIRECT_FIELD_NAME: '/test_admin/admin/',
            'username': 'changeuser',
            'password': 'secret',
        }
        self.deleteuser_login = {
            REDIRECT_FIELD_NAME: '/test_admin/admin/',
            'username': 'deleteuser',
            'password': 'secret',
        }
        self.joepublic_login = {
            REDIRECT_FIELD_NAME: '/test_admin/admin/',
            'username': 'joepublic',
            'password': 'secret',
        }
        self.no_username_login = {
            REDIRECT_FIELD_NAME: '/test_admin/admin/',
            'password': 'secret',
        }

    def test_login(self):
        """
        Make sure only staff members can log in.

        Successful posts to the login page will redirect to the original url.
        Unsuccessful attempts will continue to render the login page with
        a 200 status code.
        """
        login_url = reverse('admin:login') + '?next=/test_admin/admin/'
        # Super User
        response = self.client.get('/test_admin/admin/')
        self.assertEqual(response.status_code, 302)
        login = self.client.post(login_url, self.super_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)
        self.client.get('/test_admin/admin/logout/')

        # Test if user enters email address
        response = self.client.get('/test_admin/admin/')
        self.assertEqual(response.status_code, 302)
        login = self.client.post(login_url, self.super_email_login)
        self.assertContains(login, ERROR_MESSAGE)
        # only correct passwords get a username hint
        login = self.client.post(login_url, self.super_email_bad_login)
        self.assertContains(login, ERROR_MESSAGE)
        new_user = User(username='jondoe', password='secret', email='super@example.com')
        new_user.save()
        # check to ensure if there are multiple email addresses a user doesn't get a 500
        login = self.client.post(login_url, self.super_email_login)
        self.assertContains(login, ERROR_MESSAGE)

        # Add User
        response = self.client.get('/test_admin/admin/')
        self.assertEqual(response.status_code, 302)
        login = self.client.post(login_url, self.adduser_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)
        self.client.get('/test_admin/admin/logout/')

        # Change User
        response = self.client.get('/test_admin/admin/')
        self.assertEqual(response.status_code, 302)
        login = self.client.post(login_url, self.changeuser_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)
        self.client.get('/test_admin/admin/logout/')

        # Delete User
        response = self.client.get('/test_admin/admin/')
        self.assertEqual(response.status_code, 302)
        login = self.client.post(login_url, self.deleteuser_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)
        self.client.get('/test_admin/admin/logout/')

        # Regular User should not be able to login.
        response = self.client.get('/test_admin/admin/')
        self.assertEqual(response.status_code, 302)
        login = self.client.post(login_url, self.joepublic_login)
        self.assertEqual(login.status_code, 200)
        self.assertContains(login, ERROR_MESSAGE)

        # Requests without username should not return 500 errors.
        response = self.client.get('/test_admin/admin/')
        self.assertEqual(response.status_code, 302)
        login = self.client.post(login_url, self.no_username_login)
        self.assertEqual(login.status_code, 200)
        form = login.context[0].get('form')
        self.assertEqual(form.errors['username'][0], 'This field is required.')

    def test_login_successfully_redirects_to_original_URL(self):
        response = self.client.get('/test_admin/admin/')
        self.assertEqual(response.status_code, 302)
        query_string = 'the-answer=42'
        redirect_url = '/test_admin/admin/?%s' % query_string
        new_next = {REDIRECT_FIELD_NAME: redirect_url}
        post_data = self.super_login.copy()
        post_data.pop(REDIRECT_FIELD_NAME)
        login = self.client.post(
            '%s?%s' % (reverse('admin:login'), urlencode(new_next)),
            post_data)
        self.assertRedirects(login, redirect_url)

    def test_double_login_is_not_allowed(self):
        """Regression test for #19327"""
        login_url = reverse('admin:login') + '?next=/test_admin/admin/'

        response = self.client.get('/test_admin/admin/')
        self.assertEqual(response.status_code, 302)

        # Establish a valid admin session
        login = self.client.post(login_url, self.super_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)

        # Logging in with non-admin user fails
        login = self.client.post(login_url, self.joepublic_login)
        self.assertEqual(login.status_code, 200)
        self.assertContains(login, ERROR_MESSAGE)

        # Establish a valid admin session
        login = self.client.post(login_url, self.super_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)

        # Logging in with admin user while already logged in
        login = self.client.post(login_url, self.super_login)
        self.assertRedirects(login, '/test_admin/admin/')
        self.assertFalse(login.context)
        self.client.get('/test_admin/admin/logout/')

    def test_add_view(self):
        """Test add view restricts access and actually adds items."""

        login_url = reverse('admin:login') + '?next=/test_admin/admin/'
        add_dict = {'title': 'Døm ikke',
                    'content': '<p>great article</p>',
                    'date_0': '2008-03-18', 'date_1': '10:54:39',
                    'section': 1}

        # Change User should not have access to add articles
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.changeuser_login)
        # make sure the view removes test cookie
        self.assertEqual(self.client.session.test_cookie_worked(), False)
        response = self.client.get('/test_admin/admin/admin_views/article/add/')
        self.assertEqual(response.status_code, 403)
        # Try POST just to make sure
        post = self.client.post('/test_admin/admin/admin_views/article/add/', add_dict)
        self.assertEqual(post.status_code, 403)
        self.assertEqual(Article.objects.all().count(), 3)
        self.client.get('/test_admin/admin/logout/')

        # Add user may login and POST to add view, then redirect to admin root
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.adduser_login)
        addpage = self.client.get('/test_admin/admin/admin_views/article/add/')
        change_list_link = '&rsaquo; <a href="/test_admin/admin/admin_views/article/">Articles</a>'
        self.assertNotContains(addpage, change_list_link,
            msg_prefix='User restricted to add permission is given link to change list view in breadcrumbs.')
        post = self.client.post('/test_admin/admin/admin_views/article/add/', add_dict)
        self.assertRedirects(post, '/test_admin/admin/')
        self.assertEqual(Article.objects.all().count(), 4)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Greetings from a created object')
        self.client.get('/test_admin/admin/logout/')

        # Super can add too, but is redirected to the change list view
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.super_login)
        addpage = self.client.get('/test_admin/admin/admin_views/article/add/')
        self.assertContains(addpage, change_list_link,
            msg_prefix='Unrestricted user is not given link to change list view in breadcrumbs.')
        post = self.client.post('/test_admin/admin/admin_views/article/add/', add_dict)
        self.assertRedirects(post, '/test_admin/admin/admin_views/article/')
        self.assertEqual(Article.objects.all().count(), 5)
        self.client.get('/test_admin/admin/logout/')

        # 8509 - if a normal user is already logged in, it is possible
        # to change user into the superuser without error
        self.client.login(username='joepublic', password='secret')
        # Check and make sure that if user expires, data still persists
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.super_login)
        # make sure the view removes test cookie
        self.assertEqual(self.client.session.test_cookie_worked(), False)

    def test_change_view(self):
        """Change view should restrict access and allow users to edit items."""

        login_url = reverse('admin:login') + '?next=/test_admin/admin/'
        change_dict = {'title': 'Ikke fordømt',
                       'content': '<p>edited article</p>',
                       'date_0': '2008-03-18', 'date_1': '10:54:39',
                       'section': 1}

        # add user should not be able to view the list of article or change any of them
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.adduser_login)
        response = self.client.get('/test_admin/admin/admin_views/article/')
        self.assertEqual(response.status_code, 403)
        response = self.client.get('/test_admin/admin/admin_views/article/1/')
        self.assertEqual(response.status_code, 403)
        post = self.client.post('/test_admin/admin/admin_views/article/1/', change_dict)
        self.assertEqual(post.status_code, 403)
        self.client.get('/test_admin/admin/logout/')

        # change user can view all items and edit them
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.changeuser_login)
        response = self.client.get('/test_admin/admin/admin_views/article/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/test_admin/admin/admin_views/article/1/')
        self.assertEqual(response.status_code, 200)
        post = self.client.post('/test_admin/admin/admin_views/article/1/', change_dict)
        self.assertRedirects(post, '/test_admin/admin/admin_views/article/')
        self.assertEqual(Article.objects.get(pk=1).content, '<p>edited article</p>')

        # one error in form should produce singular error message, multiple errors plural
        change_dict['title'] = ''
        post = self.client.post('/test_admin/admin/admin_views/article/1/', change_dict)
        self.assertContains(post, 'Please correct the error below.',
            msg_prefix='Singular error message not found in response to post with one error')

        change_dict['content'] = ''
        post = self.client.post('/test_admin/admin/admin_views/article/1/', change_dict)
        self.assertContains(post, 'Please correct the errors below.',
            msg_prefix='Plural error message not found in response to post with multiple errors')
        self.client.get('/test_admin/admin/logout/')

        # Test redirection when using row-level change permissions. Refs #11513.
        RowLevelChangePermissionModel.objects.create(id=1, name="odd id")
        RowLevelChangePermissionModel.objects.create(id=2, name="even id")
        for login_dict in [self.super_login, self.changeuser_login, self.adduser_login, self.deleteuser_login]:
            self.client.post(login_url, login_dict)
            response = self.client.get('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/1/')
            self.assertEqual(response.status_code, 403)
            response = self.client.post('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/1/', {'name': 'changed'})
            self.assertEqual(RowLevelChangePermissionModel.objects.get(id=1).name, 'odd id')
            self.assertEqual(response.status_code, 403)
            response = self.client.get('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/2/')
            self.assertEqual(response.status_code, 200)
            response = self.client.post('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/2/', {'name': 'changed'})
            self.assertEqual(RowLevelChangePermissionModel.objects.get(id=2).name, 'changed')
            self.assertRedirects(response, '/test_admin/admin/')
            self.client.get('/test_admin/admin/logout/')

        for login_dict in [self.joepublic_login, self.no_username_login]:
            self.client.post(login_url, login_dict)
            response = self.client.get('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/1/', follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'login-form')
            response = self.client.post('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/1/', {'name': 'changed'}, follow=True)
            self.assertEqual(RowLevelChangePermissionModel.objects.get(id=1).name, 'odd id')
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'login-form')
            response = self.client.get('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/2/', follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'login-form')
            response = self.client.post('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/2/', {'name': 'changed again'}, follow=True)
            self.assertEqual(RowLevelChangePermissionModel.objects.get(id=2).name, 'changed')
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'login-form')
            self.client.get('/test_admin/admin/logout/')

    def test_history_view(self):
        """History view should restrict access."""

        login_url = reverse('admin:login') + '?next=/test_admin/admin/'

        # add user should not be able to view the list of article or change any of them
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.adduser_login)
        response = self.client.get('/test_admin/admin/admin_views/article/1/history/')
        self.assertEqual(response.status_code, 403)
        self.client.get('/test_admin/admin/logout/')

        # change user can view all items and edit them
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.changeuser_login)
        response = self.client.get('/test_admin/admin/admin_views/article/1/history/')
        self.assertEqual(response.status_code, 200)

        # Test redirection when using row-level change permissions. Refs #11513.
        RowLevelChangePermissionModel.objects.create(id=1, name="odd id")
        RowLevelChangePermissionModel.objects.create(id=2, name="even id")
        for login_dict in [self.super_login, self.changeuser_login, self.adduser_login, self.deleteuser_login]:
            self.client.post(login_url, login_dict)
            response = self.client.get('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/1/history/')
            self.assertEqual(response.status_code, 403)

            response = self.client.get('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/2/history/')
            self.assertEqual(response.status_code, 200)

            self.client.get('/test_admin/admin/logout/')

        for login_dict in [self.joepublic_login, self.no_username_login]:
            self.client.post(login_url, login_dict)
            response = self.client.get('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/1/history/', follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'login-form')
            response = self.client.get('/test_admin/admin/admin_views/rowlevelchangepermissionmodel/2/history/', follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'login-form')

            self.client.get('/test_admin/admin/logout/')

    def test_conditionally_show_add_section_link(self):
        """
        The foreign key widget should only show the "add related" button if the
        user has permission to add that related item.
        """
        login_url = reverse('admin:login') + '?next=/test_admin/admin/'
        # Set up and log in user.
        url = '/test_admin/admin/admin_views/article/add/'
        add_link_text = ' class="add-another"'
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.adduser_login)
        # The add user can't add sections yet, so they shouldn't see the "add
        # section" link.
        response = self.client.get(url)
        self.assertNotContains(response, add_link_text)
        # Allow the add user to add sections too. Now they can see the "add
        # section" link.
        add_user = User.objects.get(username='adduser')
        perm = get_perm(Section, get_permission_codename('add', Section._meta))
        add_user.user_permissions.add(perm)
        response = self.client.get(url)
        self.assertContains(response, add_link_text)

    def test_custom_model_admin_templates(self):
        login_url = reverse('admin:login') + '?next=/test_admin/admin/'
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.super_login)

        # Test custom change list template with custom extra context
        response = self.client.get('/test_admin/admin/admin_views/customarticle/')
        self.assertContains(response, "var hello = 'Hello!';")
        self.assertTemplateUsed(response, 'custom_admin/change_list.html')

        # Test custom add form template
        response = self.client.get('/test_admin/admin/admin_views/customarticle/add/')
        self.assertTemplateUsed(response, 'custom_admin/add_form.html')

        # Add an article so we can test delete, change, and history views
        post = self.client.post('/test_admin/admin/admin_views/customarticle/add/', {
            'content': '<p>great article</p>',
            'date_0': '2008-03-18',
            'date_1': '10:54:39'
        })
        self.assertRedirects(post, '/test_admin/admin/admin_views/customarticle/')
        self.assertEqual(CustomArticle.objects.all().count(), 1)
        article_pk = CustomArticle.objects.all()[0].pk

        # Test custom delete, change, and object history templates
        # Test custom change form template
        response = self.client.get('/test_admin/admin/admin_views/customarticle/%d/' % article_pk)
        self.assertTemplateUsed(response, 'custom_admin/change_form.html')
        response = self.client.get('/test_admin/admin/admin_views/customarticle/%d/delete/' % article_pk)
        self.assertTemplateUsed(response, 'custom_admin/delete_confirmation.html')
        response = self.client.post('/test_admin/admin/admin_views/customarticle/', data={
            'index': 0,
            'action': ['delete_selected'],
            '_selected_action': ['1'],
        })
        self.assertTemplateUsed(response, 'custom_admin/delete_selected_confirmation.html')
        response = self.client.get('/test_admin/admin/admin_views/customarticle/%d/history/' % article_pk)
        self.assertTemplateUsed(response, 'custom_admin/object_history.html')

        self.client.get('/test_admin/admin/logout/')

    def test_delete_view(self):
        """Delete view should restrict access and actually delete items."""

        login_url = reverse('admin:login') + '?next=/test_admin/admin/'
        delete_dict = {'post': 'yes'}

        # add user should not be able to delete articles
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.adduser_login)
        response = self.client.get('/test_admin/admin/admin_views/article/1/delete/')
        self.assertEqual(response.status_code, 403)
        post = self.client.post('/test_admin/admin/admin_views/article/1/delete/', delete_dict)
        self.assertEqual(post.status_code, 403)
        self.assertEqual(Article.objects.all().count(), 3)
        self.client.get('/test_admin/admin/logout/')

        # Delete user can delete
        self.client.get('/test_admin/admin/')
        self.client.post(login_url, self.deleteuser_login)
        response = self.client.get('/test_admin/admin/admin_views/section/1/delete/')
        # test response contains link to related Article
        self.assertContains(response, "admin_views/article/1/")

        response = self.client.get('/test_admin/admin/admin_views/article/1/delete/')
        self.assertEqual(response.status_code, 200)
        post = self.client.post('/test_admin/admin/admin_views/article/1/delete/', delete_dict)
        self.assertRedirects(post, '/test_admin/admin/')
        self.assertEqual(Article.objects.all().count(), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Greetings from a deleted object')
        article_ct = ContentType.objects.get_for_model(Article)
        logged = LogEntry.objects.get(content_type=article_ct, action_flag=DELETION)
        self.assertEqual(logged.object_id, '1')
        self.client.get('/test_admin/admin/logout/')

    def test_disabled_permissions_when_logged_in(self):
        self.client.login(username='super', password='secret')
        superuser = User.objects.get(username='super')
        superuser.is_active = False
        superuser.save()

        response = self.client.get('/test_admin/admin/', follow=True)
        self.assertContains(response, 'id="login-form"')
        self.assertNotContains(response, 'Log out')

        response = self.client.get('/test_admin/admin/secure-view/', follow=True)
        self.assertContains(response, 'id="login-form"')

    def test_disabled_staff_permissions_when_logged_in(self):
        self.client.login(username='super', password='secret')
        superuser = User.objects.get(username='super')
        superuser.is_staff = False
        superuser.save()

        response = self.client.get('/test_admin/admin/', follow=True)
        self.assertContains(response, 'id="login-form"')
        self.assertNotContains(response, 'Log out')

        response = self.client.get('/test_admin/admin/secure-view/', follow=True)
        self.assertContains(response, 'id="login-form"')

    def test_app_index_fail_early(self):
        """
        If a user has no module perms, avoid iterating over all the modeladmins
        in the registry.
        """
        login_url = reverse('admin:login') + '?next=/test_admin/admin/'
        opts = Article._meta
        change_user = User.objects.get(username='changeuser')
        permission = get_perm(Article, get_permission_codename('change', opts))

        self.client.post(login_url, self.changeuser_login)

        # the user has no module permissions, because this module doesn't exist
        change_user.user_permissions.remove(permission)
        response = self.client.get('/test_admin/admin/admin_views/')
        self.assertEqual(response.status_code, 403)

        # the user now has module permissions
        change_user.user_permissions.add(permission)
        response = self.client.get('/test_admin/admin/admin_views/')
        self.assertEqual(response.status_code, 200)

    def test_shortcut_view_only_available_to_staff(self):
        """
        Only admin users should be able to use the admin shortcut view.
        """
        model_ctype = ContentType.objects.get_for_model(ModelWithStringPrimaryKey)
        obj = ModelWithStringPrimaryKey.objects.create(string_pk='foo')
        shortcut_url = "/test_admin/admin/r/%s/%s/" % (model_ctype.pk, obj.pk)

        # Not logged in: we should see the login page.
        response = self.client.get(shortcut_url, follow=True)
        self.assertTemplateUsed(response, 'admin/login.html')

        # Logged in? Redirect.
        self.client.login(username='super', password='secret')
        response = self.client.get(shortcut_url, follow=False)
        # Can't use self.assertRedirects() because User.get_absolute_url() is silly.
        self.assertEqual(response.status_code, 302)
        # Domain may depend on contrib.sites tests also run
        six.assertRegex(self, response.url, 'http://(testserver|example.com)/dummy/foo/')

    def test_has_module_permission(self):
        """
        Ensure that has_module_permission() returns True for all users who
        have any permission for that module (add, change, or delete), so that
        the module is displayed on the admin index page.
        """
        login_url = reverse('admin:login') + '?next=/test_admin/admin/'

        self.client.post(login_url, self.super_login)
        response = self.client.get('/test_admin/admin/')
        self.assertContains(response, 'admin_views')
        self.assertContains(response, 'Articles')
        self.client.get('/test_admin/admin/logout/')

        self.client.post(login_url, self.adduser_login)
        response = self.client.get('/test_admin/admin/')
        self.assertContains(response, 'admin_views')
        self.assertContains(response, 'Articles')
        self.client.get('/test_admin/admin/logout/')

        self.client.post(login_url, self.changeuser_login)
        response = self.client.get('/test_admin/admin/')
        self.assertContains(response, 'admin_views')
        self.assertContains(response, 'Articles')
        self.client.get('/test_admin/admin/logout/')

        self.client.post(login_url, self.deleteuser_login)
        response = self.client.get('/test_admin/admin/')
        self.assertContains(response, 'admin_views')
        self.assertContains(response, 'Articles')
        self.client.get('/test_admin/admin/logout/')

    def test_overriding_has_module_permission(self):
        """
        Ensure that overriding has_module_permission() has the desired effect.
        In this case, it always returns False, so the module should not be
        displayed on the admin index page for any users.
        """
        login_url = reverse('admin:login') + '?next=/test_admin/admin7/'

        self.client.post(login_url, self.super_login)
        response = self.client.get('/test_admin/admin7/')
        self.assertNotContains(response, 'admin_views')
        self.assertNotContains(response, 'Articles')
        self.client.get('/test_admin/admin7/logout/')

        self.client.post(login_url, self.adduser_login)
        response = self.client.get('/test_admin/admin7/')
        self.assertNotContains(response, 'admin_views')
        self.assertNotContains(response, 'Articles')
        self.client.get('/test_admin/admin7/logout/')

        self.client.post(login_url, self.changeuser_login)
        response = self.client.get('/test_admin/admin7/')
        self.assertNotContains(response, 'admin_views')
        self.assertNotContains(response, 'Articles')
        self.client.get('/test_admin/admin7/logout/')

        self.client.post(login_url, self.deleteuser_login)
        response = self.client.get('/test_admin/admin7/')
        self.assertNotContains(response, 'admin_views')
        self.assertNotContains(response, 'Articles')
        self.client.get('/test_admin/admin7/logout/')


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class AdminViewsNoUrlTest(TestCase):
    """Regression test for #17333"""

    fixtures = ['admin-views-users.xml']

    def setUp(self):
        opts = Report._meta
        # User who can change Reports
        change_user = User.objects.get(username='changeuser')
        change_user.user_permissions.add(get_perm(Report,
            get_permission_codename('change', opts)))

        # login POST dict
        self.changeuser_login = {
            REDIRECT_FIELD_NAME: '/test_admin/admin/',
            'username': 'changeuser',
            'password': 'secret',
        }

    def test_no_standard_modeladmin_urls(self):
        """Admin index views don't break when user's ModelAdmin removes standard urls"""
        self.client.get('/test_admin/admin/')
        r = self.client.post(reverse('admin:login'), self.changeuser_login)
        r = self.client.get('/test_admin/admin/')
        # we shouldn' get an 500 error caused by a NoReverseMatch
        self.assertEqual(r.status_code, 200)
        self.client.get('/test_admin/admin/logout/')


@skipUnlessDBFeature('can_defer_constraint_checks')
@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class AdminViewDeletedObjectsTest(TestCase):
    fixtures = ['admin-views-users.xml', 'deleted-objects.xml']

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_nesting(self):
        """
        Objects should be nested to display the relationships that
        cause them to be scheduled for deletion.
        """
        pattern = re.compile(br"""<li>Plot: <a href=".+/admin_views/plot/1/">World Domination</a>\s*<ul>\s*<li>Plot details: <a href=".+/admin_views/plotdetails/1/">almost finished</a>""")
        response = self.client.get('/test_admin/admin/admin_views/villain/%s/delete/' % quote(1))
        six.assertRegex(self, response.content, pattern)

    def test_cyclic(self):
        """
        Cyclic relationships should still cause each object to only be
        listed once.

        """
        one = """<li>Cyclic one: <a href="/test_admin/admin/admin_views/cyclicone/1/">I am recursive</a>"""
        two = """<li>Cyclic two: <a href="/test_admin/admin/admin_views/cyclictwo/1/">I am recursive too</a>"""
        response = self.client.get('/test_admin/admin/admin_views/cyclicone/%s/delete/' % quote(1))

        self.assertContains(response, one, 1)
        self.assertContains(response, two, 1)

    def test_perms_needed(self):
        self.client.logout()
        delete_user = User.objects.get(username='deleteuser')
        delete_user.user_permissions.add(get_perm(Plot,
            get_permission_codename('delete', Plot._meta)))

        self.assertTrue(self.client.login(username='deleteuser',
                                          password='secret'))

        response = self.client.get('/test_admin/admin/admin_views/plot/%s/delete/' % quote(1))
        self.assertContains(response, "your account doesn't have permission to delete the following types of objects")
        self.assertContains(response, "<li>plot details</li>")

    def test_protected(self):
        q = Question.objects.create(question="Why?")
        a1 = Answer.objects.create(question=q, answer="Because.")
        a2 = Answer.objects.create(question=q, answer="Yes.")

        response = self.client.get("/test_admin/admin/admin_views/question/%s/delete/" % quote(q.pk))
        self.assertContains(response, "would require deleting the following protected related objects")
        self.assertContains(response, '<li>Answer: <a href="/test_admin/admin/admin_views/answer/%s/">Because.</a></li>' % a1.pk)
        self.assertContains(response, '<li>Answer: <a href="/test_admin/admin/admin_views/answer/%s/">Yes.</a></li>' % a2.pk)

    def test_not_registered(self):
        should_contain = """<li>Secret hideout: underground bunker"""
        response = self.client.get('/test_admin/admin/admin_views/villain/%s/delete/' % quote(1))
        self.assertContains(response, should_contain, 1)

    def test_multiple_fkeys_to_same_model(self):
        """
        If a deleted object has two relationships from another model,
        both of those should be followed in looking for related
        objects to delete.

        """
        should_contain = """<li>Plot: <a href="/test_admin/admin/admin_views/plot/1/">World Domination</a>"""
        response = self.client.get('/test_admin/admin/admin_views/villain/%s/delete/' % quote(1))
        self.assertContains(response, should_contain)
        response = self.client.get('/test_admin/admin/admin_views/villain/%s/delete/' % quote(2))
        self.assertContains(response, should_contain)

    def test_multiple_fkeys_to_same_instance(self):
        """
        If a deleted object has two relationships pointing to it from
        another object, the other object should still only be listed
        once.

        """
        should_contain = """<li>Plot: <a href="/test_admin/admin/admin_views/plot/2/">World Peace</a></li>"""
        response = self.client.get('/test_admin/admin/admin_views/villain/%s/delete/' % quote(2))
        self.assertContains(response, should_contain, 1)

    def test_inheritance(self):
        """
        In the case of an inherited model, if either the child or
        parent-model instance is deleted, both instances are listed
        for deletion, as well as any relationships they have.

        """
        should_contain = [
            """<li>Villain: <a href="/test_admin/admin/admin_views/villain/3/">Bob</a>""",
            """<li>Super villain: <a href="/test_admin/admin/admin_views/supervillain/3/">Bob</a>""",
            """<li>Secret hideout: floating castle""",
            """<li>Super secret hideout: super floating castle!"""
        ]
        response = self.client.get('/test_admin/admin/admin_views/villain/%s/delete/' % quote(3))
        for should in should_contain:
            self.assertContains(response, should, 1)
        response = self.client.get('/test_admin/admin/admin_views/supervillain/%s/delete/' % quote(3))
        for should in should_contain:
            self.assertContains(response, should, 1)

    def test_generic_relations(self):
        """
        If a deleted object has GenericForeignKeys pointing to it,
        those objects should be listed for deletion.

        """
        plot = Plot.objects.get(pk=3)
        FunkyTag.objects.create(content_object=plot, name='hott')
        should_contain = """<li>Funky tag: hott"""
        response = self.client.get('/test_admin/admin/admin_views/plot/%s/delete/' % quote(3))
        self.assertContains(response, should_contain)


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class AdminViewStringPrimaryKeyTest(TestCase):
    fixtures = ['admin-views-users.xml', 'string-primary-key.xml']

    def __init__(self, *args):
        super(AdminViewStringPrimaryKeyTest, self).__init__(*args)
        self.pk = """abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ 1234567890 -_.!~*'() ;/?:@&=+$, <>#%" {}|\^[]`"""

    def setUp(self):
        self.client.login(username='super', password='secret')
        content_type_pk = ContentType.objects.get_for_model(ModelWithStringPrimaryKey).pk
        LogEntry.objects.log_action(100, content_type_pk, self.pk, self.pk, 2, change_message='Changed something')

    def tearDown(self):
        self.client.logout()

    def test_get_history_view(self):
        """
        Retrieving the history for an object using urlencoded form of primary
        key should work.
        Refs #12349, #18550.
        """
        response = self.client.get('/test_admin/admin/admin_views/modelwithstringprimarykey/%s/history/' % quote(self.pk))
        self.assertContains(response, escape(self.pk))
        self.assertContains(response, 'Changed something')
        self.assertEqual(response.status_code, 200)

    def test_get_change_view(self):
        "Retrieving the object using urlencoded form of primary key should work"
        response = self.client.get('/test_admin/admin/admin_views/modelwithstringprimarykey/%s/' % quote(self.pk))
        self.assertContains(response, escape(self.pk))
        self.assertEqual(response.status_code, 200)

    def test_changelist_to_changeform_link(self):
        "Link to the changeform of the object in changelist should use reverse() and be quoted -- #18072"
        prefix = '/test_admin/admin/admin_views/modelwithstringprimarykey/'
        response = self.client.get(prefix)
        # this URL now comes through reverse(), thus url quoting and iri_to_uri encoding
        pk_final_url = escape(iri_to_uri(quote(self.pk)))
        should_contain = """<th class="field-__str__"><a href="%s%s/">%s</a></th>""" % (prefix, pk_final_url, escape(self.pk))
        self.assertContains(response, should_contain)

    def test_recentactions_link(self):
        "The link from the recent actions list referring to the changeform of the object should be quoted"
        response = self.client.get('/test_admin/admin/')
        link = reverse('admin:admin_views_modelwithstringprimarykey_change', args=(quote(self.pk),))
        should_contain = """<a href="%s">%s</a>""" % (escape(link), escape(self.pk))
        self.assertContains(response, should_contain)

    def test_recentactions_without_content_type(self):
        "If a LogEntry is missing content_type it will not display it in span tag under the hyperlink."
        response = self.client.get('/test_admin/admin/')
        link = reverse('admin:admin_views_modelwithstringprimarykey_change', args=(quote(self.pk),))
        should_contain = """<a href="%s">%s</a>""" % (escape(link), escape(self.pk))
        self.assertContains(response, should_contain)
        should_contain = "Model with string primary key"  # capitalized in Recent Actions
        self.assertContains(response, should_contain)
        logentry = LogEntry.objects.get(content_type__name__iexact=should_contain)
        # http://code.djangoproject.com/ticket/10275
        # if the log entry doesn't have a content type it should still be
        # possible to view the Recent Actions part
        logentry.content_type = None
        logentry.save()

        counted_presence_before = response.content.count(force_bytes(should_contain))
        response = self.client.get('/test_admin/admin/')
        counted_presence_after = response.content.count(force_bytes(should_contain))
        self.assertEqual(counted_presence_before - 1,
            counted_presence_after)

    def test_logentry_get_admin_url(self):
        "LogEntry.get_admin_url returns a URL to edit the entry's object or None for non-existent (possibly deleted) models"
        log_entry_name = "Model with string primary key"  # capitalized in Recent Actions
        logentry = LogEntry.objects.get(content_type__name__iexact=log_entry_name)
        model = "modelwithstringprimarykey"
        desired_admin_url = "/test_admin/admin/admin_views/%s/%s/" % (model, iri_to_uri(quote(self.pk)))
        self.assertEqual(logentry.get_admin_url(), desired_admin_url)

        logentry.content_type.model = "non-existent"
        self.assertEqual(logentry.get_admin_url(), None)

    def test_deleteconfirmation_link(self):
        "The link from the delete confirmation page referring back to the changeform of the object should be quoted"
        response = self.client.get('/test_admin/admin/admin_views/modelwithstringprimarykey/%s/delete/' % quote(self.pk))
        # this URL now comes through reverse(), thus url quoting and iri_to_uri encoding
        should_contain = """/%s/">%s</a>""" % (escape(iri_to_uri(quote(self.pk))), escape(self.pk))
        self.assertContains(response, should_contain)

    def test_url_conflicts_with_add(self):
        "A model with a primary key that ends with add should be visible"
        add_model = ModelWithStringPrimaryKey(pk="i have something to add")
        add_model.save()
        response = self.client.get('/test_admin/admin/admin_views/modelwithstringprimarykey/%s/' % quote(add_model.pk))
        should_contain = """<h1>Change model with string primary key</h1>"""
        self.assertContains(response, should_contain)

    def test_url_conflicts_with_delete(self):
        "A model with a primary key that ends with delete should be visible"
        delete_model = ModelWithStringPrimaryKey(pk="delete")
        delete_model.save()
        response = self.client.get('/test_admin/admin/admin_views/modelwithstringprimarykey/%s/' % quote(delete_model.pk))
        should_contain = """<h1>Change model with string primary key</h1>"""
        self.assertContains(response, should_contain)

    def test_url_conflicts_with_history(self):
        "A model with a primary key that ends with history should be visible"
        history_model = ModelWithStringPrimaryKey(pk="history")
        history_model.save()
        response = self.client.get('/test_admin/admin/admin_views/modelwithstringprimarykey/%s/' % quote(history_model.pk))
        should_contain = """<h1>Change model with string primary key</h1>"""
        self.assertContains(response, should_contain)

    def test_shortcut_view_with_escaping(self):
        "'View on site should' work properly with char fields"
        model = ModelWithStringPrimaryKey(pk='abc_123')
        model.save()
        response = self.client.get('/test_admin/admin/admin_views/modelwithstringprimarykey/%s/' % quote(model.pk))
        should_contain = '/%s/" class="viewsitelink">' % model.pk
        self.assertContains(response, should_contain)

    def test_change_view_history_link(self):
        """Object history button link should work and contain the pk value quoted."""
        url = reverse('admin:%s_modelwithstringprimarykey_change' %
            ModelWithStringPrimaryKey._meta.app_label,
            args=(quote(self.pk),))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        expected_link = reverse('admin:%s_modelwithstringprimarykey_history' %
            ModelWithStringPrimaryKey._meta.app_label,
            args=(quote(self.pk),))
        self.assertContains(response, '<a href="%s" class="historylink"' % expected_link)

    def test_redirect_on_add_view_continue_button(self):
        """As soon as an object is added using "Save and continue editing"
        button, the user should be redirected to the object's change_view.

        In case primary key is a string containing some special characters
        like slash or underscore, these characters must be escaped (see #22266)
        """
        response = self.client.post(
            '/test_admin/admin/admin_views/modelwithstringprimarykey/add/',
            {
                'string_pk': '123/history',
                "_continue": "1",  # Save and continue editing
            }
        )

        self.assertEqual(response.status_code, 302)  # temporary redirect
        self.assertEqual(
            response['location'],
            (
                'http://testserver/test_admin/admin/admin_views/'
                'modelwithstringprimarykey/123_2Fhistory/'  # PK is quoted
            )
        )


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class SecureViewTests(TestCase):
    """
    Test behavior of a view protected by the staff_member_required decorator.
    """
    fixtures = ['admin-views-users.xml']

    def tearDown(self):
        self.client.logout()

    def test_secure_view_shows_login_if_not_logged_in(self):
        """
        Ensure that we see the admin login form.
        """
        secure_url = '/test_admin/admin/secure-view/'
        response = self.client.get(secure_url)
        self.assertRedirects(response, '%s?next=%s' % (reverse('admin:login'), secure_url))
        response = self.client.get(secure_url, follow=True)
        self.assertTemplateUsed(response, 'admin/login.html')
        self.assertEqual(response.context[REDIRECT_FIELD_NAME], secure_url)


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class AdminViewUnicodeTest(TestCase):
    fixtures = ['admin-views-unicode.xml']

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_unicode_edit(self):
        """
        A test to ensure that POST on edit_view handles non-ASCII characters.
        """
        post_data = {
            "name": "Test lærdommer",
            # inline data
            "chapter_set-TOTAL_FORMS": "6",
            "chapter_set-INITIAL_FORMS": "3",
            "chapter_set-MAX_NUM_FORMS": "0",
            "chapter_set-0-id": "1",
            "chapter_set-0-title": "Norske bostaver æøå skaper problemer",
            "chapter_set-0-content": "&lt;p&gt;Svært frustrerende med UnicodeDecodeError&lt;/p&gt;",
            "chapter_set-1-id": "2",
            "chapter_set-1-title": "Kjærlighet.",
            "chapter_set-1-content": "&lt;p&gt;La kjærligheten til de lidende seire.&lt;/p&gt;",
            "chapter_set-2-id": "3",
            "chapter_set-2-title": "Need a title.",
            "chapter_set-2-content": "&lt;p&gt;Newest content&lt;/p&gt;",
            "chapter_set-3-id": "",
            "chapter_set-3-title": "",
            "chapter_set-3-content": "",
            "chapter_set-4-id": "",
            "chapter_set-4-title": "",
            "chapter_set-4-content": "",
            "chapter_set-5-id": "",
            "chapter_set-5-title": "",
            "chapter_set-5-content": "",
        }

        response = self.client.post('/test_admin/admin/admin_views/book/1/', post_data)
        self.assertEqual(response.status_code, 302)  # redirect somewhere

    def test_unicode_delete(self):
        """
        Ensure that the delete_view handles non-ASCII characters
        """
        delete_dict = {'post': 'yes'}
        response = self.client.get('/test_admin/admin/admin_views/book/1/delete/')
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/test_admin/admin/admin_views/book/1/delete/', delete_dict)
        self.assertRedirects(response, '/test_admin/admin/admin_views/book/')


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class AdminViewListEditable(TestCase):
    fixtures = ['admin-views-users.xml', 'admin-views-person.xml']

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_inheritance(self):
        Podcast.objects.create(name="This Week in Django",
            release_date=datetime.date.today())
        response = self.client.get('/test_admin/admin/admin_views/podcast/')
        self.assertEqual(response.status_code, 200)

    def test_inheritance_2(self):
        Vodcast.objects.create(name="This Week in Django", released=True)
        response = self.client.get('/test_admin/admin/admin_views/vodcast/')
        self.assertEqual(response.status_code, 200)

    def test_custom_pk(self):
        Language.objects.create(iso='en', name='English', english_name='English')
        response = self.client.get('/test_admin/admin/admin_views/language/')
        self.assertEqual(response.status_code, 200)

    def test_changelist_input_html(self):
        response = self.client.get('/test_admin/admin/admin_views/person/')
        # 2 inputs per object(the field and the hidden id field) = 6
        # 4 management hidden fields = 4
        # 4 action inputs (3 regular checkboxes, 1 checkbox to select all)
        # main form submit button = 1
        # search field and search submit button = 2
        # CSRF field = 1
        # field to track 'select all' across paginated views = 1
        # 6 + 4 + 4 + 1 + 2 + 1 + 1 = 19 inputs
        self.assertContains(response, "<input", count=19)
        # 1 select per object = 3 selects
        self.assertContains(response, "<select", count=4)

    def test_post_messages(self):
        # Ticket 12707: Saving inline editable should not show admin
        # action warnings
        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MAX_NUM_FORMS": "0",

            "form-0-gender": "1",
            "form-0-id": "1",

            "form-1-gender": "2",
            "form-1-id": "2",

            "form-2-alive": "checked",
            "form-2-gender": "1",
            "form-2-id": "3",

            "_save": "Save",
        }
        response = self.client.post('/test_admin/admin/admin_views/person/',
                                    data, follow=True)
        self.assertEqual(len(response.context['messages']), 1)

    def test_post_submission(self):
        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MAX_NUM_FORMS": "0",

            "form-0-gender": "1",
            "form-0-id": "1",

            "form-1-gender": "2",
            "form-1-id": "2",

            "form-2-alive": "checked",
            "form-2-gender": "1",
            "form-2-id": "3",

            "_save": "Save",
        }
        self.client.post('/test_admin/admin/admin_views/person/', data)

        self.assertEqual(Person.objects.get(name="John Mauchly").alive, False)
        self.assertEqual(Person.objects.get(name="Grace Hopper").gender, 2)

        # test a filtered page
        data = {
            "form-TOTAL_FORMS": "2",
            "form-INITIAL_FORMS": "2",
            "form-MAX_NUM_FORMS": "0",

            "form-0-id": "1",
            "form-0-gender": "1",
            "form-0-alive": "checked",

            "form-1-id": "3",
            "form-1-gender": "1",
            "form-1-alive": "checked",

            "_save": "Save",
        }
        self.client.post('/test_admin/admin/admin_views/person/?gender__exact=1', data)

        self.assertEqual(Person.objects.get(name="John Mauchly").alive, True)

        # test a searched page
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "0",

            "form-0-id": "1",
            "form-0-gender": "1",

            "_save": "Save",
        }
        self.client.post('/test_admin/admin/admin_views/person/?q=john', data)

        self.assertEqual(Person.objects.get(name="John Mauchly").alive, False)

    def test_non_field_errors(self):
        ''' Ensure that non field errors are displayed for each of the
            forms in the changelist's formset. Refs #13126.
        '''
        fd1 = FoodDelivery.objects.create(reference='123', driver='bill', restaurant='thai')
        fd2 = FoodDelivery.objects.create(reference='456', driver='bill', restaurant='india')
        fd3 = FoodDelivery.objects.create(reference='789', driver='bill', restaurant='pizza')

        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MAX_NUM_FORMS": "0",

            "form-0-id": str(fd1.id),
            "form-0-reference": "123",
            "form-0-driver": "bill",
            "form-0-restaurant": "thai",

            # Same data as above: Forbidden because of unique_together!
            "form-1-id": str(fd2.id),
            "form-1-reference": "456",
            "form-1-driver": "bill",
            "form-1-restaurant": "thai",

            "form-2-id": str(fd3.id),
            "form-2-reference": "789",
            "form-2-driver": "bill",
            "form-2-restaurant": "pizza",

            "_save": "Save",
        }
        response = self.client.post('/test_admin/admin/admin_views/fooddelivery/', data)
        self.assertContains(response, '<tr><td colspan="4"><ul class="errorlist nonfield"><li>Food delivery with this Driver and Restaurant already exists.</li></ul></td></tr>', 1, html=True)

        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MAX_NUM_FORMS": "0",

            "form-0-id": str(fd1.id),
            "form-0-reference": "123",
            "form-0-driver": "bill",
            "form-0-restaurant": "thai",

            # Same data as above: Forbidden because of unique_together!
            "form-1-id": str(fd2.id),
            "form-1-reference": "456",
            "form-1-driver": "bill",
            "form-1-restaurant": "thai",

            # Same data also.
            "form-2-id": str(fd3.id),
            "form-2-reference": "789",
            "form-2-driver": "bill",
            "form-2-restaurant": "thai",

            "_save": "Save",
        }
        response = self.client.post('/test_admin/admin/admin_views/fooddelivery/', data)
        self.assertContains(response, '<tr><td colspan="4"><ul class="errorlist nonfield"><li>Food delivery with this Driver and Restaurant already exists.</li></ul></td></tr>', 2, html=True)

    def test_non_form_errors(self):
        # test if non-form errors are handled; ticket #12716
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "0",

            "form-0-id": "2",
            "form-0-alive": "1",
            "form-0-gender": "2",

            # Ensure that the form processing understands this as a list_editable "Save"
            # and not an action "Go".
            "_save": "Save",
        }
        response = self.client.post('/test_admin/admin/admin_views/person/', data)
        self.assertContains(response, "Grace is not a Zombie")

    def test_non_form_errors_is_errorlist(self):
        # test if non-form errors are correctly handled; ticket #12878
        data = {
            "form-TOTAL_FORMS": "1",
            "form-INITIAL_FORMS": "1",
            "form-MAX_NUM_FORMS": "0",

            "form-0-id": "2",
            "form-0-alive": "1",
            "form-0-gender": "2",

            "_save": "Save",
        }
        response = self.client.post('/test_admin/admin/admin_views/person/', data)
        non_form_errors = response.context['cl'].formset.non_form_errors()
        self.assertIsInstance(non_form_errors, ErrorList)
        self.assertEqual(str(non_form_errors), str(ErrorList(["Grace is not a Zombie"])))

    def test_list_editable_ordering(self):
        collector = Collector.objects.create(id=1, name="Frederick Clegg")

        Category.objects.create(id=1, order=1, collector=collector)
        Category.objects.create(id=2, order=2, collector=collector)
        Category.objects.create(id=3, order=0, collector=collector)
        Category.objects.create(id=4, order=0, collector=collector)

        # NB: The order values must be changed so that the items are reordered.
        data = {
            "form-TOTAL_FORMS": "4",
            "form-INITIAL_FORMS": "4",
            "form-MAX_NUM_FORMS": "0",

            "form-0-order": "14",
            "form-0-id": "1",
            "form-0-collector": "1",

            "form-1-order": "13",
            "form-1-id": "2",
            "form-1-collector": "1",

            "form-2-order": "1",
            "form-2-id": "3",
            "form-2-collector": "1",

            "form-3-order": "0",
            "form-3-id": "4",
            "form-3-collector": "1",

            # Ensure that the form processing understands this as a list_editable "Save"
            # and not an action "Go".
            "_save": "Save",
        }
        response = self.client.post('/test_admin/admin/admin_views/category/', data)
        # Successful post will redirect
        self.assertEqual(response.status_code, 302)

        # Check that the order values have been applied to the right objects
        self.assertEqual(Category.objects.get(id=1).order, 14)
        self.assertEqual(Category.objects.get(id=2).order, 13)
        self.assertEqual(Category.objects.get(id=3).order, 1)
        self.assertEqual(Category.objects.get(id=4).order, 0)

    def test_list_editable_pagination(self):
        """
        Ensure that pagination works for list_editable items.
        Refs #16819.
        """
        UnorderedObject.objects.create(id=1, name='Unordered object #1')
        UnorderedObject.objects.create(id=2, name='Unordered object #2')
        UnorderedObject.objects.create(id=3, name='Unordered object #3')
        response = self.client.get('/test_admin/admin/admin_views/unorderedobject/')
        self.assertContains(response, 'Unordered object #3')
        self.assertContains(response, 'Unordered object #2')
        self.assertNotContains(response, 'Unordered object #1')
        response = self.client.get('/test_admin/admin/admin_views/unorderedobject/?p=1')
        self.assertNotContains(response, 'Unordered object #3')
        self.assertNotContains(response, 'Unordered object #2')
        self.assertContains(response, 'Unordered object #1')

    def test_list_editable_action_submit(self):
        # List editable changes should not be executed if the action "Go" button is
        # used to submit the form.
        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MAX_NUM_FORMS": "0",

            "form-0-gender": "1",
            "form-0-id": "1",

            "form-1-gender": "2",
            "form-1-id": "2",

            "form-2-alive": "checked",
            "form-2-gender": "1",
            "form-2-id": "3",

            "index": "0",
            "_selected_action": ['3'],
            "action": ['', 'delete_selected'],
        }
        self.client.post('/test_admin/admin/admin_views/person/', data)

        self.assertEqual(Person.objects.get(name="John Mauchly").alive, True)
        self.assertEqual(Person.objects.get(name="Grace Hopper").gender, 1)

    def test_list_editable_action_choices(self):
        # List editable changes should be executed if the "Save" button is
        # used to submit the form - any action choices should be ignored.
        data = {
            "form-TOTAL_FORMS": "3",
            "form-INITIAL_FORMS": "3",
            "form-MAX_NUM_FORMS": "0",

            "form-0-gender": "1",
            "form-0-id": "1",

            "form-1-gender": "2",
            "form-1-id": "2",

            "form-2-alive": "checked",
            "form-2-gender": "1",
            "form-2-id": "3",

            "_save": "Save",
            "_selected_action": ['1'],
            "action": ['', 'delete_selected'],
        }
        self.client.post('/test_admin/admin/admin_views/person/', data)

        self.assertEqual(Person.objects.get(name="John Mauchly").alive, False)
        self.assertEqual(Person.objects.get(name="Grace Hopper").gender, 2)

    def test_list_editable_popup(self):
        """
        Fields should not be list-editable in popups.
        """
        response = self.client.get('/test_admin/admin/admin_views/person/')
        self.assertNotEqual(response.context['cl'].list_editable, ())
        response = self.client.get('/test_admin/admin/admin_views/person/?%s' % IS_POPUP_VAR)
        self.assertEqual(response.context['cl'].list_editable, ())

    def test_pk_hidden_fields(self):
        """ Ensure that hidden pk fields aren't displayed in the table body and
            that their corresponding human-readable value is displayed instead.
            Note that the hidden pk fields are in fact be displayed but
            separately (not in the table), and only once.
            Refs #12475.
        """
        story1 = Story.objects.create(title='The adventures of Guido', content='Once upon a time in Djangoland...')
        story2 = Story.objects.create(title='Crouching Tiger, Hidden Python', content='The Python was sneaking into...')
        response = self.client.get('/test_admin/admin/admin_views/story/')
        self.assertContains(response, 'id="id_form-0-id"', 1)  # Only one hidden field, in a separate place than the table.
        self.assertContains(response, 'id="id_form-1-id"', 1)
        self.assertContains(response, '<div class="hiddenfields">\n<input type="hidden" name="form-0-id" value="%d" id="id_form-0-id" /><input type="hidden" name="form-1-id" value="%d" id="id_form-1-id" />\n</div>' % (story2.id, story1.id), html=True)
        self.assertContains(response, '<td class="field-id">%d</td>' % story1.id, 1)
        self.assertContains(response, '<td class="field-id">%d</td>' % story2.id, 1)

    def test_pk_hidden_fields_with_list_display_links(self):
        """ Similarly as test_pk_hidden_fields, but when the hidden pk fields are
            referenced in list_display_links.
            Refs #12475.
        """
        story1 = OtherStory.objects.create(title='The adventures of Guido', content='Once upon a time in Djangoland...')
        story2 = OtherStory.objects.create(title='Crouching Tiger, Hidden Python', content='The Python was sneaking into...')
        link1 = reverse('admin:admin_views_otherstory_change', args=(story1.pk,))
        link2 = reverse('admin:admin_views_otherstory_change', args=(story2.pk,))
        response = self.client.get('/test_admin/admin/admin_views/otherstory/')
        self.assertContains(response, 'id="id_form-0-id"', 1)  # Only one hidden field, in a separate place than the table.
        self.assertContains(response, 'id="id_form-1-id"', 1)
        self.assertContains(response, '<div class="hiddenfields">\n<input type="hidden" name="form-0-id" value="%d" id="id_form-0-id" /><input type="hidden" name="form-1-id" value="%d" id="id_form-1-id" />\n</div>' % (story2.id, story1.id), html=True)
        self.assertContains(response, '<th class="field-id"><a href="%s">%d</a></th>' % (link1, story1.id), 1)
        self.assertContains(response, '<th class="field-id"><a href="%s">%d</a></th>' % (link2, story2.id), 1)


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class AdminSearchTest(TestCase):
    fixtures = ['admin-views-users', 'multiple-child-classes',
                'admin-views-person']

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_search_on_sibling_models(self):
        "Check that a search that mentions sibling models"
        response = self.client.get('/test_admin/admin/admin_views/recommendation/?q=bar')
        # confirm the search returned 1 object
        self.assertContains(response, "\n1 recommendation\n")

    def test_with_fk_to_field(self):
        """Ensure that the to_field GET parameter is preserved when a search
        is performed. Refs #10918.
        """
        from django.contrib.admin.views.main import TO_FIELD_VAR
        response = self.client.get('/test_admin/admin/auth/user/?q=joe&%s=username' % TO_FIELD_VAR)
        self.assertContains(response, "\n1 user\n")
        self.assertContains(response, '<input type="hidden" name="_to_field" value="username"/>', html=True)

    def test_exact_matches(self):
        response = self.client.get('/test_admin/admin/admin_views/recommendation/?q=bar')
        # confirm the search returned one object
        self.assertContains(response, "\n1 recommendation\n")

        response = self.client.get('/test_admin/admin/admin_views/recommendation/?q=ba')
        # confirm the search returned zero objects
        self.assertContains(response, "\n0 recommendations\n")

    def test_beginning_matches(self):
        response = self.client.get('/test_admin/admin/admin_views/person/?q=Gui')
        # confirm the search returned one object
        self.assertContains(response, "\n1 person\n")
        self.assertContains(response, "Guido")

        response = self.client.get('/test_admin/admin/admin_views/person/?q=uido')
        # confirm the search returned zero objects
        self.assertContains(response, "\n0 persons\n")
        self.assertNotContains(response, "Guido")

    def test_pluggable_search(self):
        PluggableSearchPerson.objects.create(name="Bob", age=10)
        PluggableSearchPerson.objects.create(name="Amy", age=20)

        response = self.client.get('/test_admin/admin/admin_views/pluggablesearchperson/?q=Bob')
        # confirm the search returned one object
        self.assertContains(response, "\n1 pluggable search person\n")
        self.assertContains(response, "Bob")

        response = self.client.get('/test_admin/admin/admin_views/pluggablesearchperson/?q=20')
        # confirm the search returned one object
        self.assertContains(response, "\n1 pluggable search person\n")
        self.assertContains(response, "Amy")

    def test_reset_link(self):
        """
        Test presence of reset link in search bar ("1 result (_x total_)").
        """
        response = self.client.get('/test_admin/admin/admin_views/person/?q=Gui')
        self.assertContains(response,
            """<span class="small quiet">1 result (<a href="?">3 total</a>)</span>""",
            html=True)


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class AdminInheritedInlinesTest(TestCase):
    fixtures = ['admin-views-users.xml']

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_inline(self):
        "Ensure that inline models which inherit from a common parent are correctly handled by admin."

        foo_user = "foo username"
        bar_user = "bar username"

        name_re = re.compile(b'name="(.*?)"')

        # test the add case
        response = self.client.get('/test_admin/admin/admin_views/persona/add/')
        names = name_re.findall(response.content)
        # make sure we have no duplicate HTML names
        self.assertEqual(len(names), len(set(names)))

        # test the add case
        post_data = {
            "name": "Test Name",
            # inline data
            "accounts-TOTAL_FORMS": "1",
            "accounts-INITIAL_FORMS": "0",
            "accounts-MAX_NUM_FORMS": "0",
            "accounts-0-username": foo_user,
            "accounts-2-TOTAL_FORMS": "1",
            "accounts-2-INITIAL_FORMS": "0",
            "accounts-2-MAX_NUM_FORMS": "0",
            "accounts-2-0-username": bar_user,
        }

        response = self.client.post('/test_admin/admin/admin_views/persona/add/', post_data)
        self.assertEqual(response.status_code, 302)  # redirect somewhere
        self.assertEqual(Persona.objects.count(), 1)
        self.assertEqual(FooAccount.objects.count(), 1)
        self.assertEqual(BarAccount.objects.count(), 1)
        self.assertEqual(FooAccount.objects.all()[0].username, foo_user)
        self.assertEqual(BarAccount.objects.all()[0].username, bar_user)
        self.assertEqual(Persona.objects.all()[0].accounts.count(), 2)

        persona_id = Persona.objects.all()[0].id
        foo_id = FooAccount.objects.all()[0].id
        bar_id = BarAccount.objects.all()[0].id

        # test the edit case

        response = self.client.get('/test_admin/admin/admin_views/persona/%d/' % persona_id)
        names = name_re.findall(response.content)
        # make sure we have no duplicate HTML names
        self.assertEqual(len(names), len(set(names)))

        post_data = {
            "name": "Test Name",

            "accounts-TOTAL_FORMS": "2",
            "accounts-INITIAL_FORMS": "1",
            "accounts-MAX_NUM_FORMS": "0",

            "accounts-0-username": "%s-1" % foo_user,
            "accounts-0-account_ptr": str(foo_id),
            "accounts-0-persona": str(persona_id),

            "accounts-2-TOTAL_FORMS": "2",
            "accounts-2-INITIAL_FORMS": "1",
            "accounts-2-MAX_NUM_FORMS": "0",

            "accounts-2-0-username": "%s-1" % bar_user,
            "accounts-2-0-account_ptr": str(bar_id),
            "accounts-2-0-persona": str(persona_id),
        }
        response = self.client.post('/test_admin/admin/admin_views/persona/%d/' % persona_id, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Persona.objects.count(), 1)
        self.assertEqual(FooAccount.objects.count(), 1)
        self.assertEqual(BarAccount.objects.count(), 1)
        self.assertEqual(FooAccount.objects.all()[0].username, "%s-1" % foo_user)
        self.assertEqual(BarAccount.objects.all()[0].username, "%s-1" % bar_user)
        self.assertEqual(Persona.objects.all()[0].accounts.count(), 2)


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class AdminActionsTest(TestCase):
    fixtures = ['admin-views-users.xml', 'admin-views-actions.xml']

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_model_admin_custom_action(self):
        "Tests a custom action defined in a ModelAdmin method"
        action_data = {
            ACTION_CHECKBOX_NAME: [1],
            'action': 'mail_admin',
            'index': 0,
        }
        self.client.post('/test_admin/admin/admin_views/subscriber/', action_data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Greetings from a ModelAdmin action')

    def test_model_admin_default_delete_action(self):
        "Tests the default delete action defined as a ModelAdmin method"
        action_data = {
            ACTION_CHECKBOX_NAME: [1, 2],
            'action': 'delete_selected',
            'index': 0,
        }
        delete_confirmation_data = {
            ACTION_CHECKBOX_NAME: [1, 2],
            'action': 'delete_selected',
            'post': 'yes',
        }
        confirmation = self.client.post('/test_admin/admin/admin_views/subscriber/', action_data)
        self.assertIsInstance(confirmation, TemplateResponse)
        self.assertContains(confirmation, "Are you sure you want to delete the selected subscribers?")
        self.assertContains(confirmation, ACTION_CHECKBOX_NAME, count=2)
        self.client.post('/test_admin/admin/admin_views/subscriber/', delete_confirmation_data)
        self.assertEqual(Subscriber.objects.count(), 0)

    @override_settings(USE_THOUSAND_SEPARATOR=True, USE_L10N=True)
    def test_non_localized_pk(self):
        """If USE_THOUSAND_SEPARATOR is set, make sure that the ids for
        the objects selected for deletion are rendered without separators.
        Refs #14895.
        """
        subscriber = Subscriber.objects.get(id=1)
        subscriber.id = 9999
        subscriber.save()
        action_data = {
            ACTION_CHECKBOX_NAME: [9999, 2],
            'action': 'delete_selected',
            'index': 0,
        }
        response = self.client.post('/test_admin/admin/admin_views/subscriber/', action_data)
        self.assertTemplateUsed(response, 'admin/delete_selected_confirmation.html')
        self.assertContains(response, 'value="9999"')  # Instead of 9,999
        self.assertContains(response, 'value="2"')

    def test_model_admin_default_delete_action_protected(self):
        """
        Tests the default delete action defined as a ModelAdmin method in the
        case where some related objects are protected from deletion.
        """
        q1 = Question.objects.create(question="Why?")
        a1 = Answer.objects.create(question=q1, answer="Because.")
        a2 = Answer.objects.create(question=q1, answer="Yes.")
        q2 = Question.objects.create(question="Wherefore?")

        action_data = {
            ACTION_CHECKBOX_NAME: [q1.pk, q2.pk],
            'action': 'delete_selected',
            'index': 0,
        }

        response = self.client.post("/test_admin/admin/admin_views/question/", action_data)

        self.assertContains(response, "would require deleting the following protected related objects")
        self.assertContains(response, '<li>Answer: <a href="/test_admin/admin/admin_views/answer/%s/">Because.</a></li>' % a1.pk, html=True)
        self.assertContains(response, '<li>Answer: <a href="/test_admin/admin/admin_views/answer/%s/">Yes.</a></li>' % a2.pk, html=True)

    def test_model_admin_default_delete_action_no_change_url(self):
        """
        Default delete action shouldn't break if a user's ModelAdmin removes the url for change_view.

        Regression test for #20640
        """
        obj = UnchangeableObject.objects.create()
        action_data = {
            ACTION_CHECKBOX_NAME: obj.pk,
            "action": "delete_selected",
            "index": "0",
        }
        response = self.client.post('/test_admin/admin/admin_views/unchangeableobject/', action_data)
        # No 500 caused by NoReverseMatch
        self.assertEqual(response.status_code, 200)
        # The page shouldn't display a link to the nonexistent change page
        self.assertContains(response, "<li>Unchangeable object: UnchangeableObject object</li>", 1, html=True)

    def test_custom_function_mail_action(self):
        "Tests a custom action defined in a function"
        action_data = {
            ACTION_CHECKBOX_NAME: [1],
            'action': 'external_mail',
            'index': 0,
        }
        self.client.post('/test_admin/admin/admin_views/externalsubscriber/', action_data)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Greetings from a function action')

    def test_custom_function_action_with_redirect(self):
        "Tests a custom action defined in a function"
        action_data = {
            ACTION_CHECKBOX_NAME: [1],
            'action': 'redirect_to',
            'index': 0,
        }
        response = self.client.post('/test_admin/admin/admin_views/externalsubscriber/', action_data)
        self.assertEqual(response.status_code, 302)

    def test_default_redirect(self):
        """
        Test that actions which don't return an HttpResponse are redirected to
        the same page, retaining the querystring (which may contain changelist
        information).
        """
        action_data = {
            ACTION_CHECKBOX_NAME: [1],
            'action': 'external_mail',
            'index': 0,
        }
        url = '/test_admin/admin/admin_views/externalsubscriber/?o=1'
        response = self.client.post(url, action_data)
        self.assertRedirects(response, url)

    def test_custom_function_action_streaming_response(self):
        """Tests a custom action that returns a StreamingHttpResponse."""
        action_data = {
            ACTION_CHECKBOX_NAME: [1],
            'action': 'download',
            'index': 0,
        }
        response = self.client.post('/test_admin/admin/admin_views/externalsubscriber/', action_data)
        content = b''.join(response.streaming_content)
        self.assertEqual(content, b'This is the content of the file')
        self.assertEqual(response.status_code, 200)

    def test_custom_function_action_no_perm_response(self):
        """Tests a custom action that returns an HttpResponse with 403 code."""
        action_data = {
            ACTION_CHECKBOX_NAME: [1],
            'action': 'no_perm',
            'index': 0,
        }
        response = self.client.post('/test_admin/admin/admin_views/externalsubscriber/', action_data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.content, b'No permission to perform this action')

    def test_actions_ordering(self):
        """
        Ensure that actions are ordered as expected.
        Refs #15964.
        """
        response = self.client.get('/test_admin/admin/admin_views/externalsubscriber/')
        self.assertContains(response, '''<label>Action: <select name="action">
<option value="" selected="selected">---------</option>
<option value="delete_selected">Delete selected external
subscribers</option>
<option value="redirect_to">Redirect to (Awesome action)</option>
<option value="external_mail">External mail (Another awesome
action)</option>
<option value="download">Download subscription</option>
<option value="no_perm">No permission to run</option>
</select>''', html=True)

    def test_model_without_action(self):
        "Tests a ModelAdmin without any action"
        response = self.client.get('/test_admin/admin/admin_views/oldsubscriber/')
        self.assertEqual(response.context["action_form"], None)
        self.assertNotContains(response, '<input type="checkbox" class="action-select"',
            msg_prefix="Found an unexpected action toggle checkboxbox in response")
        self.assertNotContains(response, '<input type="checkbox" class="action-select"')

    def test_model_without_action_still_has_jquery(self):
        "Tests that a ModelAdmin without any actions still gets jQuery included in page"
        response = self.client.get('/test_admin/admin/admin_views/oldsubscriber/')
        self.assertEqual(response.context["action_form"], None)
        self.assertContains(response, 'jquery.min.js',
            msg_prefix="jQuery missing from admin pages for model with no admin actions")

    def test_action_column_class(self):
        "Tests that the checkbox column class is present in the response"
        response = self.client.get('/test_admin/admin/admin_views/subscriber/')
        self.assertNotEqual(response.context["action_form"], None)
        self.assertContains(response, 'action-checkbox-column')

    def test_multiple_actions_form(self):
        """
        Test that actions come from the form whose submit button was pressed (#10618).
        """
        action_data = {
            ACTION_CHECKBOX_NAME: [1],
            # Two different actions selected on the two forms...
            'action': ['external_mail', 'delete_selected'],
            # ...but we clicked "go" on the top form.
            'index': 0
        }
        self.client.post('/test_admin/admin/admin_views/externalsubscriber/', action_data)

        # Send mail, don't delete.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, 'Greetings from a function action')

    def test_user_message_on_none_selected(self):
        """
        User should see a warning when 'Go' is pressed and no items are selected.
        """
        action_data = {
            ACTION_CHECKBOX_NAME: [],
            'action': 'delete_selected',
            'index': 0,
        }
        response = self.client.post('/test_admin/admin/admin_views/subscriber/', action_data)
        msg = """Items must be selected in order to perform actions on them. No items have been changed."""
        self.assertContains(response, msg)
        self.assertEqual(Subscriber.objects.count(), 2)

    def test_user_message_on_no_action(self):
        """
        User should see a warning when 'Go' is pressed and no action is selected.
        """
        action_data = {
            ACTION_CHECKBOX_NAME: [1, 2],
            'action': '',
            'index': 0,
        }
        response = self.client.post('/test_admin/admin/admin_views/subscriber/', action_data)
        msg = """No action selected."""
        self.assertContains(response, msg)
        self.assertEqual(Subscriber.objects.count(), 2)

    def test_selection_counter(self):
        """
        Check if the selection counter is there.
        """
        response = self.client.get('/test_admin/admin/admin_views/subscriber/')
        self.assertContains(response, '0 of 2 selected')

    def test_popup_actions(self):
        """ Actions should not be shown in popups. """
        response = self.client.get('/test_admin/admin/admin_views/subscriber/')
        self.assertNotEqual(response.context["action_form"], None)
        response = self.client.get(
            '/test_admin/admin/admin_views/subscriber/?%s' % IS_POPUP_VAR)
        self.assertEqual(response.context["action_form"], None)

    def test_popup_template_response(self):
        """
        Success on popups shall be rendered from template in order to allow
        easy customization.
        """
        response = self.client.post(
            '/test_admin/admin/admin_views/actor/add/?%s=1' % IS_POPUP_VAR,
            {'name': 'Troy McClure', 'age': '55', IS_POPUP_VAR: '1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.template_name, 'admin/popup_response.html')

@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class SeleniumAdminViewsFirefoxTests(AdminSeleniumWebDriverTestCase):

    available_apps = ['admin_views'] + AdminSeleniumWebDriverTestCase.available_apps
    fixtures = ['admin-views-users.xml']
    webdriver_class = 'selenium.webdriver.firefox.webdriver.WebDriver'

    def test_prepopulated_fields(self):
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
        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-0-pubdate').send_keys('2011-12-17')
        self.get_select_option('#id_relatedprepopulated_set-0-status', 'option one').click()
        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-0-name').send_keys(' here is a sŤāÇkeð   inline !  ')
        slug1 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-0-slug1').get_attribute('value')
        slug2 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-0-slug2').get_attribute('value')
        self.assertEqual(slug1, 'here-stacked-inline-2011-12-17')
        self.assertEqual(slug2, 'option-one-here-stacked-inline')

        # Add an inline
        self.selenium.find_elements_by_link_text('Add another Related prepopulated')[0].click()
        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-1-pubdate').send_keys('1999-01-25')
        self.get_select_option('#id_relatedprepopulated_set-1-status', 'option two').click()
        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-1-name').send_keys(' now you haVe anöther   sŤāÇkeð  inline with a very ... loooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooog text... ')
        slug1 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-1-slug1').get_attribute('value')
        slug2 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-1-slug2').get_attribute('value')
        self.assertEqual(slug1, 'now-you-have-another-stacked-inline-very-loooooooo')  # 50 characters maximum for slug1 field
        self.assertEqual(slug2, 'option-two-now-you-have-another-stacked-inline-very-looooooo')  # 60 characters maximum for slug2 field

        # Tabular inlines ----------------------------------------------------
        # Initial inline
        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-0-pubdate').send_keys('1234-12-07')
        self.get_select_option('#id_relatedprepopulated_set-2-0-status', 'option two').click()
        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-0-name').send_keys('And now, with a tÃbűlaŘ inline !!!')
        slug1 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-0-slug1').get_attribute('value')
        slug2 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-0-slug2').get_attribute('value')
        self.assertEqual(slug1, 'and-now-tabular-inline-1234-12-07')
        self.assertEqual(slug2, 'option-two-and-now-tabular-inline')

        # Add an inline
        self.selenium.find_elements_by_link_text('Add another Related prepopulated')[1].click()
        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-1-pubdate').send_keys('1981-08-22')
        self.get_select_option('#id_relatedprepopulated_set-2-1-status', 'option one').click()
        self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-1-name').send_keys('a tÃbűlaŘ inline with ignored ;"&*^\%$#@-/`~ characters')
        slug1 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-1-slug1').get_attribute('value')
        slug2 = self.selenium.find_element_by_css_selector('#id_relatedprepopulated_set-2-1-slug2').get_attribute('value')
        self.assertEqual(slug1, 'tabular-inline-ignored-characters-1981-08-22')
        self.assertEqual(slug2, 'option-one-tabular-inline-ignored-characters')

        # Save and check that everything is properly stored in the database
        self.selenium.find_element_by_xpath('//input[@value="Save"]').click()
        self.wait_page_loaded()
        self.assertEqual(MainPrepopulated.objects.all().count(), 1)
        MainPrepopulated.objects.get(
            name=' this is the mAin nÀMë and it\'s awεšome',
            pubdate='2012-02-18',
            status='option two',
            slug1='main-name-and-its-awesome-2012-02-18',
            slug2='option-two-main-name-and-its-awesome',
        )
        self.assertEqual(RelatedPrepopulated.objects.all().count(), 4)
        RelatedPrepopulated.objects.get(
            name=' here is a sŤāÇkeð   inline !  ',
            pubdate='2011-12-17',
            status='option one',
            slug1='here-stacked-inline-2011-12-17',
            slug2='option-one-here-stacked-inline',
        )
        RelatedPrepopulated.objects.get(
            name=' now you haVe anöther   sŤāÇkeð  inline with a very ... loooooooooooooooooo',  # 75 characters in name field
            pubdate='1999-01-25',
            status='option two',
            slug1='now-you-have-another-stacked-inline-very-loooooooo',
            slug2='option-two-now-you-have-another-stacked-inline-very-looooooo',
        )
        RelatedPrepopulated.objects.get(
            name='And now, with a tÃbűlaŘ inline !!!',
            pubdate='1234-12-07',
            status='option two',
            slug1='and-now-tabular-inline-1234-12-07',
            slug2='option-two-and-now-tabular-inline',
        )
        RelatedPrepopulated.objects.get(
            name='a tÃbűlaŘ inline with ignored ;"&*^\%$#@-/`~ characters',
            pubdate='1981-08-22',
            status='option one',
            slug1='tabular-inline-ignored-characters-1981-08-22',
            slug2='option-one-tabular-inline-ignored-characters',
        )

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
        self.selenium.find_element_by_css_selector('#id_name').send_keys(' hello')

        # The slugs got prepopulated didn't change since they were originally not empty
        slug1 = self.selenium.find_element_by_css_selector('#id_slug1').get_attribute('value')
        slug2 = self.selenium.find_element_by_css_selector('#id_slug2').get_attribute('value')
        self.assertEqual(slug1, 'main-name-best-2012-02-18')
        self.assertEqual(slug2, 'option-two-main-name-best')

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
        self.selenium.get('%s%s' % (self.live_server_url,
            '/test_admin/admin/admin_views/reservation/add/'))
        self.assertEqual(
            self.selenium.switch_to_active_element(),
            self.selenium.find_element_by_id('id_start_date_0')
        )


class SeleniumAdminViewsChromeTests(SeleniumAdminViewsFirefoxTests):
    webdriver_class = 'selenium.webdriver.chrome.webdriver.WebDriver'


class SeleniumAdminViewsIETests(SeleniumAdminViewsFirefoxTests):
    webdriver_class = 'selenium.webdriver.ie.webdriver.WebDriver'


@override_settings(PASSWORD_HASHERS=('django.contrib.auth.hashers.SHA1PasswordHasher',),
    ROOT_URLCONF="admin_views.urls")
class ReadonlyTest(TestCase):
    fixtures = ['admin-views-users.xml']

    def setUp(self):
        self.client.login(username='super', password='secret')

    def tearDown(self):
        self.client.logout()

    def test_readonly_get(self):
        response = self.client.get('/test_admin/admin/admin_views/post/add/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="posted"')
        # 3 fields + 2 submit buttons + 5 inline management form fields, + 2
        # hidden fields for inlines + 1 field for the inline + 2 empty form
        self.assertContains(response, "<input", count=15)
        self.assertContains(response, formats.localize(datetime.date.today()))
        self.assertContains(response,
            "<label>Awesomeness level:</label>")
        self.assertContains(response, "Very awesome.")
        self.assertContains(response, "Unknown coolness.")
        self.assertContains(response, "foo")

        # Checks that multiline text in a readonly field gets <br /> tags
        self.assertContains(response, "Multiline<br />test<br />string")
        self.assertContains(response, "<p>Multiline<br />html<br />content</p>", html=True)
        self.assertContains(response, "InlineMultiline<br />test<br />string")

        self.assertContains(response,
            formats.localize(datetime.date.today() - datetime.timedelta(days=7)))

        self.assertContains(response, '<div class="form-row field-coolness">')
        self.assertContains(response, '<div class="form-row field-awesomeness_level">')
        self.assertContains(response, '<div class="form-row field-posted">')
        self.assertContains(response, '<div class="form-row field-value">')
        self.assertContains(response, '<div class="form-row">')
        self.assertContains(response, '<p class="help">', 3)
        self.assertContains(response, '<p class="help">Some help text for the title (with unicode ŠĐĆŽćžšđ)</p>', html=True)
        self.assertContains(response, '<p class="help">Some help text for the content (with unicode ŠĐĆŽćžšđ)</p>', html=True)
        self.assertContains(response, '<p class="help">Some help text for the date (with unicode ŠĐĆŽćžšđ)</p>', html=True)

        p = Post.objects.create(title="I worked on readonly_fields", content="Its good stuff")
        response = self.client.get('/test_admin/admin/admin_views/post/%d/' % p.pk)
        self.assertContains(response, "%d amount of cool" % p.pk)

    def test_readonly_post(self):
        data = {
            "title": "Django Got Readonly Fields",
            "content": "This is an incredible development.",
            "link_set-TOTAL_FORMS": "1",
            "link_set-INITIAL_FORMS": "0",
            "link_set-MAX_NUM_FORMS": "0",
        }
        response = self.client.post('/test_admin/admin/admin_views/post/add/', data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Post.objects.count(), 1)
        p = Post.objects.get()
        self.assertEqual(p.posted, datetime.date.today())

        data["posted"] = "10-8-1990"  # some date that's not today
        response = self.client.post('/test_admin/admin/admin_views/post/add/', data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Post.objects.count(), 2)
        p = Post.objects.order_by('-id')[0]
        self.assertEqual(p.posted, datetime.date.today())

    def test_readonly_manytomany(self):
        "Regression test for #13004"
        response = self.client.get('/test_admin/admin/admin_views/pizza/add/')
        self.assertEqual(response.status_code, 200)

    def test_user_password_change_limited_queryset(self):
        su = User.objects.filter(is_superuser=True)[0]
        response = self.client.get('/test_admin/admin2/auth/user/%s/password/' % su.pk)
        self.assertEqual(response.status_code, 404)

    def test_change_form_renders_correct_null_choice_value(self):
        """
        Regression test for #17911.
        """
        choice = Choice.objects.create(choice=None)
        response = self.client.get('/test_admin/admin/admin_views/choice/%s/' % choice.pk)
        self.assertContains(response, '<p>No opinion</p>', html=True)
        self.assertNotContains(response, '<p>(None)</p>')

    def test_readonly_backwards_ref(self):
        """
        Regression test for #16433 - backwards references for related objects
        broke if the related field is read-only due to the help_text attribute
        """
        topping = Topping.objects.create(name='Salami')
        pizza = Pizza.objects.create(name='Americano')
        pizza.toppings.add(topping)
        response = self.client.get('/test_admin/admin/admin_views/topping/add/')
        self.assertEqual(response.status_code, 200)

    def test_readonly_field_overrides(self):
        """
        Regression test for #22087 - ModelForm Meta overrides are ignored by
        AdminReadonlyField
        """
        p = FieldOverridePost.objects.create(title="Test Post", content="Test Content")
        response = self.client.get('/test_admin/admin/admin_views/fieldoverridepost/%d/' % p.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<p class="help">Overridden help text for the date</p>')
        self.assertContains(response, '<label for="id_public">Overridden public label:</label>', html=True)
        self.assertNotContains(response, "Some help text for the date (with unicode ŠĐĆŽćžšđ)")
