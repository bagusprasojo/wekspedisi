from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from core.views import dashboard

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('platform/', include('tenants.urls')),
    path('master/', include('master.urls')),
    path('finance/', include('finance.urls')),
    path('invoice/', include('invoice.urls')),
    path('accounting/', include('accounting.urls')),
    path('reports/', include('reports.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('bagusprasojo/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
