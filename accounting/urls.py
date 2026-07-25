from django.urls import path

from accounting import views
from accounting.forms import ClosingPeriodForm
from accounting.models import ClosingPeriod
from core.crud import CrudConfig, build_crud_views

closing_list_view, closing_create_view, closing_update_view, closing_delete_view = build_crud_views(
    CrudConfig(
        model=ClosingPeriod,
        form_class=ClosingPeriodForm,
        title='Closing',
        list_display=['tanggal', 'keterangan'],
        search_fields=['keterangan'],
        success_url_name='accounting_closing_list',
        detail_url_name='accounting_closing_detail',
    )
)

urlpatterns = [
    path('jurnal/account-lookup/', views.adjustment_account_lookup, name='accounting_jurnal_account_lookup'),
    path('jurnal/', views.journal_list, name='accounting_jurnal_list'),
    path('jurnal/new/', views.journal_create, name='accounting_jurnal_create'),
    path('jurnal/<uuid:uuid>/edit/', views.journal_update, name='accounting_jurnal_update'),
    path('jurnal/<uuid:uuid>/delete/', views.journal_delete, name='accounting_jurnal_delete'),
    path('closing/', closing_list_view.as_view(), name='accounting_closing_list'),
    path('closing/<uuid:uuid>/', views.closing_detail, name='accounting_closing_detail'),
    path('closing/new/', closing_create_view.as_view(), name='accounting_closing_create'),
    path('closing/<uuid:uuid>/edit/', closing_update_view.as_view(), name='accounting_closing_update'),
    path('closing/<uuid:uuid>/delete/', closing_delete_view.as_view(), name='accounting_closing_delete'),
]

