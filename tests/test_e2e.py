#End-to-end tests - test the app through a real browser

import pytest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from app import create_app
from extensions import db
from threading import Thread


@pytest.fixture(scope="module")
def app():
    """Create and configure a test app"""
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    
    with app.app_context():
        db.create_all()
    
    yield app
    
    with app.app_context():
        db.drop_all()


@pytest.fixture(scope="module")
def live_server(app):
    """Run the Flask app in a background thread"""
    def run_app():
        app.run(port=5001, use_reloader=False, threaded=True)
    
    thread = Thread(target=run_app, daemon=True)
    thread.start()
    time.sleep(2)  # Give server time to start
    
    yield "http://localhost:5001"  


@pytest.fixture
def driver():
    """Create a Chrome WebDriver instance"""
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(10)
    
    yield driver
    
    driver.quit()


class TestE2EAuth:
    """Test authentication through the browser"""
    
    def test_register_and_login(self, driver, live_server):
        driver.get(f"{live_server}/register")
        
        driver.find_element(By.NAME, "username").send_keys("e2euser")
        driver.find_element(By.NAME, "password").send_keys("password123")
        driver.find_element(By.NAME, "confirm").send_keys("password123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        WebDriverWait(driver, 10).until(
            EC.url_contains("/login")
        )
        
        driver.find_element(By.NAME, "username").send_keys("e2euser")
        driver.find_element(By.NAME, "password").send_keys("password123")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        WebDriverWait(driver, 10).until(
            EC.url_to_be(f"{live_server}/")
        )
        
        assert "task" in driver.page_source.lower()


class TestE2ETaskOperations:
    """Test task operations through the browser"""
    
    @pytest.fixture(autouse=True)
    def setup(self, driver, live_server):
        """Register and login a user before each test"""
        driver.get(f"{live_server}/register")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        
        username = f"taskuser_{time.time()}"
        driver.find_element(By.NAME, "username").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys("pass")
        driver.find_element(By.NAME, "confirm").send_keys("pass")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        username_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        username_input.send_keys(username)
        driver.find_element(By.NAME, "password").send_keys("pass")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "New Task"))
        )

    def test_create_task_through_ui(self, driver, live_server):
        driver.find_element(By.LINK_TEXT, "New Task").click()
        
        driver.find_element(By.NAME, "title").send_keys("E2E Test Task")
        driver.find_element(By.NAME, "description").send_keys("Created by Selenium")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        WebDriverWait(driver, 10).until(
            EC.url_to_be(f"{live_server}/")
        )
        assert "E2E Test Task" in driver.page_source

    def test_toggle_task_completion(self, driver, live_server):
        driver.get(f"{live_server}/tasks/new")
        driver.find_element(By.NAME, "title").send_keys("Toggle Task")
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        
        time.sleep(1)
        toggle_button = driver.find_element(By.CSS_SELECTOR, "form[action*='/toggle'] button")
        toggle_button.click()
        time.sleep(1)
        
        assert "completed" in driver.page_source.lower() or "done" in driver.page_source.lower()
