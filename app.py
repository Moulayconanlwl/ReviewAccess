from flask import (Flask, render_template, request, jsonify,
                   send_file, redirect, url_for, abort)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from flask_bcrypt import Bcrypt
import pandas as pd
from io import BytesIO
from datetime import datetime
from collections import defaultdict

from config import Config
from models import db, User, ReviewSession, UserRow, Delegation
from auth import admin_required, owner_required

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = "login_page"
login_manager.login_message = "Please log in to access this page."

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(role="admin").first():
        hashed = bcrypt.generate_password_hash("Admin@1234").decode("utf-8")
        db.session.add(User(email="admin@scor.com", password_hash=hashed, role="admin"))
        db.session.commit()
        print("Default admin created: admin@scor.com / Admin@1234")


def get_active_session():
    return ReviewSession.query.order_by(ReviewSession.created_at.desc()).first()


# ── Auth ─────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").lower().strip()
        password = request.form.get("password", "")
        user     = User.query.filter_by(email=email).first()
        if user and bcrypt.check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            return redirect(url_for("index"))
        error = "Invalid email or password."
    return render_template("login.html", error=error)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login_page"))

@app.route("/")
@login_required
def index():
    if current_user.role == "admin":
        return render_template("admin.html", user=current_user)
    return render_template("index.html", user=current_user)

@app.errorhandler(403)
def forbidden(_):
    return render_template("login.html", error="Access denied. You do not have permission."), 403

@app.errorhandler(401)
def unauthorized(_):
    return redirect(url_for("login_page"))


# ── Admin: User Management ────────────────────────────────────────────────────
@app.route("/admin/users", methods=["GET"])
@admin_required
def list_users():
    users = User.query.filter(User.role != "admin").all()
    return jsonify([{
        "id": u.id, "email": u.email,
        "role": u.role, "owner_key": u.owner_key
    } for u in users])

@app.route("/admin/users/create", methods=["POST"])
@admin_required
def create_user():
    data = request.json
    if not data.get("email") or not data.get("password"):
        return jsonify({"error": "Email and password required"}), 400
    if User.query.filter_by(email=data["email"].lower()).first():
        return jsonify({"error": "Email already exists"}), 400
    hashed = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    user = User(
        email=data["email"].lower().strip(),
        password_hash=hashed,
        role="filter_owner",
        owner_key=data.get("owner_key", "").strip()
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"success": True, "id": user.id})

@app.route("/admin/users/<int:user_id>", methods=["PUT"])
@admin_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json
    if "owner_key" in data:
        user.owner_key = data["owner_key"].strip()
    if "email" in data and data["email"]:
        user.email = data["email"].lower().strip()
    if "password" in data and data["password"]:
        user.password_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    db.session.commit()
    return jsonify({"success": True})

@app.route("/admin/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True})


# ── Admin: Upload ─────────────────────────────────────────────────────────────
@app.route("/admin/upload", methods=["POST"])
@admin_required
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded", "success": False}), 400
    file = request.files["file"]
    if not file.filename.endswith(".xlsx"):
        return jsonify({"error": "Please upload an .xlsx file", "success": False}), 400
    try:
        df = pd.read_excel(file, engine="openpyxl")
        df.columns = [str(c).strip() for c in df.columns]
        if "Data entry filter owner" not in df.columns:
            return jsonify({"error": "Column 'Data entry filter owner' not found", "success": False}), 400

        session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        review = ReviewSession(
            id=session_id,
            deadline=request.form.get("deadline", ""),
            quarter=request.form.get("quarter", ""),
            created_by=current_user.email,
        )
        db.session.add(review)

        col_map = {
            "Code": "code", "User Name": "user_name",
            "Functional Profile": "functional_profile",
            "Data entry access": "data_entry_access",
            "Manager": "manager", "Département": "departement",
            "Location": "location",
            "Data entry filter owner": "filter_owner",
            "Active BFC": "active_bfc", "Active AD": "active_ad",
        }

        for _, row in df.iterrows():
            known = {}
            for excel_col, db_col in col_map.items():
                val = row.get(excel_col)
                known[db_col] = str(val) if (val is not None and not (isinstance(val, float) and pd.isna(val))) else None
            extra = {
                c: (str(row[c]) if not (isinstance(row[c], float) and pd.isna(row[c])) else None)
                for c in df.columns if c not in col_map
            }
            db.session.add(UserRow(session_id=session_id, **known, extra_data=extra))

        db.session.commit()
        owners_in_file = df["Data entry filter owner"].dropna().unique().tolist()
        return jsonify({
            "success": True,
            "session_id": session_id,
            "total_rows": len(df),
            "owners_in_file": owners_in_file
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e), "success": False}), 500


# ── Admin: Stats & Export ─────────────────────────────────────────────────────
@app.route("/admin/stats")
@admin_required
def admin_stats():
    review = get_active_session()
    if not review:
        return jsonify({"error": "No active session found"}), 404

    # Fetch all rows for the session
    rows = UserRow.query.filter_by(session_id=review.id).all()

    # Group by unique user (code)
    users = {}
    for r in rows:
        users.setdefault(r.code, []).append(r)

    total = len(users)
    validated = 0
    deactivated = 0
    pending = 0

    # Compute global stats per unique user
    for code, u_rows in users.items():
        if all(r.choice == "validate" for r in u_rows):
            validated += 1
        elif all(r.choice == "deactivate" for r in u_rows):
            deactivated += 1
        else:
            pending += 1

    pct = round((validated + deactivated) / total * 100) if total > 0 else 0

    # Now compute stats per filter owner
    owner_users = {}  # owner_key → {code → rows}
    for code, u_rows in users.items():
        owner = u_rows[0].filter_owner
        owner_users.setdefault(owner, {})
        owner_users[owner][code] = u_rows

    # Include delegation data
    delegations = {
        d.owner_key: d.delegate_key
        for d in Delegation.query.filter_by(session_id=review.id).all()
    }

    owners_stats = []
    for owner, u_map in owner_users.items():
        o_total = len(u_map)
        o_valid = 0
        o_deact = 0
        o_pending = 0

        for code, u_rows in u_map.items():
            if all(r.choice == "validate" for r in u_rows):
                o_valid += 1
            elif all(r.choice == "deactivate" for r in u_rows):
                o_deact += 1
            else:
                o_pending += 1

        o_pct = round((o_valid + o_deact) / o_total * 100) if o_total > 0 else 0
        status = (
            "Terminated" if o_pct == 100 else
            "In progress" if o_pct > 0 else
            "Not started"
        )

        # Last validation date among the user’s rows
        last_dt = None
        for _, user_rows in u_map.items():
            for r in user_rows:
                if r.validated_at:
                    last_dt = max(last_dt, r.validated_at) if last_dt else r.validated_at

        owners_stats.append({
            "code": owner,
            "name": owner,
            "pct": o_pct,
            "status": status,
            "last_date": last_dt.strftime("%d/%m/%Y") if last_dt else "",
            "delegation": delegations.get(owner, ""),
            "total": o_total,
            "deactivated": o_deact,
        })

    return jsonify({
        "success": True,
        "total": total,
        "validated": validated,
        "deactivated": deactivated,
        "pending": pending,
        "pct": pct,
        "deadline": review.deadline,
        "quarter": review.quarter,
        "owners_stats": owners_stats,
    })

@app.route("/admin/export")
@admin_required
def admin_export():
    review = get_active_session()
    if not review:
        abort(404)
    rows = UserRow.query.filter_by(session_id=review.id).all()
    data = [{
        "Code": r.code, "User Name": r.user_name,
        "Functional Profile": r.functional_profile,
        "Data entry access": r.data_entry_access,
        "Manager": r.manager, "Département": r.departement,
        "Location": r.location, "Filter Owner": r.filter_owner,
        "Active BFC": r.active_bfc, "Choice": r.choice,
        "Validator": r.validator, "Validated At": r.validated_at
    } for r in rows]
    df       = pd.DataFrame(data)
    deact_df = df[df["Choice"] == "deactivate"].copy()
    output   = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="All Users")
        deact_df.to_excel(writer, index=False, sheet_name="Deactivated")
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name=f"admin_review_{datetime.now().strftime('%Y%m%d')}.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── Filter Owner Routes ───────────────────────────────────────────────────────
@app.route("/my/users")
@owner_required
def get_my_users():
    review = get_active_session()
    if not review:
        return jsonify({"error": "No active review session"}), 404

    owner_key = current_user.owner_key or ""
    delegated_keys = [
        d.owner_key for d in
        Delegation.query.filter_by(session_id=review.id, delegate_key=owner_key).all()
    ]
    keys_to_show = list(set([owner_key] + delegated_keys))

    rows = (UserRow.query
            .filter_by(session_id=review.id)
            .filter(UserRow.filter_owner.in_(keys_to_show))
            .all())

    # One row per unique Code
    seen = {}
    for r in rows:
        if r.code not in seen:
            seen[r.code] = {
                "code": r.code, "user_name": r.user_name,
                "functional_profile": r.functional_profile,
                "data_entry_access": r.data_entry_access,
                "manager": r.manager, "departement": r.departement,
                "location": r.location, "active_bfc": r.active_bfc,
                "choice": r.choice, "line_count": 1,
            }
        else:
            seen[r.code]["line_count"] += 1

    return jsonify({
        "success": True,
        "users": list(seen.values()),
        "deadline": review.deadline,
        "quarter": review.quarter,
    })

@app.route("/my/user/<code>/details")
@owner_required
def get_user_details(code):
    review    = get_active_session()
    owner_key = current_user.owner_key or ""
    delegated_keys = [
        d.owner_key for d in
        Delegation.query.filter_by(session_id=review.id, delegate_key=owner_key).all()
    ]
    keys_to_show = list(set([owner_key] + delegated_keys))

    rows = (UserRow.query
            .filter_by(session_id=review.id, code=code)
            .filter(UserRow.filter_owner.in_(keys_to_show))
            .all())
    if not rows:
        abort(404)

    return jsonify({
        "success": True,
        "code": code,
        "user_name": rows[0].user_name,
        "details": [{
            "id": r.id, "code": r.code, "user_name": r.user_name,
            "functional_profile": r.functional_profile,
            "data_entry_access": r.data_entry_access,
            "manager": r.manager, "departement": r.departement,
            "location": r.location, "active_bfc": r.active_bfc,
            "active_ad": r.active_ad, "choice": r.choice,
            "extra": r.extra_data or {},
        } for r in rows]
    })

@app.route("/my/update_choice", methods=["POST"])
@owner_required
def update_choice():
    data   = request.json
    code   = data.get("code")
    choice = data.get("choice")
    if choice not in ("validate", "deactivate", "pending"):
        return jsonify({"error": "Invalid choice"}), 400

    review    = get_active_session()
    owner_key = current_user.owner_key or ""
    delegated_keys = [
        d.owner_key for d in
        Delegation.query.filter_by(session_id=review.id, delegate_key=owner_key).all()
    ]
    keys_to_show = list(set([owner_key] + delegated_keys))

    rows = (UserRow.query
            .filter_by(session_id=review.id, code=code)
            .filter(UserRow.filter_owner.in_(keys_to_show))
            .all())
    for r in rows:
        r.choice      = choice
        r.validator   = current_user.email
        r.validated_at = datetime.utcnow() if choice != "pending" else None
    db.session.commit()
    return jsonify({"success": True, "updated": len(rows)})

@app.route("/my/signoff", methods=["POST"])
@owner_required
def signoff():
    review    = get_active_session()
    owner_key = current_user.owner_key or ""
    rows      = UserRow.query.filter_by(session_id=review.id, filter_owner=owner_key).all()
    for r in rows:
        r.signoff_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"success": True})
@app.route("/my/stats")
@owner_required
def my_stats():
    review    = get_active_session()
    owner_key = current_user.owner_key or ""

    rows = UserRow.query.filter_by(session_id=review.id, filter_owner=owner_key).all()

    # Group by code (unique user)
    users = {}
    for r in rows:
        users.setdefault(r.code, []).append(r)

    total = len(users)

    validated = 0
    deactivated = 0
    pending = 0

    for code, user_rows in users.items():
        # A user is validated only if ALL rows are validated
        if all(r.choice == "validate" for r in user_rows):
            validated += 1
        # A user is deactivated only if ALL rows are deactivated
        elif all(r.choice == "deactivate" for r in user_rows):
            deactivated += 1
        else:
            pending += 1

    pct = round((validated + deactivated) / total * 100) if total > 0 else 0

    return jsonify({
        "success": True,
        "total": total,
        "validated": validated,
        "deactivated": deactivated,
        "pending": pending,
        "pct": pct,
        "deadline": review.deadline,
    })

@app.route("/my/delegate", methods=["POST"])
@owner_required
def set_delegation():
    data         = request.json
    delegate_key = data.get("delegate_key", "").strip()
    review       = get_active_session()
    owner_key    = current_user.owner_key or ""
    existing = Delegation.query.filter_by(session_id=review.id, owner_key=owner_key).first()
    if existing:
        existing.delegate_key = delegate_key
    else:
        db.session.add(Delegation(session_id=review.id, owner_key=owner_key, delegate_key=delegate_key))
    db.session.commit()
    return jsonify({"success": True})

@app.route("/my/export")
@owner_required
def export_my_data():
    review    = get_active_session()
    owner_key = current_user.owner_key or ""
    rows      = UserRow.query.filter_by(session_id=review.id, filter_owner=owner_key).all()
    data = [{
        "Code": r.code, "User Name": r.user_name,
        "Functional Profile": r.functional_profile,
        "Data entry access": r.data_entry_access,
        "Manager": r.manager, "Département": r.departement,
        "Location": r.location, "Choice": r.choice
    } for r in rows]
    df     = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="My Users")
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name="my_review.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
