from pyecharts.charts import Bar
from pyecharts import options as opts
from jinja2 import Environment, FileSystemLoader
from django.http import HttpResponse, HttpResponseRedirect
from django import forms
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
import re
import os
import time

from .models import DataFile, DataFileRecord

from pyecharts.globals import CurrentConfig
CurrentConfig.GLOBAL_ENV = Environment(
    loader=FileSystemLoader("./stats/templates"))
CurrentConfig.ONLINE_HOST = '/static/stats/'

file_size_units = {"B": 1, "KB": 1024, "MB": 1024*1024}


def parse_file_size_str_to_int(size_str):
    size_str = size_str.upper()
    if not re.match(r' ', size_str):
        size_str = re.sub(r'([KM]?B)', r' \1', size_str)
    number, unit = [string.strip() for string in size_str.split()]
    return int(float(number) * file_size_units[unit])


def index(request):
    c = (
        Bar()
        .add_xaxis(["衬衫", "羊毛衫", "雪纺衫", "裤子", "高跟鞋", "袜子"])
        .add_yaxis("商家A", [5, 20, 36, 10, 75, 90])
        .set_global_opts(title_opts=opts.TitleOpts(title="Bar-基本示例", subtitle="我是副标题"))
    )
    return HttpResponse(c.render_embed())


class UploadFileForm(forms.Form):
    date_time_str = forms.CharField(max_length=50)
    file = forms.FileField()


def handle_uploaded_file(f, date_time_str):
    for chunk in f.chunks():
        for line in chunk.splitlines():
            full_name, size_str = line.decode('utf-8').split(',', 2)
            full_name = full_name.replace('\\', '/').replace('//', '/')
            full_name = full_name.split('/ns/data/')[1]

            data_file_created = False
            new_record_datetime = parse_datetime(date_time_str)
            new_record_size = parse_file_size_str_to_int(size_str)
            data_file = DataFile.objects.filter(full_name=full_name).first()
            if not data_file:
                data_file = DataFile(full_name=full_name, file_name=os.path.basename(full_name))
                data_file.save()
                data_file_created = True

            create_data_file_record = False
            if data_file_created:
                create_data_file_record = True
            else:
                # check and update same day record
                same_day_data_file_record = DataFileRecord.objects.filter(data_file=data_file,
                                                                          date_time__date=new_record_datetime.date()).first()
                if same_day_data_file_record:
                    if new_record_size != same_day_data_file_record.size and new_record_datetime > same_day_data_file_record.date_time:
                        same_day_data_file_record.size = new_record_size
                        same_day_data_file_record.date_time = new_record_datetime
                        same_day_data_file_record.save()
                else:
                    # check the closet earlier/later day
                    closet_earlier_day_data_file_record = DataFileRecord.objects.filter(data_file=data_file,
                                                                              date_time__lt=new_record_datetime.date()).order_by('-date_time').first()
                    closet_later_day_data_file_record = DataFileRecord.objects.filter(data_file=data_file,
                                                                                        date_time__gt=new_record_datetime.date()).order_by(
                        'date_time').first()
                    if not closet_earlier_day_data_file_record and not closet_later_day_data_file_record \
                            or ((closet_earlier_day_data_file_record and closet_earlier_day_data_file_record.size != new_record_size) \
                            and (closet_later_day_data_file_record and closet_later_day_data_file_record.size != new_record_size)):
                        create_data_file_record = True
                    elif closet_earlier_day_data_file_record and closet_earlier_day_data_file_record.size == new_record_size:
                        closet_earlier_day_data_file_record.date_time = new_record_datetime
                        closet_earlier_day_data_file_record.save()
                    elif closet_later_day_data_file_record and closet_later_day_data_file_record.size == new_record_size:
                        closet_later_day_data_file_record.date_time = new_record_datetime
                        closet_later_day_data_file_record.save()
            if create_data_file_record:
                data_file_record = DataFileRecord(size=new_record_size,
                                                  date_time=new_record_datetime,
                                                  data_file=data_file)
                data_file_record.save()


def add_data_file_record(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            start = time.time()
            handle_uploaded_file(request.FILES['file'], request.POST['date_time_str'])
            return HttpResponse(f'success time elapsed:{time.time() - start}')
    else:
        form = UploadFileForm()
    return render(request, 'upload.html', {'form': form})
