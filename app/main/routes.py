from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from app import cache, mail
from flask_mail import Message
import os
import json
import logging
import re
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)


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
        try:
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            subject = request.form.get('subject', '').strip()
            message = request.form.get('message', '').strip()
            
            # Validate inputs
            if not name or not email or not message:
                flash("Please fill in all required fields.", "error")
                return render_template("main/contact.html")
            
            # Validate email format
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                flash("Please enter a valid email address.", "error")
                return render_template("main/contact.html")
            
            # Send Email
            email_sent = False
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
                email_sent = True
                logger.info(f"Contact email sent from {email}")

            except Exception as e:
                logger.error(f"Email sending failed: {e}")
                # Continue to save locally even if email fails

            # Save locally (backup)
            entry = {
                'name': name,
                'email': email,
                'subject': subject,
                'message': message,
                'received_at': datetime.utcnow().isoformat() + 'Z',
                'email_sent': email_sent
            }

            try:
                storage_dir = os.path.join(os.getcwd(), 'storage')
                os.makedirs(storage_dir, exist_ok=True)
                submissions_file = os.path.join(storage_dir, 'contact_submissions.jsonl')
                
                with open(submissions_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry) + "\n")
                logger.info(f"Contact form saved locally for {email}")
            except IOError as e:
                logger.error(f"Failed to save contact form locally: {e}")
                if not email_sent:
                    flash("There was an issue submitting your message. Please try again.", "error")
                    return render_template("main/contact.html")

            flash("Message sent successfully! We'll get back to you soon.", "success")
            return redirect(url_for("main.contact"))
            
        except Exception as e:
            logger.error(f"Unexpected error in contact form: {e}")
            flash("An unexpected error occurred. Please try again later.", "error")
            return render_template("main/contact.html")

    return render_template("main/contact.html")


# ----------------------------
# NEWSLETTER
# ----------------------------
@main_bp.route('/subscribe-newsletter', methods=['POST'])
def subscribe_newsletter():
    try:
        email = request.form.get('email') or (request.get_json(silent=True) or {}).get('email')

        if not email or not email.strip():
            return jsonify({'success': False, 'message': 'Email address is required'}), 400
        
        email = email.strip().lower()
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'}), 400

        entry = {
            'email': email,
            'subscribed_at': datetime.utcnow().isoformat() + 'Z'
        }

        try:
            storage_dir = os.path.join(os.getcwd(), 'storage')
            os.makedirs(storage_dir, exist_ok=True)
            subs_file = os.path.join(storage_dir, 'newsletter_subscribers.jsonl')
            
            with open(subs_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
            
            logger.info(f"Newsletter subscription: {email}")
            return jsonify({'success': True, 'message': 'Successfully subscribed to newsletter'})
            
        except IOError as e:
            logger.error(f"Failed to save newsletter subscription: {e}")
            return jsonify({'success': False, 'message': 'Unable to process subscription. Please try again later.'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in newsletter subscription: {e}")
        return jsonify({'success': False, 'message': 'An unexpected error occurred'}), 500

