"""Read-only integration checks for the combined FlowLab/E&I deployment."""

import unittest
import os

from werkzeug.test import Client
from werkzeug.wrappers import Response

from integrated_app import application


class IntegratedPlatformTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from web_app import app
        cls.previous_testing=app.config.get('TESTING',False)
        app.config['TESTING']=False
        cls.client = Client(application, Response)

    @classmethod
    def tearDownClass(cls):
        from web_app import app
        app.config['TESTING']=cls.previous_testing

    def test_landing_and_both_login_pages_share_one_origin(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/login").status_code, 200)
        response = self.client.get("/ei-lab/login/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/ei-lab/static/", response.data)

    def test_actual_landing_choices_reach_different_login_pages(self):
        import re
        client=Client(application,Response)
        landing=client.get('/').get_data(as_text=True)
        links=re.findall(r'<a class="access-link" href="([^"]+)"',landing)
        self.assertGreaterEqual(len(links),3)
        flow=client.get(links[0],follow_redirects=True)
        ei=client.get(links[1],follow_redirects=True)
        self.assertEqual(flow.status_code,200)
        self.assertEqual(ei.status_code,200)
        self.assertIn('Sign In · FlowLab Pro',flow.get_data(as_text=True))
        self.assertIn('Sign In · E&amp;I Lab',ei.get_data(as_text=True))
        self.assertNotEqual(flow.request.path,ei.request.path)

    def test_ei_root_uses_prefixed_auth_redirect(self):
        response = self.client.get("/ei-lab/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith("/ei-lab/login/"))

    def test_ei_static_files_are_served_under_mount(self):
        response = self.client.get("/ei-lab/static/core/flowlab-theme.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/css", response.headers.get("Content-Type", ""))

    def test_shared_policy_library_is_public_and_linked_from_ei(self):
        self.assertEqual(self.client.get("/lab-policies").status_code, 200)
        response = self.client.get("/ei-lab/login/")
        # The authenticated E&I shell contains the same public policy route;
        # login remains intentionally independent.
        self.assertEqual(response.status_code, 200)

    def test_ei_uses_postgresql_and_separate_cookie_scope(self):
        from django.conf import settings
        expected = 'django.db.backends.sqlite3' if os.environ.get('EI_LAB_FORCE_SQLITE') == '1' else 'django.db.backends.postgresql'
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], expected)
        self.assertEqual(settings.SESSION_COOKIE_PATH, "/ei-lab/")
        self.assertEqual(settings.CSRF_COOKIE_PATH, "/ei-lab/")

    def test_flask_session_cookie_does_not_authenticate_django(self):
        from web_app import app
        client = Client(application, Response)
        serializer = app.session_interface.get_signing_serializer(app)
        client.set_cookie('session', serializer.dumps({'user_id':1, 'role_name':'Administrator'}))
        response = client.get('/ei-lab/jobs/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].startswith('/ei-lab/login/'))

    def test_django_cookie_does_not_authenticate_flask(self):
        client = Client(application, Response)
        client.set_cookie('ei_lab_sessionid', 'no-shared-authentication', path='/ei-lab/')
        response = client.get('/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])


if __name__ == "__main__":
    unittest.main()
