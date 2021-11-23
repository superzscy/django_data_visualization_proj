from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^file_size_info', views.file_size_info, name='file_size_info'),
    url(r'^add_data_file_record', views.add_data_file_record, name='add_data_file_record'),
]