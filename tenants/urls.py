from django.urls import path

from tenants import views

urlpatterns = [
    path('tenants/', views.platform_tenant_list, name='platform_tenant_list'),
    path('tenants/admission/', views.platform_tenant_admission, name='platform_tenant_admission'),
    path('tenants/<int:pk>/edit/', views.platform_tenant_edit, name='platform_tenant_edit'),
    path('tenants/users/new/', views.platform_tenant_user_create, name='platform_tenant_user_create'),
    path('config/', views.platform_config_list, name='platform_config_list'),
    path('config/new/', views.platform_config_create, name='platform_config_create'),
    path('config/<uuid:uuid>/edit/', views.platform_config_edit, name='platform_config_edit'),
    path('config/<uuid:uuid>/delete/', views.platform_config_delete, name='platform_config_delete'),
    path('jenis-transaksi/', views.platform_transaction_type_list, name='platform_transaction_type_list'),
    path('jenis-transaksi/new/', views.platform_transaction_type_create, name='platform_transaction_type_create'),
    path('jenis-transaksi/<uuid:uuid>/edit/', views.platform_transaction_type_edit, name='platform_transaction_type_edit'),
    path('jenis-transaksi/<uuid:uuid>/delete/', views.platform_transaction_type_delete, name='platform_transaction_type_delete'),
]
