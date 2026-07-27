"""Email service using Resend."""
import html
import httpx
from app.config import settings


def _send(to: str, subject: str, html: str):
    api_key = settings.RESEND_API_KEY if settings.RESEND_API_KEY else settings.SENDGRID_API_KEY
    if not api_key:
        print(f"[EMAIL STUB] To: {to}, Subject: {subject}")
        return

    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            json={
                "from": f"Plus <{settings.FROM_EMAIL}>",
                "to": [to],
                "subject": subject,
                "html": html,
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"[EMAIL] Sent to {to}: {resp.json().get('id', 'ok')}")
        else:
            print(f"[EMAIL ERROR] {to}: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"[EMAIL ERROR] {to}: {e}")


def _wrap(body_content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#141210;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#141210;">
<tr><td align="center" style="padding:48px 20px;">
<table role="presentation" width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;">

<!-- Logo -->
<tr><td style="padding-bottom:32px;">
  <span style="color:#d4b896;font-size:14px;letter-spacing:4px;text-transform:uppercase;">PLUS</span>
</td></tr>

<!-- Content -->
{body_content}

<!-- Footer -->
<tr><td style="padding-top:40px;">
  <table role="presentation" width="100%" style="border-top:1px solid #2a2520;">
  <tr><td style="padding-top:20px;">
    <p style="font-size:11px;line-height:1.6;color:#5a5248;margin:0;">
      Plus, luxury dating
      <br>
      Plus, PO Box 911711, Houston, TX 77291
      <br>
      <a href="{settings.FRONTEND_URL}/settings" style="color:#5a5248;">Email preferences</a>
      &nbsp;&middot;&nbsp;
      <a href="mailto:unsubscribe@meetyourplus.com?subject=Unsubscribe" style="color:#5a5248;">Unsubscribe</a>
      &nbsp;&middot;&nbsp;
      <a href="{settings.FRONTEND_URL}/privacy" style="color:#5a5248;">Privacy</a>
      &nbsp;&middot;&nbsp;
      <a href="{settings.FRONTEND_URL}" style="color:#5a5248;">meetyourplus.com</a>
    </p>
  </td></tr>
  </table>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def _button(url: str, text: str) -> str:
    return f"""<table role="presentation" cellpadding="0" cellspacing="0" style="margin:28px 0;">
<tr><td style="background-color:#d4b896;padding:14px 36px;">
  <a href="{url}" style="color:#141210;text-decoration:none;font-size:14px;font-weight:600;letter-spacing:0.5px;">{text}</a>
</td></tr>
</table>"""


def send_email_verification(to: str, token: str):
    url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Verify your email</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    Welcome to Plus. Tap the button below to verify your email and get started.
  </p>
  {_button(url, "Verify email")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:0;">
    Link expires in 7 days. Didn't create an account? Ignore this email.
  </p>
</td></tr>"""
    _send(to, "Verify your email | Plus", _wrap(body))


def send_password_reset(to: str, reset_token: str):
    url = f"{settings.FRONTEND_URL}/forgot-password?token={reset_token}"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Reset your password</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    We got a request to reset your password. Tap below to choose a new one.
  </p>
  {_button(url, "Reset password")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:0;">
    Expires in 1 hour. Didn't request this? Just ignore it.
  </p>
</td></tr>"""
    _send(to, "Reset your password | Plus", _wrap(body))


def send_new_match(to: str, match_name: str):
    safe_name = html.escape(match_name)
    url = f"{settings.FRONTEND_URL}/messages"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">You matched with {safe_name}</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    You both expressed interest. The conversation is open.
  </p>
  {_button(url, "Say hello")}
</td></tr>"""
    _send(to, f"You matched with {safe_name} | Plus", _wrap(body))


def send_new_message(to: str, sender_name: str):
    safe_name = html.escape(sender_name)
    url = f"{settings.FRONTEND_URL}/messages"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">New message from {safe_name}</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    You have a new message waiting on Plus.
  </p>
  {_button(url, "Read message")}
</td></tr>"""
    _send(to, f"New message from {safe_name} | Plus", _wrap(body))


def send_someone_liked_you(to: str, liker_name: str = "Someone", liker_city: str = ""):
    safe_name = html.escape(liker_name)
    safe_city = html.escape(liker_city) if liker_city else ""
    url = f"{settings.FRONTEND_URL}/likes"
    city_text = f" from {safe_city}" if safe_city else ""
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">{safe_name}{city_text} is interested in you</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    They liked your profile on Plus. Check out their profile and decide if you'd like to connect.
  </p>
  {_button(url, "See who liked you")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:16px 0 0;">
    Profiles with photos and a completed bio get 5x more likes.
  </p>
</td></tr>"""
    _send(to, f"{safe_name} is interested in you | Plus", _wrap(body))


def send_weekly_digest(to: str, display_name: str, new_members: int, likes_received: int, profile_views: int):
    safe_name = html.escape(display_name)
    url = f"{settings.FRONTEND_URL}/discover"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Your week on Plus, {safe_name}</h1>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:20px 0;width:100%;">
    <tr>
      <td style="padding:16px;text-align:center;border:1px solid #2a2520;width:33%;">
        <p style="color:#d4b896;font-size:28px;font-weight:600;margin:0;font-family:Georgia,serif;">{new_members}</p>
        <p style="color:#706860;font-size:11px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">New members</p>
      </td>
      <td style="padding:16px;text-align:center;border:1px solid #2a2520;width:33%;">
        <p style="color:#d4b896;font-size:28px;font-weight:600;margin:0;font-family:Georgia,serif;">{likes_received}</p>
        <p style="color:#706860;font-size:11px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">Likes received</p>
      </td>
      <td style="padding:16px;text-align:center;border:1px solid #2a2520;width:33%;">
        <p style="color:#d4b896;font-size:28px;font-weight:600;margin:0;font-family:Georgia,serif;">{profile_views}</p>
        <p style="color:#706860;font-size:11px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">Profile views</p>
      </td>
    </tr>
  </table>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    New members are joining every day. Browse the latest profiles and make a connection.
  </p>
  {_button(url, "Browse new members")}
</td></tr>"""
    _send(to, f"Your weekly update | Plus", _wrap(body))


def send_add_photos(to: str, display_name: str):
    """Nudge users who have a profile but no photos."""
    url = f"{settings.FRONTEND_URL}/profile"
    safe_name = html.escape(display_name)
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Add a photo, {safe_name}</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Your profile is live but you haven't added any photos yet. Members with photos get <strong style="color:#d4b896;">10x more likes</strong> and are far more likely to receive messages.
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    It takes 30 seconds. One good photo is all you need to start.
  </p>
  {_button(url, "Add a photo")}
</td></tr>"""
    _send(to, f"Add a photo to get noticed | Plus", _wrap(body))


def send_complete_profile(to: str, user_type: str):
    """Email users who signed up but never created a profile."""
    url = f"{settings.FRONTEND_URL}/onboarding"
    if user_type == "sugar":
        headline = "Your profile is 2 minutes away"
        body_text = """
    <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
      You signed up for Plus but haven't created your profile yet. We've made it even simpler — no photo required to get started, and you can browse members immediately.
    </p>
    <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
      Verified, attractive members are joining every day. Your profile takes 2 minutes, and you can start browsing the moment it's live.
    </p>"""
    else:
        headline = "Members are waiting to meet you"
        body_text = """
    <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
      You signed up for Plus but haven't set up your profile yet. It takes 2 minutes, no photo required to get started, and it's completely free for you — always.
    </p>
    <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
      Income-verified sugar daddies are already on the platform. Create your profile and start connecting.
    </p>"""

    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">{headline}</h1>
  {body_text}
  {_button(url, "Complete your profile")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:16px 0 0;">
    Takes 2 minutes. No credit card needed.
  </p>
</td></tr>"""
    _send(to, f"{headline} | Plus", _wrap(body))


def send_profile_incomplete(to: str, display_name: str, missing_items: list[str]):
    """Nudge users whose profile is missing key fields (photo, bio, headline)."""
    safe_name = html.escape(display_name)
    url = f"{settings.FRONTEND_URL}/profile"

    # Build checklist rows
    all_items = {"photo": "Profile photo", "bio": "About me / bio", "headline": "Profile headline"}
    checklist_rows = ""
    for key, label in all_items.items():
        if key in missing_items:
            checklist_rows += f'<tr><td style="padding:6px 0;font-size:14px;color:#a8a090;"><span style="color:#e74c3c;font-weight:600;">&#10007;</span>&nbsp; {label}</td></tr>'
        else:
            checklist_rows += f'<tr><td style="padding:6px 0;font-size:14px;color:#706860;"><span style="color:#22c55e;font-weight:600;">&#10003;</span>&nbsp; {label}</td></tr>'

    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Your profile is almost invisible, {safe_name}</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Members with complete profiles get <strong style="color:#d4b896;">10x more attention</strong>. Here's what's missing:
  </p>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 20px;">
    {checklist_rows}
  </table>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Profiles without photos are shown last in search results. Complete yours to appear higher and get more matches.
  </p>
  {_button(url, "Complete your profile")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:16px 0 0;">
    Takes less than a minute.
  </p>
</td></tr>"""
    _send(to, "Your profile is almost invisible | Plus", _wrap(body))


def send_reengagement(to: str, display_name: str, days_inactive: int):
    url = f"{settings.FRONTEND_URL}/discover"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">We miss you, {display_name}</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    It's been {days_inactive} days since you last visited Plus. New members have joined since you were last here, and some of them might be exactly what you're looking for.
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    Your profile is still live and receiving attention. Come back and see what you've been missing.
  </p>
  {_button(url, "See new profiles")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:16px 0 0;">
    Don't want these emails? <a href="{settings.FRONTEND_URL}/settings?tab=notifications" style="color:#706860;text-decoration:underline;">Update your preferences</a>
  </p>
</td></tr>"""
    _send(to, f"New members waiting for you | Plus", _wrap(body))


def send_admin_new_user(email: str, user_type: str, city: str = "", display_name: str = "", gender: str = "", age: str = ""):
    """Notify admin when a new user signs up or creates a profile."""
    label = "Generous" if user_type == "sugar" else "Attractive"
    safe_name = html.escape(display_name) if display_name else "—"
    safe_city = html.escape(city) if city else "—"
    safe_gender = html.escape(gender) if gender else "—"
    safe_age = html.escape(str(age)) if age else "—"

    rows = f"""
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">Email</td><td style="color:#ede6db;font-size:14px;padding:8px 0;border-bottom:1px solid #2a2520;">{email}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">Type</td><td style="color:#d4b896;font-size:14px;font-weight:600;padding:8px 0;border-bottom:1px solid #2a2520;">{label}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">Name</td><td style="color:#ede6db;font-size:14px;padding:8px 0;border-bottom:1px solid #2a2520;">{safe_name}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">City</td><td style="color:#ede6db;font-size:14px;padding:8px 0;border-bottom:1px solid #2a2520;">{safe_city}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">Gender</td><td style="color:#ede6db;font-size:14px;padding:8px 0;border-bottom:1px solid #2a2520;">{safe_gender}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;">Age</td><td style="color:#ede6db;font-size:14px;padding:8px 0;">{safe_age}</td></tr>"""

    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">New {label} signed up</h1>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:16px 0;width:100%;">
    {rows}
  </table>
  {_button(f"{settings.FRONTEND_URL}/admin", "View in Admin")}
</td></tr>"""
    _send("cmoralestech@gmail.com", f"New {label}: {safe_name} in {safe_city} | Plus", _wrap(body))


def send_admin_new_subscription(email: str, display_name: str, tier: str, city: str = ""):
    """Notify admin when someone subscribes to a paid plan."""
    safe_name = html.escape(display_name) if display_name else email
    safe_city = html.escape(city) if city else "—"
    price = "$99.99/mo" if tier == "diamond" else "$49.99/mo"
    tier_label = tier.capitalize()

    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">New paid subscriber!</h1>
  <div style="background:#1a1714;border:2px solid #d4b896;padding:20px;margin:16px 0;text-align:center;">
    <p style="color:#d4b896;font-size:32px;font-weight:700;margin:0;font-family:Georgia,serif;">{price}</p>
    <p style="color:#ede6db;font-size:16px;margin:8px 0 0;">{tier_label} subscription</p>
  </div>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:16px 0;width:100%;">
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">Name</td><td style="color:#ede6db;font-size:14px;padding:8px 0;border-bottom:1px solid #2a2520;">{safe_name}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">Email</td><td style="color:#ede6db;font-size:14px;padding:8px 0;border-bottom:1px solid #2a2520;">{email}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">City</td><td style="color:#ede6db;font-size:14px;padding:8px 0;border-bottom:1px solid #2a2520;">{safe_city}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;">Plan</td><td style="color:#d4b896;font-size:14px;font-weight:600;padding:8px 0;">{tier_label} — {price}</td></tr>
  </table>
  {_button(f"{settings.FRONTEND_URL}/admin", "View in Admin")}
</td></tr>"""
    _send("cmoralestech@gmail.com", f"New {tier_label} subscriber: {safe_name} ({price}) | Plus", _wrap(body))


def send_contact_form(name: str, email: str, category: str, message: str):
    """Send contact form submission to the support inbox."""
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">New contact form submission</h1>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:16px 0;width:100%;">
    <tr><td style="color:#706860;font-size:12px;padding:6px 0;">From</td><td style="color:#ede6db;font-size:14px;padding:6px 0;">{name} &lt;{email}&gt;</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:6px 0;">Category</td><td style="color:#ede6db;font-size:14px;padding:6px 0;">{category}</td></tr>
  </table>
  <div style="background:#1a1714;border:1px solid #2a2520;padding:16px;margin:16px 0;">
    <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;white-space:pre-wrap;">{message}</p>
  </div>
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:0;">
    Reply directly to this email to respond to the user.
  </p>
</td></tr>"""
    _send("support@meetyourplus.com", f"[{category}] Contact from {name}", _wrap(body))


def send_contact_confirmation(to: str, name: str):
    """Send confirmation email to the user who submitted the contact form."""
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">We got your message, {name}</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    Thanks for reaching out. Our team typically responds within 24 hours, often sooner.
    If your issue is urgent or safety-related, email us directly at
    <a href="mailto:safety@meetyourplus.com" style="color:#d4b896;">safety@meetyourplus.com</a>.
  </p>
</td></tr>"""
    _send(to, "We got your message | Plus", _wrap(body))


def send_newsletter_welcome(to: str):
    """Drip email 1: Sent immediately when someone subscribes via blog."""
    url = f"{settings.FRONTEND_URL}/blog/sugar-dating-for-beginners"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">You're in.</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Thanks for subscribing. We write about sugar dating without the fluff — real advice, real numbers, no fairy tales.
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 4px;">Start with our most popular guides:</p>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:12px 0 24px;">
    <tr><td style="padding:6px 0;font-size:14px;">
      <a href="{settings.FRONTEND_URL}/blog/what-is-private-dating" style="color:#d4b896;text-decoration:underline;">Private Dating Guide: What To Expect</a>
    </td></tr>
    <tr><td style="padding:6px 0;font-size:14px;">
      <a href="{settings.FRONTEND_URL}/blog/best-dating-apps-miami-2026" style="color:#d4b896;text-decoration:underline;">Best Verified Dating Apps 2026</a>
    </td></tr>
    <tr><td style="padding:6px 0;font-size:14px;">
      <a href="{settings.FRONTEND_URL}/blog/sugar-dating-scams" style="color:#d4b896;text-decoration:underline;">How to Spot Sugar Dating Scams</a>
    </td></tr>
  </table>
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:0;">
    We'll send you one more email in a few days with a side-by-side comparison of every platform. That's it — no spam.
  </p>
</td></tr>"""
    _send(to, "You're in | Plus", _wrap(body))


def send_newsletter_drip_comparison(to: str):
    """Drip email 2: Sent 3 days after subscribe. Platform comparison."""
    url = f"{settings.FRONTEND_URL}/alternatives"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Seeking vs Plus vs the rest</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    You subscribed a few days ago, so you're probably weighing your options. Here's the honest breakdown:
  </p>
  <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;margin:20px 0;font-size:13px;">
    <tr style="border-bottom:1px solid #2a2520;">
      <td style="color:#706860;padding:10px 8px;"></td>
      <td style="color:#706860;padding:10px 8px;">Price</td>
      <td style="color:#706860;padding:10px 8px;">Verified</td>
      <td style="color:#706860;padding:10px 8px;">Bots</td>
    </tr>
    <tr style="border-bottom:1px solid #2a2520;">
      <td style="color:#a8a090;padding:10px 8px;">Seeking</td>
      <td style="color:#a8a090;padding:10px 8px;">$150/mo</td>
      <td style="color:#a8a090;padding:10px 8px;">Optional</td>
      <td style="color:#a8a090;padding:10px 8px;">High</td>
    </tr>
    <tr style="border-bottom:1px solid #2a2520;">
      <td style="color:#d4b896;padding:10px 8px;font-weight:600;">Plus</td>
      <td style="color:#d4b896;padding:10px 8px;">$49.99/mo</td>
      <td style="color:#d4b896;padding:10px 8px;">Required</td>
      <td style="color:#d4b896;padding:10px 8px;">None</td>
    </tr>
    <tr>
      <td style="color:#a8a090;padding:10px 8px;">Secret Benefits</td>
      <td style="color:#a8a090;padding:10px 8px;">Credits</td>
      <td style="color:#a8a090;padding:10px 8px;">No</td>
      <td style="color:#a8a090;padding:10px 8px;">Medium</td>
    </tr>
  </table>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Attractive members join Plus for free — always. If you're on the generous side, it's $49.99/month with no credits, no hidden fees, and every profile is verified.
  </p>
  {_button(f"{settings.FRONTEND_URL}/auth?mode=register", "Create your free profile")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:16px 0 0;">
    <a href="{url}" style="color:#706860;text-decoration:underline;">Read the full comparison →</a>
  </p>
</td></tr>"""
    _send(to, "Seeking vs Plus: honest comparison | Plus", _wrap(body))


def send_newsletter_drip_cta(to: str):
    """Drip email 3: Sent 7 days after subscribe. Final nudge."""
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">One last thing</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    You've been reading our guides for about a week now. If you're still on the fence about trying sugar dating, here's what we'd say:
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Creating a profile takes two minutes. It costs nothing. You can browse, see who's in your city, and decide if it's for you — without paying a cent or uploading a photo.
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    No pressure. No sales pitch. Just a platform built by people who thought sugar dating deserved something better than Seeking Arrangement.
  </p>
  {_button(f"{settings.FRONTEND_URL}/auth?mode=register", "See who's near you")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:16px 0 0;">
    This is the last email in our welcome series. You'll only get occasional updates from here — unsubscribe anytime.
  </p>
</td></tr>"""
    _send(to, "See who's in your city | Plus", _wrap(body))


def send_profile_viewed(to: str, display_name: str, viewer_city: str = ""):
    safe_name = html.escape(display_name)
    safe_city = html.escape(viewer_city) if viewer_city else "your area"
    url = f"{settings.FRONTEND_URL}/likes"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Someone viewed your profile</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    A member from {safe_city} just viewed your profile. Verified members are checking you out.
  </p>
  {_button(url, "See who's interested")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:16px 0 0;">
    Profiles with verified photos get 3x more views.
  </p>
</td></tr>"""
    _send(to, "Someone viewed your profile | Plus", _wrap(body))


def send_welcome(to: str, display_name: str):
    url = f"{settings.FRONTEND_URL}/discover"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Welcome, {display_name}</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Your profile is live. Three things to do first:
  </p>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0;">
    <tr><td style="padding:6px 0;color:#a8a090;font-size:14px;">
      <span style="color:#d4b896;font-weight:600;">1.</span>&nbsp; Add photos
    </td></tr>
    <tr><td style="padding:6px 0;color:#a8a090;font-size:14px;">
      <span style="color:#d4b896;font-weight:600;">2.</span>&nbsp; Complete your profile
    </td></tr>
    <tr><td style="padding:6px 0;color:#a8a090;font-size:14px;">
      <span style="color:#d4b896;font-weight:600;">3.</span>&nbsp; Browse and message someone
    </td></tr>
  </table>
  {_button(url, "Start browsing")}
</td></tr>"""
    _send(to, f"Welcome to Plus, {display_name}", _wrap(body))


def send_new_members_digest(to: str, display_name: str, new_members_count: int, member_previews: list[dict]):
    """Weekly digest showing new members who joined. Only for paying SDs."""
    safe_name = html.escape(display_name)
    url = f"{settings.FRONTEND_URL}/discover"

    # Build member preview rows
    preview_rows = ""
    for m in member_previews[:5]:
        name = html.escape(m.get("name", ""))
        age = m.get("age", "")
        city = html.escape(m.get("city", ""))
        preview_rows += f"""<tr>
          <td style="padding:10px 8px;color:#ede6db;font-size:14px;border-bottom:1px solid #2a2520;">{name}</td>
          <td style="padding:10px 8px;color:#a8a090;font-size:14px;border-bottom:1px solid #2a2520;">{age}</td>
          <td style="padding:10px 8px;color:#a8a090;font-size:14px;border-bottom:1px solid #2a2520;">{city}</td>
        </tr>"""

    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">{new_members_count} new members joined this week</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Here's a preview of who's new on Plus, {safe_name}.
  </p>
  <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;margin:20px 0;font-size:13px;">
    <tr>
      <td style="color:#706860;padding:10px 8px;border-bottom:1px solid #2a2520;text-transform:uppercase;letter-spacing:1px;font-size:11px;">Name</td>
      <td style="color:#706860;padding:10px 8px;border-bottom:1px solid #2a2520;text-transform:uppercase;letter-spacing:1px;font-size:11px;">Age</td>
      <td style="color:#706860;padding:10px 8px;border-bottom:1px solid #2a2520;text-transform:uppercase;letter-spacing:1px;font-size:11px;">City</td>
    </tr>
    {preview_rows}
  </table>
  {_button(url, "Browse new members")}
</td></tr>"""
    _send(to, f"{new_members_count} new members joined this week | Plus", _wrap(body))


def send_weekly_stats(to: str, display_name: str, profile_views: int, likes_received: int, search_appearances: int):
    """Weekly activity stats for paying SDs."""
    safe_name = html.escape(display_name)
    url = f"{settings.FRONTEND_URL}/likes"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Your week on Plus, {safe_name}</h1>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:20px 0;width:100%;">
    <tr>
      <td style="padding:16px;text-align:center;border:1px solid #2a2520;width:33%;">
        <p style="color:#d4b896;font-size:28px;font-weight:600;margin:0;font-family:Georgia,serif;">{profile_views}</p>
        <p style="color:#706860;font-size:11px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">Profile views</p>
      </td>
      <td style="padding:16px;text-align:center;border:1px solid #2a2520;width:33%;">
        <p style="color:#d4b896;font-size:28px;font-weight:600;margin:0;font-family:Georgia,serif;">{likes_received}</p>
        <p style="color:#706860;font-size:11px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">Likes received</p>
      </td>
      <td style="padding:16px;text-align:center;border:1px solid #2a2520;width:33%;">
        <p style="color:#d4b896;font-size:28px;font-weight:600;margin:0;font-family:Georgia,serif;">{search_appearances}</p>
        <p style="color:#706860;font-size:11px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">Search appearances</p>
      </td>
    </tr>
  </table>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    Members are checking out your profile. See who's interested and make a connection.
  </p>
  {_button(url, "See who liked you")}
</td></tr>"""
    _send(to, f"Your week on Plus, {safe_name} | Plus", _wrap(body))


def send_discount_offer(to: str, display_name: str, coupon_url: str):
    """Email users who browsed but didn't convert — 25% first-month discount."""
    safe_name = html.escape(display_name)
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Still thinking about it, {safe_name}?</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    We noticed you browsed some great profiles but haven't unlocked full access yet.
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Here's 25% off your first month &mdash; <strong style="color:#d4b896;">$74.99 instead of $99.99.</strong>
  </p>
  {_button(coupon_url, "Claim 25% off")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:16px 0 0;">
    Offer expires in 48 hours.
  </p>
</td></tr>"""
    _send(to, "25% off your first month | Plus", _wrap(body))


def send_abandoned_checkout(to: str, display_name: str):
    """Email sugar daddies who started checkout but didn't complete it."""
    safe_name = html.escape(display_name)
    url = f"{settings.FRONTEND_URL}/settings?tab=subscription"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">You were almost there, {safe_name}</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    You started setting up your Plus account but didn't finish.
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Your profile is live and members are already seeing it. Unlock full access to start messaging and see unblurred photos.
  </p>
  <ul style="margin:0 0 20px;padding:0 0 0 18px;">
    <li style="color:#a8a090;font-size:14px;line-height:2;">See all photos</li>
    <li style="color:#a8a090;font-size:14px;line-height:2;">Unlimited messaging</li>
    <li style="color:#a8a090;font-size:14px;line-height:2;">See who liked you</li>
  </ul>
  {_button(url, "Complete your upgrade")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:16px 0 0;">
    Cancel anytime. No commitment.
  </p>
</td></tr>"""
    _send(to, "You were almost there | Plus", _wrap(body))


def send_referral_prompt(to: str, display_name: str, referral_code: str):
    """Sent to new paying subscribers to encourage referrals."""
    safe_name = html.escape(display_name)
    referral_url = f"{settings.FRONTEND_URL}/?ref={referral_code}"
    referrals_page = f"{settings.FRONTEND_URL}/referrals"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Earn recurring income for every friend who subscribes</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Know another successful man who'd appreciate Plus, {safe_name}?
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Share your personal referral link and earn <strong style="color:#d4b896;">$5-25/month per referral depending on your tier</strong>. No cap, recurring. See <a href="{settings.FRONTEND_URL}/earn" style="color:#d4b896;">meetyourplus.com/earn</a> for tier details.
  </p>
  <div style="background:#1a1714;border:2px solid #d4b896;padding:16px;margin:20px 0;text-align:center;">
    <p style="color:#706860;font-size:11px;margin:0 0 8px;text-transform:uppercase;letter-spacing:1px;">Your referral link</p>
    <a href="{referral_url}" style="color:#d4b896;font-size:16px;font-weight:600;text-decoration:none;word-break:break-all;">{referral_url}</a>
  </div>
  {_button(referrals_page, "Copy your referral link")}
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    Starter tier: $5/month per Plus referral, $10/month per Plus+ referral. Rates increase as you refer more. <a href="{settings.FRONTEND_URL}/earn" style="color:#d4b896;">See all tiers</a>.
  </p>
</td></tr>"""
    _send(to, f"Earn recurring income for every friend who subscribes | Plus", _wrap(body))


def send_admin_churn_alert(admin_email: str, user_email: str, display_name: str, city: str, days_inactive: int, tier: str):
    """Alert admin about a paying subscriber who hasn't been active."""
    safe_name = html.escape(display_name) if display_name else user_email
    safe_city = html.escape(city) if city else "Unknown"
    tier_label = tier.capitalize() if tier else "Unknown"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Paying subscriber inactive</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    A paying subscriber hasn't logged in for {days_inactive} days. They may churn.
  </p>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:16px 0;width:100%;">
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">Name</td><td style="color:#ede6db;font-size:14px;padding:8px 0;border-bottom:1px solid #2a2520;">{safe_name}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">Email</td><td style="color:#ede6db;font-size:14px;padding:8px 0;border-bottom:1px solid #2a2520;">{user_email}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">City</td><td style="color:#ede6db;font-size:14px;padding:8px 0;border-bottom:1px solid #2a2520;">{safe_city}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;border-bottom:1px solid #2a2520;">Tier</td><td style="color:#d4b896;font-size:14px;font-weight:600;padding:8px 0;border-bottom:1px solid #2a2520;">{tier_label}</td></tr>
    <tr><td style="color:#706860;font-size:12px;padding:8px 0;">Days inactive</td><td style="color:#ede6db;font-size:14px;font-weight:600;padding:8px 0;">{days_inactive}</td></tr>
  </table>
</td></tr>"""
    _send(admin_email, f"\u26a0 Paying subscriber inactive: {safe_name} ({days_inactive} days) | Plus", _wrap(body))


def send_weekly_revenue_report(to: str, mrr: float, new_subs: int, new_signups: int, cancellations: int, top_sources: list[dict], total_profiles: int, total_events: int):
    """Weekly revenue and metrics report for admin."""
    sources_html = ""
    for i, src in enumerate(top_sources[:3], 1):
        source_name = html.escape(str(src.get("source", "Unknown")))
        count = src.get("count", 0)
        sources_html += f'<tr><td style="color:#ede6db;font-size:14px;padding:6px 0;border-bottom:1px solid #2a2520;">{i}. {source_name}</td><td style="color:#d4b896;font-size:14px;padding:6px 0;border-bottom:1px solid #2a2520;text-align:right;">{count}</td></tr>'

    if not sources_html:
        sources_html = '<tr><td style="color:#706860;font-size:14px;padding:6px 0;">No referrer data this week</td></tr>'

    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Weekly Revenue Report</h1>

  <div style="background:#1a1714;border:2px solid #d4b896;padding:20px;margin:16px 0;text-align:center;">
    <p style="color:#d4b896;font-size:36px;font-weight:700;margin:0;font-family:Georgia,serif;">${mrr:,.2f}</p>
    <p style="color:#706860;font-size:11px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">Monthly Recurring Revenue</p>
  </div>

  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:20px 0;width:100%;">
    <tr>
      <td style="padding:16px;text-align:center;border:1px solid #2a2520;width:25%;">
        <p style="color:#d4b896;font-size:24px;font-weight:600;margin:0;font-family:Georgia,serif;">{new_subs}</p>
        <p style="color:#706860;font-size:10px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">New subs</p>
      </td>
      <td style="padding:16px;text-align:center;border:1px solid #2a2520;width:25%;">
        <p style="color:#d4b896;font-size:24px;font-weight:600;margin:0;font-family:Georgia,serif;">{new_signups}</p>
        <p style="color:#706860;font-size:10px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">New signups</p>
      </td>
      <td style="padding:16px;text-align:center;border:1px solid #2a2520;width:25%;">
        <p style="color:#d4b896;font-size:24px;font-weight:600;margin:0;font-family:Georgia,serif;">{cancellations}</p>
        <p style="color:#706860;font-size:10px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">Cancellations</p>
      </td>
      <td style="padding:16px;text-align:center;border:1px solid #2a2520;width:25%;">
        <p style="color:#d4b896;font-size:24px;font-weight:600;margin:0;font-family:Georgia,serif;">{total_profiles}</p>
        <p style="color:#706860;font-size:10px;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">Total profiles</p>
      </td>
    </tr>
  </table>

  <h2 style="color:#ede6db;font-size:16px;font-weight:400;margin:24px 0 8px;font-family:Georgia,serif;">Top signup sources</h2>
  <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 16px;width:100%;">
    {sources_html}
  </table>

  <p style="color:#706860;font-size:12px;margin:16px 0 0;">
    Total funnel events this week: {total_events}
  </p>
</td></tr>"""
    _send(to, f"Weekly report: ${mrr:,.0f} MRR, {new_subs} new subs | Plus", _wrap(body))


def send_sd_day1_boost(to: str, display_name: str):
    """Day 1 onboarding: profile boost notification for new paying SDs."""
    safe_name = html.escape(display_name)
    url = f"{settings.FRONTEND_URL}/discover"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Your profile is boosted for 24 hours</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Welcome, {safe_name}. As a new member, your profile is getting priority placement in Discover right now. Verified members are seeing your profile as we speak.
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    Make sure your profile and photos are looking their best — first impressions matter.
  </p>
  {_button(url, "Browse members")}
</td></tr>"""
    _send(to, "Your profile is boosted for 24 hours | Plus", _wrap(body))


def send_sd_day3_activity(to: str, display_name: str, likes_count: int):
    """Day 3 onboarding: early activity summary for new paying SDs."""
    safe_name = html.escape(display_name)
    url = f"{settings.FRONTEND_URL}/likes"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">{likes_count} members have shown interest in your profile</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    You've been on Plus for a few days now, {safe_name}, and people are noticing. Check out who's been interested in your profile and start a conversation.
  </p>
  {_button(url, "See who's interested")}
  <p style="color:#706860;font-size:12px;line-height:1.6;margin:16px 0 0;">
    Tip: Members who send the first message get 3x more responses.
  </p>
</td></tr>"""
    _send(to, f"{likes_count} members have shown interest | Plus", _wrap(body))


def send_sb_invite_sd(to: str, display_name: str, referral_code: str):
    """Invite SBs to refer sugar daddies. Aggressive commission offer."""
    safe_name = html.escape(display_name)
    referral_url = f"{settings.FRONTEND_URL}/r/{referral_code}"
    referrals_page = f"{settings.FRONTEND_URL}/earn"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Earn recurring income from referrals</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    {safe_name}, here's something most sugar babies don't know about.
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Every successful man you refer to Plus earns you <strong style="color:#d4b896;">$5/month at the Starter tier, every month, for as long as they subscribe.</strong> That's not a one-time bonus. It's recurring income, and rates increase as you refer more.
  </p>

  <div style="background:#1a1714;border:2px solid #d4b896;padding:20px;margin:20px 0;">
    <p style="color:#ede6db;font-size:16px;font-weight:600;margin:0 0 16px;font-family:Georgia,serif;">The math (Starter tier):</p>
    <table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;font-size:14px;">
      <tr><td style="color:#a8a090;padding:6px 0;">Refer 1 man</td><td style="color:#d4b896;font-weight:600;text-align:right;padding:6px 0;">$5/month</td></tr>
      <tr><td style="color:#a8a090;padding:6px 0;">Refer 5 men</td><td style="color:#d4b896;font-weight:600;text-align:right;padding:6px 0;">$25/month</td></tr>
      <tr><td style="color:#a8a090;padding:6px 0;">Refer 10 men</td><td style="color:#d4b896;font-weight:600;text-align:right;padding:6px 0;">$50/month</td></tr>
      <tr><td style="color:#ede6db;padding:8px 0;border-top:1px solid #2a2520;font-weight:600;">Refer 25+ men</td><td style="color:#d4b896;font-weight:700;text-align:right;padding:8px 0;border-top:1px solid #2a2520;font-size:18px;">Higher tiers unlock</td></tr>
    </table>
    <p style="color:#706860;font-size:12px;margin:12px 0 0;">No cap. Rates increase with more referrals. <a href="{settings.FRONTEND_URL}/earn" style="color:#706860;text-decoration:underline;">See all tiers</a>.</p>
  </div>

  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    Think about every wealthy man you've met on other platforms, at events, through friends. Your ex-SD. Your friend's boss. That guy in your DMs. Each one earns you recurring monthly income if they join Plus.
  </p>

  <div style="background:#1a1714;border:2px solid #d4b896;padding:16px;margin:20px 0;text-align:center;">
    <p style="color:#706860;font-size:11px;margin:0 0 8px;text-transform:uppercase;letter-spacing:1px;">Your personal referral link</p>
    <a href="{referral_url}" style="color:#d4b896;font-size:16px;font-weight:600;text-decoration:none;word-break:break-all;">{referral_url}</a>
  </div>

  {_button(referrals_page, "See how much you can earn")}

  <p style="color:#a8a090;font-size:13px;line-height:1.7;margin:16px 0 0;">
    <strong style="color:#ede6db;">How it works:</strong> Share your link &rarr; He signs up &rarr; He subscribes &rarr; You earn $5-32/month per subscriber depending on your tier. Track your earnings at meetyourplus.com/earn.
  </p>
</td></tr>"""
    _send(to, f"Earn recurring income from referrals | Plus", _wrap(body))


def send_sd_day7_recap(to: str, display_name: str, new_members_count: int):
    """Day 7 onboarding: first week recap for new paying SDs."""
    safe_name = html.escape(display_name)
    url = f"{settings.FRONTEND_URL}/discover"
    body = f"""
<tr><td>
  <h1 style="color:#ede6db;font-size:22px;font-weight:400;margin:0 0 12px;font-family:Georgia,serif;">Your first week on Plus</h1>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0 0 20px;">
    It's been a week since you joined, {safe_name}. In that time, {new_members_count} new members have joined the platform. Here's who's new.
  </p>
  <p style="color:#a8a090;font-size:14px;line-height:1.7;margin:0;">
    New members join every day. Browse the latest profiles and find your match.
  </p>
  {_button(url, "See who's new")}
</td></tr>"""
    _send(to, f"Your first week: {new_members_count} new members joined | Plus", _wrap(body))
