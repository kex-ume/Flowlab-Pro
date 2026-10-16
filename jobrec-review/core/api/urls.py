from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken import views as auth_views

from core.api import views

router = DefaultRouter()
router.register(r'clients', views.ClientViewSet, basename='client')
router.register(r'waybills', views.WaybillViewSet, basename='waybill')
router.register(r'calibration-logs', views.CalibrationLogViewSet, basename='calibrationlog')
router.register(r'jobs', views.JobViewSet, basename='job')
router.register(r'pre-calibration-logs', views.PreCalibrationLogViewSet, basename='precalibrationlog')
router.register(r'environment-records', views.EnvironmentRecordViewSet, basename='environmentrecord')
router.register(r'personnel', views.PersonnelViewSet, basename='personnel')
router.register(r'calibration-types', views.CalibrationTypeViewSet, basename='calibrationtype')
router.register(r'units', views.UnitViewSet, basename='unit')
router.register(r'roles', views.RoleViewSet, basename='role')
router.register(r'notifications', views.NotificationViewSet, basename='notification')

app_name = 'api'

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('auth/token/', auth_views.obtain_auth_token, name='api_token_auth'),
]
