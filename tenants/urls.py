from django.urls import path

from tenants import views

urlpatterns = [
    path('tenants/', views.platform_tenant_list, name='platform_tenant_list'),
    path('tenants/admission/', views.platform_tenant_admission, name='platform_tenant_admission'),
    path('tenants/<int:pk>/edit/', views.platform_tenant_edit, name='platform_tenant_edit'),
    path('tenants/users/new/', views.platform_tenant_user_create, name='platform_tenant_user_create'),
]
