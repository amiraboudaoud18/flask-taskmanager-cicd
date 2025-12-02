# Integration tests - test Flask routes with a test database

import pytest
from app import create_app
from extensions import db
from models import User, Task


@pytest.fixture
def app():
    """Create a Flask app configured for testing"""
    app = create_app()

    # Use a separate test database
    app.config.update(
        {
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',  # In-memory DB
            'WTF_CSRF_ENABLED': False,  # Disable CSRF for testing
            'SECRET_KEY': 'test-secret-key',
        }
    )

    # Create tables
    with app.app_context():
        db.create_all()

    yield app

    # Properly cleanup: remove session and drop tables
    with app.app_context():
        db.session.remove()  # Close all sessions first!
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for making requests"""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a CLI runner for testing CLI commands"""
    return app.test_cli_runner()


class TestAuthFlow:
    """Test user registration and login"""

    def test_register_success(self, client):
        """Test successful user registration"""
        response = client.post(
            '/register',
            data={
                'username': 'newuser',
                'password': 'password123',
                'confirm': 'password123',
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert (
            b'Registration successful' in response.data
            or b'Please log in' in response.data
        )

    def test_register_password_mismatch(self, client):
        """Test registration fails when passwords don't match"""
        response = client.post(
            '/register',
            data={
                'username': 'newuser',
                'password': 'password123',
                'confirm': 'different',
            },
        )

        assert b'Passwords do not match' in response.data

    def test_register_duplicate_username(self, client, app):
        """Test registration fails with duplicate username"""
        # Create a user first
        with app.app_context():
            user = User(username='existing')
            user.set_password('pass')
            db.session.add(user)
            db.session.commit()

        # Try to register with same username
        response = client.post(
            '/register',
            data={
                'username': 'existing',
                'password': 'password123',
                'confirm': 'password123',
            },
        )

        assert b'already taken' in response.data

    def test_login_success(self, client, app):
        """Test successful login"""
        # Create a user
        with app.app_context():
            user = User(username='testuser')
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

        # Login
        response = client.post(
            '/login',
            data={'username': 'testuser', 'password': 'password123'},
            follow_redirects=True,
        )

        assert response.status_code == 200
        # Should not see login error message
        assert b'Invalid username or password' not in response.data

    def test_login_invalid_credentials(self, client):
        """Test login fails with wrong password"""
        response = client.post(
            '/login', data={'username': 'nonexistent', 'password': 'wrongpass'}
        )

        assert b'Invalid username or password' in response.data


class TestTaskOperations:
    """Test task CRUD operations"""

    @pytest.fixture
    def logged_in_client(self, client, app):
        """Create a logged-in test client"""
        # Create and login a user
        with app.app_context():
            user = User(username='taskuser')
            user.set_password('pass')
            db.session.add(user)
            db.session.commit()

        # Login
        client.post('/login', data={'username': 'taskuser', 'password': 'pass'})

        return client

    def test_create_task(self, logged_in_client, app):
        """Test creating a new task"""
        response = logged_in_client.post(
            '/tasks/new',
            data={
                'title': 'Test Task',
                'description': 'Test Description',
                'due_date': '2025-12-31',
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b'Task created' in response.data

        # Verify task was saved to database
        with app.app_context():
            task = Task.query.filter_by(title='Test Task').first()
            assert task is not None
            assert task.description == 'Test Description'

    def test_toggle_task(self, logged_in_client, app):
        """Test toggling task completion status"""
        # Create a task first
        with app.app_context():
            user = User.query.filter_by(username='taskuser').first()
            task = Task(title='Toggle Test', user_id=user.id, is_completed=False)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        # Toggle it
        response = logged_in_client.post(
            f'/tasks/{task_id}/toggle', follow_redirects=True
        )

        assert response.status_code == 200
        assert b'Task status updated' in response.data

        # Verify it was toggled
        with app.app_context():
            task = db.session.get(Task, task_id)
            assert task.is_completed is True

    def test_delete_task(self, logged_in_client, app):
        """Test deleting a task"""
        # Create a task first
        with app.app_context():
            user = User.query.filter_by(username='taskuser').first()
            task = Task(title='Delete Me', user_id=user.id)
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        # Delete it
        response = logged_in_client.post(
            f'/tasks/{task_id}/delete', follow_redirects=True
        )

        assert response.status_code == 200
        assert b'Task deleted' in response.data

        # Verify it's gone
        with app.app_context():
            task = db.session.get(Task, task_id)
            assert task is None
