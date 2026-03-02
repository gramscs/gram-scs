from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from app.models import Consignment
from app import cache, mail
from flask_mail import Message
import os
import json
from datetime import datetime


main_bp = Blueprint(
    "main",
    __name__,
    template_folder="templates"
)


# ----------------------------
# HOME
# ----------------------------
@main_bp.route("/")
@cache.cached(timeout=300)
def index():
    return render_template("main/index.html")


# ----------------------------
# TRACK
# ----------------------------
@main_bp.route("/track", methods=["GET", "POST"])
def track():
    consignment = None

    if request.method == "POST":
        number = request.form.get("consignment_number")

        if number:
            consignment = Consignment.query.filter_by(
                consignment_number=number.strip()
            ).first()

    return render_template("main/track.html", consignment=consignment)


# ----------------------------
# ABOUT
# ----------------------------
@main_bp.route("/about")
@cache.cached(timeout=300)
def about():
    return render_template("main/about.html")


# ----------------------------
# CONTACT
# ----------------------------
@main_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
    
        # Send Email
        try:
            msg = Message(
                subject=f"New Contact: {subject or 'No Subject'}",
                sender=email,
                recipients=["yourgmail@gmail.com"]
            )

            msg.body = f"""
Name: {name}
Email: {email}

Message:
{message}
"""
            mail.send(msg)

        except Exception as e:
            print("Email error:", e)

        # Save locally (optional backup)
        entry = {
            'name': name,
            'email': email,
            'subject': subject,
            'message': message,
            'received_at': datetime.utcnow().isoformat() + 'Z'
        }

        storage_dir = os.path.join(os.getcwd(), 'storage')
        os.makedirs(storage_dir, exist_ok=True)
        submissions_file = os.path.join(storage_dir, 'contact_submissions.jsonl')
        try:
            with open(submissions_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

        flash("Message sent successfully!")
        return redirect(url_for("main.contact"))

    return render_template("main/contact.html")


# ----------------------------
# NEWSLETTER
# ----------------------------
@main_bp.route('/subscribe-newsletter', methods=['POST'])
def subscribe_newsletter():
    email = request.form.get('email') or (request.get_json(silent=True) or {}).get('email')

    if not email:
        return jsonify({'success': False, 'message': 'Email required'}), 400

    storage_dir = os.path.join(os.getcwd(), 'storage')
    os.makedirs(storage_dir, exist_ok=True)
    subs_file = os.path.join(storage_dir, 'newsletter_subscribers.jsonl')

    entry = {
        'email': email,
        'subscribed_at': datetime.utcnow().isoformat() + 'Z'
    }

    try:
        with open(subs_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        return jsonify({'success': False, 'message': 'Could not save subscription'}), 500

    return jsonify({'success': True, 'message': 'Subscribed successfully'})