from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^data_file_info', views.data_file_info, name='data_file_info'),
    url(r'^add_data_file_record', views.add_data_file_record, name='add_data_file_record'),
    url(r'^add_fps_file_record', views.add_fps_file_record, name='add_fps_file_record'),
]