import unittest
import os
from app import app, db, User, Event, RegistrationForm

class BasicTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'test_musorfigyelo.db')
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['LOGIN_DISABLED'] = True

        cls.client = app.test_client()

        with app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.drop_all()
        basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        test_db_path = os.path.join(basedir, 'test_musorfigyelo.db')
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_index_page_loads(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'M\xc5\xb1sorfigyel\xc5\x91',
                      response.data)
    def test_user_model_password_hashing(self):
        with app.app_context():
            u = User(fullname="Test User", email="test@example.com")
            u.set_password("cat")
            self.assertFalse(u.check_password("dog"))
            self.assertTrue(u.check_password("cat"))
            self.assertNotEqual(u.password_hash, "cat")

    def test_registration_form_validation(self):
        form = RegistrationForm(fullname="", email="user", password="pw", confirm_password="pw")
        self.assertFalse(form.validate())
        self.assertIn('email', form.errors)
        self.assertIn('fullname', form.errors)

        form = RegistrationForm(fullname="Valid Name", email="valid@example.com", password="password1",
                                confirm_password="password2")
        self.assertFalse(form.validate())
        self.assertIn('confirm_password', form.errors)
        self.assertIn('A két jelszónak egyeznie kell.', form.confirm_password.errors[0])

        form = RegistrationForm(fullname="Valid Name", email="valid@example.com", password="password123",
                                confirm_password="password123")
        with app.test_request_context():
            is_valid_without_db_check = form.password.validate(form) and \
                                        form.confirm_password.validate(form) and \
                                        form.email.validate(form) and \
                                        form.fullname.validate(form)
            self.assertTrue(is_valid_without_db_check)

    def test_add_event_to_db_and_retrieve(self):
        with app.app_context():
            initial_event_count = Event.query.count()
            new_event = Event(title="Tesztesemény", event_type="Teszt", venue="Teszt Helyszín",
                              city="Tesztváros", date="2025-12-31", time="23:59", source="Test")
            db.session.add(new_event)
            db.session.commit()

            self.assertEqual(Event.query.count(), initial_event_count + 1)
            retrieved_event = Event.query.filter_by(title="Tesztesemény").first()
            self.assertIsNotNone(retrieved_event)
            self.assertEqual(retrieved_event.venue, "Teszt Helyszín")

            db.session.delete(retrieved_event)
            db.session.commit()
            self.assertEqual(Event.query.count(), initial_event_count)


if __name__ == '__main__':
    unittest.main()