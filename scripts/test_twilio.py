"""
scripts/test_twilio.py
──────────────────────
Direct diagnostic utility for testing Twilio SMS & Call integration.
Run via:
    python scripts/test_twilio.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

print("=" * 60)
print("ADERS — Twilio Integration Diagnostic Tool")
print("=" * 60)

# 1. Check Python package
try:
    from twilio.rest import Client as TwilioClient
    from twilio.base.exceptions import TwilioRestException
    print("✅ twilio package is installed.")
except ImportError:
    print("❌ twilio package is NOT installed.")
    print("   Please run: pip install twilio")
    sys.exit(1)

# 2. Check environment credentials
sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
from_num = os.getenv("TWILIO_FROM_NUMBER", "").strip()

print("\nChecking .env configuration:")
print(f"  • TWILIO_ACCOUNT_SID : {'✅ Configured (' + sid[:6] + '...' + sid[-4:] + ')' if sid else '❌ MISSING'}")
print(f"  • TWILIO_AUTH_TOKEN  : {'✅ Configured (Length: ' + str(len(token)) + ')' if token else '❌ MISSING'}")
print(f"  • TWILIO_FROM_NUMBER : {from_num if from_num else '❌ MISSING'}")

if not (sid and token and from_num):
    print("\n❌ Error: Please ensure TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER are in .env")
    sys.exit(1)

# 3. Test API Authentication
print("\nConnecting to Twilio REST API...")
try:
    client = TwilioClient(sid, token)
    account = client.api.accounts(sid).fetch()
    print(f"✅ Authenticated successfully!")
    print(f"  • Account Name   : {account.friendly_name}")
    print(f"  • Account Status : {account.status}")
    print(f"  • Account Type   : {account.type}")
except Exception as e:
    print(f"❌ Twilio Authentication Failed: {e}")
    sys.exit(1)

# 4. Check Contacts
from alerts.contact_manager import get_contacts
contacts = get_contacts("major")

print(f"\nConfigured Emergency Contacts ({len(contacts)} active):")
if not contacts:
    print("  ⚠️ No active contacts found! Check your CONTACT_*_PHONE values in .env")
for c in contacts:
    print(f"  • {c['name']} ({c['role']}) : {c['phone']} [SMS: {c['receive_sms']}, Call: {c['receive_call']}]")

if not contacts:
    sys.exit(0)

# 5. Test Options
print("\n" + "=" * 60)
print("Select Twilio Test Mode:")
print("  1. 📞 Test Voice Call (Recommended for Trial accounts - No template restrictions)")
print("  2. 💬 Test SMS (May require upgraded account or pre-approved templates on Trial)")
choice = input("Enter choice (1 or 2) [default: 1]: ").strip() or "1"

print(f"\nDefault contact from .env: {contacts[0]['name']} ({contacts[0]['phone']})")
user_input = input("Press ENTER to use this number, or type your verified phone number (e.g. +91XXXXXXXXXX): ").strip()
target_phone = user_input if user_input else contacts[0]["phone"]

if choice == "1":
    print(f"\n📞 Placing an automated emergency voice call to: {target_phone}...")
    voice_url = os.getenv("TWILIO_TWIML_BIN_URL", "").strip() or "https://demo.twilio.com/welcome/voice/"
    print(f"  • Using Voice URL: {voice_url}")

    try:
        # Use url parameter for trial account compatibility
        call = client.calls.create(
            url=voice_url,
            from_=from_num,
            to=target_phone,
        )
        print(f"\n🎉 Emergency Voice Call placed successfully!")
        print(f"  • Call SID    : {call.sid}")
        print(f"  • Call Status : {call.status}")
        print(f"  • Destination : {target_phone}")
        print("\n👉 Answer the incoming phone call on your mobile to hear the alert!")
    except TwilioRestException as e:
        print(f"\n❌ Call Failed:")
        print(f"  • Error Code : {e.code}")
        print(f"  • Message    : {e.msg}")
        if "disallowed parameters" in str(e).lower() or e.code == 0:
            print("\n💡 Twilio Trial Tip: Trial accounts require a hosted TwiML URL instead of inline XML.")
            print("   You can create a free custom message TwiML Bin in Twilio Console:")
            print("   1. Go to: https://console.twilio.com/us1/develop/voice/twiml-bins")
            print("   2. Click 'Create TwiML Bin' and paste your speech text")
            print("   3. Copy its URL into .env as TWILIO_TWIML_BIN_URL=...")
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")

else:
    print(f"\n💬 Attempting to send SMS to: {target_phone}...")
    test_body = (
        "[ADERS ALERT TEST] 🚨 AI Accident Detection & Emergency Response System.\n"
        "Twilio integration verified successfully! Alerts are operational."
    )
    try:
        msg = client.messages.create(
            body=test_body,
            from_=from_num,
            to=target_phone,
        )
        print(f"\n🎉 SMS sent successfully!")
        print(f"  • Message SID : {msg.sid}")
        print(f"  • Status      : {msg.status}")
        print(f"  • Sent To     : {target_phone}")
    except TwilioRestException as e:
        print(f"\n❌ Failed to send SMS:")
        print(f"  • Twilio Error Code : {e.code}")
        print(f"  • Message           : {e.msg}")
        if e.code == 572006:
            print("\n💡 REASON: Twilio Trial Account Restriction (Error 572006)")
            print("   Twilio restricts new Trial accounts from sending custom freeform SMS text.")
            print("   👉 Solutions:")
            print("      1. Use Emergency Voice Calls (Option 1 above), which work on Trial accounts!")
            print("      2. Upgrade your Twilio account by adding funds ($10) to unlock unrestricted custom SMS.")
        elif e.code in (21608, 572002):
            print("\n💡 REASON: This exact phone number is NOT in your Twilio Verified Caller IDs!")
            print("   👉 Verify it at: https://console.twilio.com/us1/develop/phone-numbers/manage/verified")
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")

print("=" * 60)

