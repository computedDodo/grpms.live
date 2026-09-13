# emergency_reset.py
# Run on PythonAnywhere console: python3 emergency_reset.py
#current pass is cyberdodo:6ix9ine3ryyes

sys.path.insert(0, '/home/CyberDodoo/grpms_v2')
os.environ['FLASK_APP'] = 'run.py'
os.chdir('/home/CyberDodoo/grpms_v2')

from dotenv import load_dotenv
load_dotenv('.env')

from app import create_app, db
from app.models import User

app = create_app()
with app.app_context():
    admins = User.query.filter_by(role='PlatformAdmin').all()
    print("PlatformAdmin accounts found:")
    for a in admins:
        print(f"  ID:{a.id}  Username:{a.username}")

    username = input("\nEnter username to reset: ").strip()
    new_pwd  = input("Enter new password (min 8 chars): ").strip()

    if len(new_pwd) < 8:
        print("Too short. Aborted.")
        sys.exit(1)

    u = User.query.filter_by(username=username, role='PlatformAdmin').first()
    if not u:
        print("Not found. Aborted.")
        sys.exit(1)

    u.set_password(new_pwd)
    db.session.commit()
    print(f"Done — password reset for @{u.username}")
