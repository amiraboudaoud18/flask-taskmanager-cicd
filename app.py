import os
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    request,
    session,
    flash,
    g,
)
from dotenv import load_dotenv
from extensions import db 

load_dotenv()


def _build_postgres_uri() -> str:
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url

    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    name = os.environ.get("POSTGRES_DB", "taskmanager")

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


def create_app():
    app = Flask(__name__)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-unsafe-secret")
    app.config["SQLALCHEMY_DATABASE_URI"] = _build_postgres_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        from models import User, Task  # noqa: F401
        db.create_all()

    register_routes(app)
    return app



def login_required(view):
    @wraps(view)
    def wrapped_view(**kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(**kwargs)

    return wrapped_view


def register_routes(app):
    from models import User, Task

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        if user_id is None:
            g.user = None
        else:
            g.user = db.session.get(User, user_id)


    @app.route("/")
    @login_required
    def index():
        status_filter = request.args.get("status", "all")
        query = Task.query.filter_by(user_id=g.user.id)

        if status_filter == "open":
            query = query.filter_by(is_completed=False)
        elif status_filter == "done":
            query = query.filter_by(is_completed=True)

        tasks = query.order_by(Task.due_date.asc().nullslast()).all()
        return render_template(
            "index.html",
            tasks=tasks,
            status_filter=status_filter,
            today=date.today(),
        )

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")

            if not username or not password:
                flash("Username and password are required.", "error")
            elif password != confirm:
                flash("Passwords do not match.", "error")
            elif User.query.filter_by(username=username).first():
                flash("Username is already taken.", "error")
            else:
                user = User(username=username)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            user = User.query.filter_by(username=username).first()
            if user is None or not user.check_password(password):
                flash("Invalid username or password.", "error")
            else:
                session.clear()
                session["user_id"] = user.id
                flash("Logged in successfully.", "success")
                next_url = request.args.get("next")
                return redirect(next_url or url_for("index"))

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("login"))

    @app.route("/tasks/new", methods=["GET", "POST"])
    @login_required
    def create_task():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            due_date_str = request.form.get("due_date", "").strip()

            if not title:
                flash("Title is required.", "error")
                return render_template("task_form.html", task=None)

            due_date = None
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                except ValueError:
                    flash("Invalid date format. Use YYYY-MM-DD.", "error")
                    return render_template("task_form.html", task=None)

            task = Task(
                title=title,
                description=description or None,
                due_date=due_date,
                user_id=g.user.id,
            )
            db.session.add(task)
            db.session.commit()
            flash("Task created.", "success")
            return redirect(url_for("index"))

        return render_template("task_form.html", task=None)

    @app.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_task(task_id):
        task = Task.query.filter_by(id=task_id, user_id=g.user.id).first_or_404()

        if request.method == "POST":
            title = request.form.get("title", "").strip()
            description = request.form.get("description", "").strip()
            due_date_str = request.form.get("due_date", "").strip()
            is_completed = bool(request.form.get("is_completed"))

            if not title:
                flash("Title is required.", "error")
                return render_template("task_form.html", task=task)

            due_date = None
            if due_date_str:
                try:
                    due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
                except ValueError:
                    flash("Invalid date format. Use YYYY-MM-DD.", "error")
                    return render_template("task_form.html", task=task)

            task.title = title
            task.description = description or None
            task.due_date = due_date
            task.is_completed = is_completed
            db.session.commit()

            flash("Task updated.", "success")
            return redirect(url_for("index"))

        return render_template("task_form.html", task=task)

    @app.route("/tasks/<int:task_id>/toggle", methods=["POST"])
    @login_required
    def toggle_task(task_id):
        task = Task.query.filter_by(id=task_id, user_id=g.user.id).first_or_404()
        task.is_completed = not task.is_completed
        db.session.commit()
        flash("Task status updated.", "success")
        return redirect(url_for("index"))

    @app.route("/tasks/<int:task_id>/delete", methods=["POST"])
    @login_required
    def delete_task(task_id):
        task = Task.query.filter_by(id=task_id, user_id=g.user.id).first_or_404()
        db.session.delete(task)
        db.session.commit()
        flash("Task deleted.", "success")
        return redirect(url_for("index"))


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000, host="0.0.0.0")
