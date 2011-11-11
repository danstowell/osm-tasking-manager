import unittest
from pyramid.config import Configurator
from pyramid import testing

def _initTestingDB():
    from sqlalchemy import create_engine
    from OSMTM.models import initialize_sql, populate
    session = initialize_sql(create_engine('sqlite:///:memory:'))
    populate()
    return session

def _registerRoutes(config):
    config.add_route('job', 'job/{job}')

class TileModelTests(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        _initTestingDB()

    def tearDown(self):
        testing.tearDown()

    def _getTargetClass(self):
        from OSMTM.models import Tile
        return Tile

    def _makeOne(self, x=1, y=2):
        return self._getTargetClass()(x, y)

    def test_constructor(self):
        instance = self._makeOne()
        self.assertEqual(instance.x, 1)
        self.assertEqual(instance.y, 2)
        self.assertEqual(instance.checkin, 0)

class JobModelTests(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        _initTestingDB()

    def tearDown(self):
        testing.tearDown()

    def _getTargetClass(self):
        from OSMTM.models import Job
        return Job

    def _makeOne(self, title='SomeTitle', description='some description',
            geometry='some geometry', workflow='some workflow', zoom=1):
        return self._getTargetClass()(title, description, geometry, workflow, zoom)

    def test_constructor(self):
        instance = self._makeOne()
        self.assertEqual(instance.title, 'SomeTitle')
        self.assertEqual(instance.description, 'some description')
        self.assertEqual(instance.geometry, 'some geometry')
        self.assertEqual(instance.workflow, 'some workflow')
        self.assertEqual(instance.zoom, 1)

class UserModelTests(unittest.TestCase):

    def setUp(self):
        self.config = testing.setUp()
        _initTestingDB()

    def tearDown(self):
        testing.tearDown()

    def _getTargetClass(self):
        from OSMTM.models import User
        return User

    def _makeOne(self, username=u'bar'):
        user = self._getTargetClass()(username)
        return user

    def test_constructor(self):
        instance = self._makeOne()
        self.assertEqual(instance.username, u'bar')

class TestHome(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        _initTestingDB()

    def tearDown(self):
        testing.tearDown()

    def test_it(self):
        from OSMTM.views.views import home 
        request = testing.DummyRequest()
        self.config.testing_securitypolicy(userid=u'foo')
        info = home(request)
        self.assertEqual(len(info['jobs']), 1)
        self.assertEqual(info['admin'], False)

class TestJobNew(unittest.TestCase):
    
    def setUp(self):
        self.config = testing.setUp()
        self.session = _initTestingDB()

    def tearDown(self):
        testing.tearDown()

    def test_it(self):
        _registerRoutes(self.config)
        from OSMTM.views.jobs import job_new
        request = testing.DummyRequest()
        request.params = {
            'form.submitted': True,
            'title':u'NewJob',
            'description':u'SomeDescription',
            'geometry':u'POLYGON((0 0, 100 0, 100 100, 0 100, 0 0))',
            'workflow':u'SomeWorflow',
            'imagery':u'',
            'zoom':20
        }
        response = job_new(request)
        self.assertEqual(response.location, 'http://example.com/job/2')
        from OSMTM.models import Job
        self.assertEqual(len(self.session.query(Job).get(2).tiles),
            9)

class TestJob(unittest.TestCase):
    
    def setUp(self):
        self.config = testing.setUp()
        self.session = _initTestingDB()

    def tearDown(self):
        testing.tearDown()

    def test_it(self):
        _registerRoutes(self.config)
        from OSMTM.views.jobs import job
        request = testing.DummyRequest()
        self.config.testing_securitypolicy(userid=u'foo')
        request.matchdict = {'job': 1}
        info = job(request)
        from OSMTM.models import Job
        self.assertEqual(info['job'], self.session.query(Job).get(1))

class FunctionalTests(unittest.TestCase):

    def setUp(self):
        from OSMTM import main
        settings = {
            'sqlalchemy.url': 'sqlite:///:memory:'
        }
        self.app = main({}, **settings)
        from webtest import TestApp
        self.testapp = TestApp(self.app)

        from OSMTM.models import populate
        populate()

    def __remember(self, username):
        from pyramid.security import remember
        request = testing.DummyRequest(environ={'SERVER_NAME': 'servername'})
        request.registry = self.app.registry
        headers = remember(request, username)
        return {'Cookie': headers[0][1].split(';')[0]}

    def __forget(self):
        from pyramid.security import forget
        request = testing.DummyRequest(environ={'SERVER_NAME': 'servername'})
        request.registry = self.app.registry
        forget(request)

    def test_root(self):
        res = self.testapp.get('/', status=200)
        self.failUnless('About Task Server' in res.body)
        self.failUnless('Login' in res.body)

    def test_authenticated(self):
        from pyramid.security import remember, forget
        headers = self.__remember('foo')
        try:
            res = self.testapp.get('/', headers=headers, status=200)
        finally:
            self.__forget()
        self.failUnless('You are foo' in res.body)

    def test_user_authenticated(self):
        from pyramid.security import remember, forget
        headers = self.__remember('foo')
        try:
            res = self.testapp.get('/', headers=headers, status=200)
        finally:
            self.__forget()
        self.assertFalse('<a href="http://localhost:6543/users">Users</a>' in res.body)

    def test_user_users(self):
        from pyramid.security import remember, forget
        headers = self.__remember('foo')
        try:
            res = self.testapp.get('/users', headers=headers, status=200)
        finally:
            self.__forget()

    def test_user_profile(self):
        from pyramid.security import remember, forget
        headers = self.__remember('foo')
        try:
            res = self.testapp.get('/user/foo', headers=headers, status=200)
        finally:
            self.__forget()
        self.assertTrue('Forbidden' in res.body)

    def test_admin_authenticated(self):
        from pyramid.security import remember, forget
        headers = self.__remember('admin_user')
        try:
            res = self.testapp.get('/', headers=headers, status=200)
        finally:
            self.__forget()
        self.assertTrue('<a href="http://localhost/users">Users</a>' in res.body)

    def test_about(self):
        from pyramid.security import remember, forget
        headers = self.__remember('foo')
        try:
            res = self.testapp.get('/about', headers=headers, status=200)
        finally:
            self.__forget()
        self.assertEquals(res.html.head.title.string, 'OSM Tasking Manager - About')

    def test_nextview(self):
        from pyramid.security import remember, forget
        headers = self.__remember('foo')
        from OSMTM.models import DBSession, User
        session = DBSession()
        try:
            res = self.testapp.get('/profile/nextview', headers=headers, status=200)
        finally:
            self.__forget()

        try:
            res = self.testapp.post('/profile/nextview',
                    params={'accepted_terms': 'I AGREE', 'redirect': 'http://localhost/'},
                    headers=headers, status=302)
        finally:
            self.__forget()

        user = session.query(User).get('foo')
        self.assertTrue(user.accepted_nextview)
        try:
            res = self.testapp.post('/profile/nextview',
                    params={'accepted_terms': 'blah', 'redirect': 'http://localhost/'},
                    headers=headers, status=302)
        finally:
            self.__forget()

        from OSMTM.models import DBSession, User
        session = DBSession()
        user = session.query(User).get('foo')
        self.assertFalse(user.accepted_nextview)

    def test_admin_user(self):
        from pyramid.security import remember, forget
        headers = self.__remember('admin_user')
        try:
            res = self.testapp.get('/user/foo', headers=headers, status=200)
            self.assertTrue('Profile for foo' in res.body)
            self.assertFalse(res.html.find(id='admin').checked)
        finally:
            self.__forget()

        try:
            res = self.testapp.get('/user/admin_user', headers=headers, status=200)
            self.assertTrue('Profile for admin_user' in res.body)
            self.assertTrue(res.html.find(id='admin')['checked'] == 'checked')
        finally:
            self.__forget()

    def test_admin_user_update(self):
        from pyramid.security import remember, forget
        headers = self.__remember('admin_user')
        try:
            res = self.testapp.post('/user/foo/update',
                    params={'form.submitted': True, 'admin': 'on'},
                    headers=headers, status=302)
            res2 = res.follow(status=200)
            self.assertTrue('Profile for foo' in res2.body)
            self.assertTrue(res2.html.find(id='admin').checked)
        finally:
            self.__forget()
