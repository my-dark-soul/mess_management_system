from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash
from functools import wraps
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
from files_utils import move_all_files
import os
from sqlalchemy import func, extract
from flask_login import LoginManager
import calendar
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'myy_meal_management_system'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meal_management_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
UPLOAD_FOLDER = 'member_photo'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
migrate = Migrate(app, db)


# =======================
# Models
# =======================

class Monitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    password = db.Column(db.String(200), nullable=False)
    photo = db.Column(db.String(200), nullable=True)
    mess_location = db.Column(db.String(100), nullable=False)

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    nid = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(100), nullable=True)
    photo = db.Column(db.String(100), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='boder')

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bajar_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    bajarkari = db.Column(db.String(100), nullable=False)
    meal_cost = db.Column(db.Float, nullable=False)
    extra = db.Column(db.Float, nullable=True)
    total_cost = db.Column(db.Float, nullable=False)

class Notice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class Cleaning(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cleaning_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cleaner1 = db.Column(db.String(100), nullable=False)
    cleaner2 = db.Column(db.String(100), nullable=False)

class MealRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    meal_date = db.Column(db.DateTime, nullable=False)
    # FIX 8: Changed Integer -> Float to correctly store 0.5 meal values
    meal_count = db.Column(db.Float, nullable=False)
    member = db.relationship('Member', backref=db.backref('meal_records', lazy=True))

class GasRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    gas_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    gas_amount = db.Column(db.Float, nullable=False, default=0)

class SavedAmount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    meal_amount = db.Column(db.Float, default=0)
    gas_amount = db.Column(db.Float, default=0)
    member = db.relationship('Member', backref=db.backref('saved_amounts', lazy=True))

class Fine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fine_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    criminal = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    fine_amount = db.Column(db.Float, nullable=False)
    total_fine = db.Column(db.Float, nullable=False)


# =======================
# Helpers / Auth
# =======================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("monitor_id"):
            flash("You must be logged in as Admin to access this page.", "danger")
            return redirect(url_for("signin"))
        return f(*args, **kwargs)
    return decorated_function


# FIX 7: Use db.session.get() instead of deprecated Monitor.query.get()
@app.context_processor
def inject_mess_location():
    mess_location = None
    contact = None
    if "monitor_id" in session:
        monitor = db.session.get(Monitor, session["monitor_id"])
        if monitor:
            mess_location = monitor.mess_location
            contact = monitor.phone
    return dict(mess_location=mess_location, contact=contact)


# =======================
# Routes
# =======================

@app.route("/")
@app.route("/home/")
def home():
    monitor_id = session.get("monitor_id")
    all_members = Member.query.all()
    fine_lists = Fine.query.all()
    current_monitor = db.session.get(Monitor, monitor_id) if monitor_id else Monitor.query.first()
    manager_member = Member.query.filter_by(role="manager").first()
    bajar_list = Item.query.order_by(Item.bajar_date).all()

    first_half = [item for item in bajar_list if 1 <= item.bajar_date.day <= 15]
    second_half = [item for item in bajar_list if item.bajar_date.day >= 16]

    total_meals = db.session.query(func.sum(MealRecord.meal_count)).scalar() or 0
    total_expense = db.session.query(func.sum(Item.total_cost)).scalar() or 0
    meal_rate = total_expense / total_meals if total_meals > 0 else 0

    return render_template(
        "home.html",
        members=all_members,
        current_monitor=current_monitor,
        manager_member=manager_member,
        first_half=first_half,
        second_half=second_half,
        now=datetime.now(),
        fine_lists=fine_lists,
        total_meals=total_meals,
        total=total_expense,
        meal_rate=meal_rate,
    )


@app.route("/members/")
def members():
    all_members = Member.query.all()
    return render_template("members.html", members=all_members)


@app.route("/add_member/", methods=["GET", "POST"])
@login_required
def add_member():
    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        nid = request.form["nid"]
        email = request.form["email"]

        photo_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                photo_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                move_all_files()

        new_member = Member(name=name, phone=phone, nid=nid, email=email, photo=photo_path)
        db.session.add(new_member)
        db.session.commit()
        return redirect(url_for("members"))

    return render_template("add_member.html")


@app.route('/move_files/', methods=['POST'])
def move_files_route():
    try:
        move_all_files()
        return "Files moved successfully!"
    except Exception as e:
        return f"Error while moving files: {str(e)}"


@app.route("/bajar/")
def bajar():
    bajar_list = Item.query.all()
    return render_template("bajar.html", bajar_list=bajar_list)


# FIX 2: Removed monitor_id=session["monitor_id"] — Item model has no monitor_id column
@app.route("/add_items/", methods=["GET", "POST"])
@login_required
def add_items():
    if request.method == "POST":
        bajar_date_str = request.form["bajar_date"]
        bajarkari = request.form["bajarkari"]
        meal_cost = float(request.form["meal_cost"])
        extra = float(request.form["extra"]) if request.form.get("extra") else None
        total_cost = float(request.form["totalCost"])
        bajar_date = datetime.strptime(bajar_date_str, "%Y-%m-%d")

        new_item = Item(
            bajar_date=bajar_date,
            bajarkari=bajarkari,
            meal_cost=meal_cost,
            extra=extra,
            total_cost=total_cost,
        )
        db.session.add(new_item)
        db.session.commit()
        return redirect(url_for("bajar"))

    return render_template("add_items.html")


# FIX 3: Removed monitor_id=session["monitor_id"] — Fine model has no monitor_id column
@app.route("/fine_boder/", methods=['GET', 'POST'])
@login_required
def fine_boder():
    if request.method == 'POST':
        fine_date_str = request.form["fine_date"]
        criminal = request.form["criminal"]
        reason = request.form["reason"]
        fine_amount = float(request.form["fine_amount"])
        total_fine = float(request.form["total_fine"])
        fine_date = datetime.strptime(fine_date_str, "%Y-%m-%d")

        boder_fine_amount = Fine(
            fine_date=fine_date,
            criminal=criminal,
            reason=reason,
            fine_amount=fine_amount,
            total_fine=total_fine
        )
        db.session.add(boder_fine_amount)
        db.session.commit()
        return redirect(url_for("monitor"))

    return redirect(url_for("monitor"))


@app.route("/notice/")
def notice():
    notices = Notice.query.all()
    return render_template("notice.html", notices=notices)


@app.route("/delete_notice/<int:notice_id>", methods=["POST"])
@login_required
def delete_notice(notice_id):
    try:
        notice = db.session.get(Notice, notice_id)
        if not notice:
            flash("Notice not found.", "error")
            return redirect(request.referrer or url_for("home"))

        db.session.delete(notice)
        db.session.commit()
        flash("Notice deleted successfully!", "success")
        return redirect(request.referrer or url_for("home"))
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting notice: {str(e)}", "error")
        return redirect(request.referrer or url_for("home"))


@app.route("/cleaning/")
def cleaning():
    cleanings = Cleaning.query.all()
    return render_template("cleaning.html", cleanings=cleanings)


@app.route("/add_cleaner/", methods=["GET", "POST"])
@login_required
def add_cleaner():
    if request.method == "POST":
        try:
            cleaning_date_str = request.form["cleaning_date"]
            cleaner1 = request.form["cleaner1"]
            cleaner2 = request.form["cleaner2"]
            cleaning_date = datetime.strptime(cleaning_date_str, "%Y-%m-%d")

            cleaning = Cleaning(
                cleaning_date=cleaning_date,
                cleaner1=cleaner1,
                cleaner2=cleaner2,
            )
            db.session.add(cleaning)
            db.session.commit()
            return redirect(url_for("cleaning"))
        except Exception as e:
            return f"An error occurred: {str(e)}"

    return render_template("add_cleaner.html")


@app.route("/delete_cleaning/<int:cleaning_id>", methods=["POST"])
@login_required
def delete_cleaning(cleaning_id):
    try:
        cleaning = db.session.get(Cleaning, cleaning_id)
        if not cleaning:
            flash("Cleaning record not found.", "error")
            return redirect(request.referrer or url_for("home"))

        db.session.delete(cleaning)
        db.session.commit()
        flash("Cleaning record deleted successfully!", "success")
        return redirect(request.referrer or url_for("home"))
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting cleaning record: {str(e)}", "error")
        return redirect(request.referrer or url_for("home"))


@app.route("/meal_rent/")
def meal_rent():
    members = Member.query.all()
    meal_data = {}

    now = datetime.now()
    current_year = now.year
    current_month = now.month
    days_in_month = calendar.monthrange(current_year, current_month)[1]

    for member in members:
        meals = MealRecord.query.filter_by(member_id=member.id).all()
        member_meal_counts = {meal.meal_date.day: meal.meal_count for meal in meals}
        meal_data[member.id] = member_meal_counts

    return render_template(
        "meal_rent.html",
        members=members,
        meal_data=meal_data,
        days_in_month=days_in_month
    )


# FIX 9: meal_table was building a flat dict overwriting per-member data — now builds correct nested structure
@app.route("/meal_table/")
def meal_table():
    members = Member.query.all()
    meal_data = {}

    now = datetime.now()
    days_in_month = calendar.monthrange(now.year, now.month)[1]

    for member in members:
        meals = MealRecord.query.filter_by(member_id=member.id).all()
        meal_data[member.id] = {meal.meal_date.day: meal.meal_count for meal in meals}

    return render_template(
        "meal_rent.html",
        members=members,
        meal_data=meal_data,
        days_in_month=days_in_month
    )


@app.route("/save_meal_data/", methods=["POST"])
@login_required
def save_meal_data():
    meal_data = request.json

    if not meal_data or not isinstance(meal_data, list):
        return jsonify({"success": False, "message": "Invalid data. Expected a list."}), 400

    try:
        now = datetime.now()
        year, month = now.year, now.month

        for entry in meal_data:
            member_id = entry.get("member_id")
            meal_counts = entry.get("meal_counts", [])

            if not member_id:
                continue

            for i, count in enumerate(meal_counts):
                meal_date = datetime(year, month, i + 1)

                existing_record = MealRecord.query.filter_by(
                    member_id=member_id,
                    meal_date=meal_date
                ).first()

                if existing_record:
                    existing_record.meal_count = float(count)
                else:
                    new_record = MealRecord(
                        member_id=member_id,
                        meal_date=meal_date,
                        meal_count=float(count)
                    )
                    db.session.add(new_record)

        db.session.commit()
        return jsonify({"success": True, "message": "Meal data saved successfully!"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)})


# FIX 4 & 5: Removed broken monitor_id and Member.monitor_id filters,
# added missing extract import, now correctly queries all members' monthly meals
@app.route("/meal_summary/")
def meal_summary():
    now = datetime.now()
    members = Member.query.all()

    meal_totals = (
        db.session.query(
            MealRecord.member_id,
            func.sum(MealRecord.meal_count).label("total_meals")
        )
        .filter(
            extract('year', MealRecord.meal_date) == now.year,
            extract('month', MealRecord.meal_date) == now.month
        )
        .group_by(MealRecord.member_id)
        .all()
    )

    totals_dict = {member_id: total for member_id, total in meal_totals}

    return render_template(
        "meal_summary.html",
        members=members,
        totals_dict=totals_dict
    )


# FIX 1: Hash password on signup, verify hash on signin
@app.route("/signup/", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]
        mess_location = request.form["mess_location"]

        if password != confirm_password:
            flash("Passwords do not match", "danger")
            return redirect(url_for("signup"))

        # Check duplicate email
        if Monitor.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
            return redirect(url_for("signup"))

        photo_path = None
        if "photo" in request.files:
            file = request.files["photo"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                photo_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                move_all_files()

        new_monitor = Monitor(
            name=name,
            email=email,
            phone=phone,
            password=generate_password_hash(password),  # FIXED: hash password
            photo=photo_path,
            mess_location=mess_location
        )
        db.session.add(new_monitor)
        db.session.commit()

        flash("Monitor registered successfully!", "success")
        return redirect(url_for("signin"))

    return render_template("signup.html")


@app.route("/signin/", methods=["GET", "POST"])
def signin():
    if request.method == "POST":
        phone = request.form.get("phone")
        password = request.form.get("password")

        monitor = Monitor.query.filter_by(phone=phone).first()

        # FIX 1: Verify against hashed password
        if monitor and check_password_hash(monitor.password, password):
            session['monitor_id'] = monitor.id
            session['monitor_name'] = monitor.name
            flash("Login successful", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid phone or password", "danger")
            return redirect(url_for("signin"))

    return render_template("signin.html")


@app.route("/monitor/", methods=["GET", "POST"])
@login_required
def monitor():
    if request.method == "POST":
        if "title" in request.form and "description" in request.form:
            title = request.form.get("title")
            description = request.form.get("description")
            if title and description:
                try:
                    new_notice = Notice(title=title, description=description)
                    db.session.add(new_notice)
                    db.session.commit()
                    flash("Notice created successfully.", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Error creating notice: {str(e)}", "danger")
            return redirect(url_for("monitor"))

        elif "cleaning_date" in request.form:
            cleaning_date_str = request.form.get("cleaning_date")
            cleaner1 = request.form.get("cleaner1")
            cleaner2 = request.form.get("cleaner2")

            if not cleaning_date_str or not cleaner1:
                flash("Cleaning date and cleaner 1 are required.", "danger")
                return redirect(url_for("monitor"))

            try:
                cleaning_date = datetime.strptime(cleaning_date_str, "%Y-%m-%d")
                cleaning = Cleaning(
                    cleaning_date=cleaning_date,
                    cleaner1=cleaner1,
                    cleaner2=cleaner2
                )
                db.session.add(cleaning)
                db.session.commit()
                flash("Cleaning record added successfully.", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding cleaning: {str(e)}", "danger")

            return redirect(url_for("monitor"))

    all_members = Member.query.all()
    fine_lists = Fine.query.all()
    notices = Notice.query.all()
    cleanings = Cleaning.query.all()
    items = Item.query.all()

    total_meals = db.session.query(func.sum(MealRecord.meal_count)).scalar() or 0

    member_meals = {
        m.id: db.session.query(func.sum(MealRecord.meal_count))
                        .filter(MealRecord.member_id == m.id).scalar() or 0
        for m in all_members
    }

    member_gas = {
        m.id: db.session.query(func.sum(GasRecord.gas_amount))
                        .filter(GasRecord.member_id == m.id).scalar() or 0
        for m in all_members
    }

    member_saved_meal = {
        m.id: db.session.query(func.sum(SavedAmount.meal_amount))
                         .filter(SavedAmount.member_id == m.id).scalar() or 0
        for m in all_members
    }

    member_saved_gas = {
        m.id: db.session.query(func.sum(SavedAmount.gas_amount))
                         .filter(SavedAmount.member_id == m.id).scalar() or 0
        for m in all_members
    }

    total_expense = db.session.query(func.sum(Item.total_cost)).scalar() or 0
    meal_rate = total_expense / total_meals if total_meals > 0 else 0
    current_monitor = db.session.get(Monitor, session.get("monitor_id"))

    return render_template(
        "monitor.html",
        members=all_members,
        fine_lists=fine_lists,
        notices=notices,
        cleanings=cleanings,
        total_meals=total_meals,
        member_meals=member_meals,
        member_gas=member_gas,
        member_saved_meal=member_saved_meal,
        member_saved_gas=member_saved_gas,
        total=total_expense,
        meal_rate=meal_rate,
        current_monitor=current_monitor
    )


@app.route('/save_financial_data/', methods=['POST'])
@login_required
def save_financial_data():
    data = request.get_json(force=True)

    if not data or not isinstance(data, list):
        return jsonify({"success": False, "message": "Invalid or empty data. Expected a list."}), 400

    try:
        for entry in data:
            member_id = entry.get('member_id')
            meal_amount = entry.get('meal_amount', 0)
            gas_amount = entry.get('gas_amount', 0)

            if member_id is None:
                continue

            member = db.session.get(Member, member_id)
            if not member:
                continue

            saved = SavedAmount.query.filter_by(member_id=member_id).first()
            if saved:
                saved.meal_amount = meal_amount
                saved.gas_amount = gas_amount
            else:
                saved = SavedAmount(
                    member_id=member_id,
                    meal_amount=meal_amount,
                    gas_amount=gas_amount
                )
                db.session.add(saved)

        db.session.commit()
        return jsonify({"success": True, "message": "Financial data saved successfully!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/delete_fine/<int:fine_id>", methods=["POST"])
@login_required
def delete_fine(fine_id):
    try:
        fine = db.session.get(Fine, fine_id)
        if not fine:
            flash("Fine record not found.", "error")
            return redirect(request.referrer or url_for("home"))

        db.session.delete(fine)
        db.session.commit()
        flash("Fine record deleted successfully!", "success")
        return redirect(request.referrer or url_for("home"))
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting fine record: {str(e)}", "error")
        return redirect(request.referrer or url_for("home"))


@app.route("/delete_boder/<int:member_id>", methods=["POST"])
@login_required
def delete_boder(member_id):
    try:
        member = db.session.get(Member, member_id)
        if not member:
            flash(f"Member with ID {member_id} not found", "danger")
            return redirect(url_for("monitor"))

        member_name = member.name
        MealRecord.query.filter_by(member_id=member.id).delete(synchronize_session=False)
        SavedAmount.query.filter_by(member_id=member.id).delete(synchronize_session=False)
        GasRecord.query.filter_by(member_id=member.id).delete(synchronize_session=False)

        db.session.delete(member)
        db.session.commit()
        flash(f"Member '{member_name}' removed successfully", "success")
        return redirect(url_for("monitor"))

    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting member: {str(e)}", "danger")
        return redirect(url_for("monitor"))


# FIX 6: Removed monitor_id filter — Member model has no monitor_id column
@app.route('/change_role/<int:member_id>', methods=['POST'])
@login_required
def change_role(member_id):
    new_role = request.form.get('role')
    member = db.session.get(Member, member_id)

    if not member:
        flash("Member not found.", "danger")
        return redirect(url_for('monitor'))

    member.role = new_role
    db.session.commit()
    flash(f"Role for {member.name} updated to {new_role}", "success")
    return redirect(url_for('monitor'))


@app.route("/signout/")
def signout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("signin"))


if __name__ == '__main__':
    app.run(debug=True, port='9003', host='0.0.0.0')
