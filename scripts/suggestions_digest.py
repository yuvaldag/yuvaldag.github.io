"""Email the site owner new "add a place" suggestions, at most once a day.

Runs from .github/workflows/suggestions-digest.yml. Signs in to Firebase as the owner,
reads suggestions not yet emailed, sends one email if there are any, then marks them
as emailed. Sends nothing when there are no new suggestions.

Environment: FOOD_OWNER_EMAIL, FOOD_OWNER_PASSWORD (the site's owner login),
GMAIL_APP_PASSWORD (a Gmail app password for FOOD_OWNER_EMAIL). --dry-run prints
the email instead of sending it and does not mark anything.
"""
import html, json, os, smtplib, sys, urllib.request, urllib.error
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

API_KEY = "AIzaSyAxtCYRQ-5V4K7QjIDs8NGSwcvei_pXHwY"   # public web key, same as in food/index.html
PROJECT = "food-recommendations-45bee"
DOCS = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents"
SITE = "https://yuvaldag.github.io/food/"


def call(url, body=None, method=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None, headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"{method or 'GET'} {url.split('?')[0]} failed: {e.code} {e.read()[:300]!r}")


def val(f):
    if not f:
        return ""
    for k in ("stringValue", "timestampValue", "booleanValue"):
        if k in f:
            return f[k]
    return ""


def main():
    dry = "--dry-run" in sys.argv
    email, password = os.environ["FOOD_OWNER_EMAIL"], os.environ["FOOD_OWNER_PASSWORD"]
    token = call(f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}",
                 {"email": email, "password": password, "returnSecureToken": True})["idToken"]
    rows = call(DOCS + ":runQuery", {"structuredQuery": {
        "from": [{"collectionId": "suggestions"}],
        "where": {"fieldFilter": {"field": {"fieldPath": "notified"}, "op": "EQUAL", "value": {"booleanValue": False}}}}},
        "POST", token)
    new = [r["document"] for r in rows if "document" in r]
    if not new:
        print("No new suggestions; nothing sent.")
        return
    new.sort(key=lambda d: val(d["fields"].get("created_at")))
    items_txt, items_html = [], []
    for d in new:
        f = d["fields"]
        place, city, why = val(f.get("place")), val(f.get("city")), val(f.get("why"))
        who = val(f.get("name")), val(f.get("email"))
        by = f"{who[0]} <{who[1]}>" if who[0] else who[1]
        faces = {"3": "😋", "2": "🙂", "1": "😐"}
        dishes = []
        for dv in f.get("dishes", {}).get("arrayValue", {}).get("values", []):
            m = dv.get("mapValue", {}).get("fields", {})
            line = f"{faces.get(str(m.get('rating', {}).get('integerValue', '2')), '🙂')} {val(m.get('name'))}"
            if val(m.get("price")):
                line += f" — {val(m.get('price'))}"
            if m.get("hasPhoto", {}).get("booleanValue"):
                line += " (photo)"
            dishes.append(line)
        dish_txt = "".join(f"  Dish: {x}\n" for x in dishes)
        items_txt.append(f"• {place} — {city}\n  {why}\n{dish_txt}  From: {by}\n")
        items_html.append(f"<li><b>{html.escape(place)}</b> — {html.escape(city)}<br>"
                          f"<span style='white-space:pre-wrap'>{html.escape(why)}</span>"
                          + "".join(f"<br>Dish: {html.escape(x)}" for x in dishes) +
                          f"<br><small>From: {html.escape(by)}</small></li>")
    n = len(new)
    subject = f"{n} new place suggestion{'s' if n > 1 else ''} for your food page"
    text = f"{subject}:\n\n" + "\n".join(items_txt) + f"\nSign in at {SITE} → Suggestions to add or dismiss them.\n"
    body = (f"<p>{html.escape(subject)}:</p><ul>{''.join(items_html)}</ul>"
            f"<p>Sign in at <a href='{SITE}'>{SITE}</a> → <b>Suggestions</b> to add or dismiss them.</p>")
    if dry:
        print("DRY RUN — would send:\nSubject:", subject, "\n\n" + text)
        return
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, email, email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(email, os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)
    for d in new:
        call(f"https://firestore.googleapis.com/v1/{d['name']}?updateMask.fieldPaths=notified",
             {"fields": {"notified": {"booleanValue": True}}}, "PATCH", token)
    print(f"Sent 1 email about {n} suggestion(s).")


if __name__ == "__main__":
    main()
