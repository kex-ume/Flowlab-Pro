"""Explicit administrator credential links; independent technical personnel remain intact."""
from pathlib import Path
import sys
from urllib.parse import urlparse, unquote
from app.database import database


def shared_database():
    try:
        from django.apps import apps
    except ImportError:
        return False
    if not apps.ready:
        return False
    from django.conf import settings
    config = settings.DATABASES['default']
    if database.database_backend() == 'sqlite':
        return config['ENGINE'].endswith('sqlite3') and str(config['NAME']) != ':memory:' and Path(config['NAME']).resolve() == database.DATABASE_PATH.resolve()
    parsed = urlparse(database.database_url())
    return config['ENGINE'].endswith('postgresql') and config['NAME'] == unquote(parsed.path.lstrip('/')) and config.get('HOST') == parsed.hostname


class SharedConnection:
    """Use Django's transaction for BOTH ORM and FlowLab SQL on shared SQLite."""
    def __init__(self):
        from django.db import transaction, connection
        self.connection = connection
        self.atomic = transaction.atomic()
        self.atomic.__enter__()
        self.cursors = []
    def execute(self, statement, params=()):
        cursor = self.connection.cursor()
        self.cursors.append(cursor)
        cursor.execute(database._replace_qmarks(statement), params)
        if self.connection.vendor=='postgresql' and statement.lstrip().upper().startswith('INSERT INTO USERS'):
            identity = self.connection.cursor()
            self.cursors.append(identity)
            identity.execute("SELECT currval(pg_get_serial_sequence('users','id'))")
            cursor.lastrowid = identity.fetchone()[0]
        return cursor
    def commit(self):
        pass  # The encompassing atomic transaction commits in close().
    def rollback(self):
        from django.db import transaction
        transaction.set_rollback(True)
    def close(self):
        for cursor in self.cursors:
            cursor.close()
        self.atomic.__exit__(*sys.exc_info())


def admin_connection():
    return SharedConnection() if shared_database() else database.get_connection()


def models():
    from django.contrib.auth.models import User
    from core.models import AdminAccountLink, Personnel, Role
    return User, AdminAccountLink, Personnel, Role


def admin_role():
    _, _, _, Role = models()
    return Role.objects.get(name='Administrator')


def sync_from_flow(connection, user_id, password=None, confirm_existing=False):
    if not shared_database():
        return
    from django.contrib.auth.hashers import make_password
    User, Link, Personnel, Role = models()
    row = connection.execute('SELECT u.username,u.password_hash,u.full_name,COALESCE(u.email,\'\'),r.name,u.is_active FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=?', (user_id,)).fetchone()
    if not row:
        return
    link = Link.objects.select_related('user').filter(flowlab_user_id=user_id).first()
    if row[4] != 'Administrator':
        if link and link.enabled:
            person = Personnel.objects.filter(user=link.user).first()
            if person:
                person.role = Role.objects.filter(pk=link.previous_role_id).first() or Role.objects.get_or_create(name='Guest')[0]
                person.save(update_fields=['role','updated_at'])
            link.user.is_superuser = False
            link.user.is_staff = False
            link.user.save(update_fields=['is_superuser','is_staff'])
            link.enabled = False
            link.save(update_fields=['enabled','updated_at'])
        return
    user = link.user if link else User.objects.filter(username__iexact=row[0]).first()
    if user and not link and not confirm_existing and not (password and user.check_password(password)):
        raise ValueError('An E&I account already has this username. Confirm that it is the same person before linking it as Administrator.')
    if user and Link.objects.filter(user=user).exclude(flowlab_user_id=user_id).exists():
        raise ValueError('This E&I account is already linked to another FlowLab identity.')
    if not user:
        first, _, last = row[2].partition(' ')
        user = User.objects.create_user(username=row[0], password=None, email=row[3], first_name=first, last_name=last)
    person, _ = Personnel.objects.get_or_create(user=user, defaults={'name':row[2], 'qualifications':'', 'years_of_experience':0})
    if not link:
        link = Link.objects.create(flowlab_user_id=user_id, user=user, previous_role_id=person.role_id)
    person.role = admin_role()
    person.name = row[2]
    person.save(update_fields=['role','name','updated_at'])
    user.is_active = bool(row[5])
    user.email = row[3]
    user.first_name, _, user.last_name = row[2].partition(' ')
    from app.modules.auth.service import AuthService
    encoded = (row[1] if '$' in row[1] and AuthService.verify_password(password,row[1]) else make_password(password)) if password else row[1]
    if '$' in encoded:
        user.password = encoded
    else:
        user.set_unusable_password()  # Legacy FlowLab hash is checked only by our linked-admin backend.
    user.save(update_fields=['password','is_active','email','first_name','last_name'])
    if password:
        connection.execute('UPDATE users SET password_hash=? WHERE id=?', (encoded,user_id))
    link.enabled = True
    link.save(update_fields=['enabled','updated_at'])
    return user


def sync_from_ei(connection, user, confirm_existing=False, temporary=None):
    if not shared_database():
        return
    _, Link, Personnel, _ = models()
    person = Personnel.objects.filter(user=user).select_related('role').first()
    link = Link.objects.filter(user=user).first()
    if not person or (not user.is_superuser and (not person.role or person.role.name != 'Administrator')):
        if link and link.enabled:
            role = connection.execute("SELECT id FROM roles WHERE name='Guest'").fetchone()
            guard_last_admin(connection, link.flowlab_user_id)
            connection.execute('UPDATE users SET role_id=? WHERE id=?',(role[0],link.flowlab_user_id))
            link.enabled = False
            link.save(update_fields=['enabled','updated_at'])
        return
    existing = connection.execute('SELECT id FROM users WHERE LOWER(username)=LOWER(?)',(user.username,)).fetchone()
    if existing and not link and not confirm_existing:
        raise ValueError('A FlowLab account has this username. Confirm that the accounts belong to the same person before linking.')
    if not user.has_usable_password():
        raise ValueError('Set a usable E&I password before assigning shared Administrator access.')
    role = connection.execute("SELECT id FROM roles WHERE name='Administrator'").fetchone()
    if not existing:
        cursor = connection.execute('INSERT INTO users(username,password_hash,full_name,email,role_id,is_active,must_change_password) VALUES(?,?,?,?,?,?,?)', (user.username,user.password,person.name,user.email,role[0],int(user.is_active),int(bool(temporary))))
        flow_id = cursor.lastrowid
    else:
        flow_id = existing[0]
        pending = connection.execute('SELECT must_change_password FROM users WHERE id=?',(flow_id,)).fetchone()[0] if temporary is None else int(temporary)
        connection.execute('UPDATE users SET password_hash=?,full_name=?,email=?,role_id=?,is_active=?,must_change_password=? WHERE id=?',(user.password,person.name,user.email,role[0],int(user.is_active),pending,flow_id))
    if not link:
        if Link.objects.filter(flowlab_user_id=flow_id).exists():
            raise ValueError('This FlowLab identity is already linked to another E&I account.')
        link = Link.objects.create(user=user,flowlab_user_id=flow_id)
    link.enabled = True
    link.save(update_fields=['enabled','updated_at'])


def update_linked_password(user, password):
    """Called inside the E&I password-change transaction; one SQLite writer."""
    if not shared_database():
        return
    _, Link, _, _ = models()
    link = Link.objects.filter(user=user,enabled=True).first()
    if link:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('UPDATE users SET password_hash=%s,must_change_password=0 WHERE id=%s', [user.password,link.flowlab_user_id])


def guard_last_admin(connection, flow_id):
    row = connection.execute('SELECT r.name,u.is_active FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=?',(flow_id,)).fetchone()
    if row and row[0]=='Administrator' and row[1] and not connection.execute("SELECT 1 FROM users u JOIN roles r ON r.id=u.role_id WHERE r.name='Administrator' AND u.is_active=1 AND u.id<>?",(flow_id,)).fetchone():
        raise ValueError('The last active integrated Administrator cannot be deactivated or demoted.')


def authenticate_ei_administrator(username, password):
    if not shared_database():
        return False
    User, _, Personnel, _ = models()
    user = User.objects.filter(username__iexact=username,is_active=True).first()
    if not user or not user.check_password(password):
        return False
    person = Personnel.objects.filter(user=user).select_related('role').first()
    if not person or not (user.is_superuser or person.role and person.role.name=='Administrator'):
        return False
    connection = admin_connection()
    try:
        sync_from_ei(connection,user)
    except ValueError:
        connection.rollback()
        return False
    finally:
        connection.close()
    return True
