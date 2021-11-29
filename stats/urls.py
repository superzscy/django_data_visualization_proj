from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^data_file_info', views.data_file_info, name='data_file_info'),
    url(r'^data_file_list', views.data_file_list, name='data_file_list'),
    url(r'^data_file_changes', views.data_file_changes, name='data_file_changes'),
    
    url(r'^phase_stat', views.phase_stat, name='phase_stat'),
    url(r'^phase_record', views.phase_record, name='phase_record'),
    url(r'^phase_fps_heatmap', views.phase_fps_heatmap, name='phase_fps_heatmap'),
    
    url(r'^add_data_file_record', views.add_data_file_record, name='add_data_file_record'),
    url(r'^add_stats_file_record', views.add_stats_file_record, name='add_stats_file_record'),
]