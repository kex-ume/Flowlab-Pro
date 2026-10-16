"""Shared ADMIN credentials only; ordinary E&I authentication stays independent."""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction


class IntegratedAdminBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        from app.modules.integrated_accounts import shared_database, admin_connection, sync_from_flow
        from app.modules.auth.service import AuthService
        from .models import AdminAccountLink
        if not shared_database() or not username or password is None:
            return super().authenticate(request,username=username,password=password,**kwargs)
        connection = admin_connection()
        try:
            row = connection.execute("SELECT u.id,u.password_hash,u.is_active,r.name FROM users u JOIN roles r ON r.id=u.role_id WHERE LOWER(u.username)=LOWER(?)",(username,)).fetchone()
            linked = AdminAccountLink.objects.filter(user__username__iexact=username,enabled=True).exists()
            if row and row[2] and row[3]=='Administrator' and AuthService.verify_password(password,row[1]):
                try:
                    return sync_from_flow(connection,row[0],password=password)
                except ValueError:
                    connection.rollback()
                    return None
            if linked:
                return None
        finally:
            connection.close()
        return super().authenticate(request,username=username,password=password,**kwargs)


class IntegratedPasswordChangeView(PasswordChangeView):
    def form_valid(self, form):
        from app.modules.integrated_accounts import update_linked_password
        with transaction.atomic():
            response = super().form_valid(form)
            update_linked_password(self.request.user,form.cleaned_data['new_password1'])
        return response


class AdminPasswordRequirementMiddleware:
    def __init__(self,get_response):
        self.get_response = get_response
    def __call__(self,request):
        from app.modules.integrated_accounts import shared_database
        if request.user.is_authenticated and shared_database() and not any(part in request.path for part in ('/password/','/logout/','/static/')):
            from .models import AdminAccountLink
            from django.db import connection
            from django.shortcuts import redirect
            link = AdminAccountLink.objects.filter(user=request.user,enabled=True).first()
            if link:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT u.must_change_password,u.is_active,r.name FROM users u JOIN roles r ON r.id=u.role_id WHERE u.id=%s',[link.flowlab_user_id])
                    row = cursor.fetchone()
                if not row or not row[1] or row[2]!='Administrator':
                    from django.contrib.auth import logout
                    logout(request)
                    return redirect('login')
                if row and row[0]:
                    return redirect('password_change')
        return self.get_response(request)
