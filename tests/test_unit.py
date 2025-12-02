# Unit tests

import os
from datetime import date, timedelta
from models import User, Task
from app import _build_postgres_uri


class TestUserModel:
    """Test User model methods"""
    
    def test_set_password(self):
        """Test that set_password hashes the password"""
        user = User(username="testuser")
        user.set_password("mypassword123")
        
        # Password should be hashed (not stored as plain text)
        assert user.password_hash != "mypassword123"
        assert user.password_hash is not None
        assert len(user.password_hash) > 20  # Hashes are long
    
    def test_check_password_correct(self):
        """Test that check_password works with correct password"""
        user = User(username="testuser")
        user.set_password("mypassword123")
        
        # Should return True for correct password
        assert user.check_password("mypassword123") is True
    
    def test_check_password_incorrect(self):
        """Test that check_password rejects wrong password"""
        user = User(username="testuser")
        user.set_password("mypassword123")
        
        # Should return False for wrong password
        assert user.check_password("wrongpassword") is False


class TestTaskModel:
    """Test Task model methods"""
    
    def test_is_overdue_with_past_date(self):
        """Test that task is overdue if due_date is in the past"""
        task = Task(
            title="Old Task",
            due_date=date.today() - timedelta(days=5),  # 5 days ago
            is_completed=False
        )
        
        assert task.is_overdue() is True
    
    def test_is_overdue_with_future_date(self):
        """Test that task is NOT overdue if due_date is in the future"""
        task = Task(
            title="Future Task",
            due_date=date.today() + timedelta(days=5),  # 5 days from now
            is_completed=False
        )
        
        assert task.is_overdue() is False
    
    def test_is_overdue_completed_task(self):
        """Test that completed tasks are never overdue"""
        task = Task(
            title="Completed Task",
            due_date=date.today() - timedelta(days=5),  # Past date
            is_completed=True  # But it's completed
        )
        
        # Even though due_date is past, completed tasks aren't overdue
        assert task.is_overdue() is False
    
    def test_is_overdue_no_due_date(self):
        """Test that tasks without due_date are never overdue"""
        task = Task(
            title="No Due Date",
            due_date=None,
            is_completed=False
        )
        
        assert task.is_overdue() is False


class TestBuildPostgresUri:
    """Test the _build_postgres_uri helper function"""
    
    def test_build_uri_from_database_url(self, monkeypatch):
        """Test that DATABASE_URL takes precedence"""
        # monkeypatch lets us fake environment variables
        monkeypatch.setenv("DATABASE_URL", "postgresql://custom-url")
        
        uri = _build_postgres_uri()
        assert uri == "postgresql://custom-url"
    
    def test_build_uri_from_components(self, monkeypatch):
        """Test building URI from individual components"""
        # Clear DATABASE_URL so it uses components
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("POSTGRES_USER", "myuser")
        monkeypatch.setenv("POSTGRES_PASSWORD", "mypass")
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_PORT", "5432")
        monkeypatch.setenv("POSTGRES_DB", "mydb")
        
        uri = _build_postgres_uri()
        expected = "postgresql+psycopg2://myuser:mypass@localhost:5432/mydb"
        assert uri == expected
    
    def test_build_uri_with_defaults(self, monkeypatch):
        """Test that defaults are used when env vars are missing"""
        # Clear all postgres env vars
        for key in ["DATABASE_URL", "POSTGRES_USER", "POSTGRES_PASSWORD", 
                    "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB"]:
            monkeypatch.delenv(key, raising=False)
        
        uri = _build_postgres_uri()
        expected = "postgresql+psycopg2://postgres:postgres@localhost:5432/taskmanager"
        assert uri == expected