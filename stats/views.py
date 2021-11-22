from pyecharts.charts import Bar
from pyecharts import options as opts
from jinja2 import Environment, FileSystemLoader
from django.http import HttpResponse, HttpResponseRedirect
from django import forms
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
import os
import time

from .models import DataFile, DataFileRecord
from .common.util.file import parse_file_size_str_to_int, parse_file_size_int_to_str

from pyecharts.globals import CurrentConfig
CurrentConfig.GLOBAL_ENV = Environment(
    loader=FileSystemLoader("./stats/templates"))
CurrentConfig.ONLINE_HOST = '/static/stats/'


def index(request):
    file_name = request.GET['file_name']
    data_file = DataFile.objects.filter(file_name=file_name).first()
    if not data_file:
        return HttpResponse(f"Can not find {file_name}")

    data_file_records = DataFileRecord.objects.filter(
        data_file=data_file).order_by('date_time')
    if len(data_file_records) == 0:
        return HttpResponse(f"No data file record for {file_name}")

    date_list = []
    size_list = []
    for r in data_file_records:
        size_list.append(round(r.size / 1024 / 1024, 2))
        date_list.append(r.date_time.date())

    c = (
        Bar()
        .add_xaxis(date_list)
        .add_yaxis(file_name, size_list)
        .set_global_opts(title_opts=opts.TitleOpts(title="Size(MB)"))
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
                data_file = DataFile(full_name=full_name,
                                     file_name=os.path.basename(full_name))
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
                    pre_day_rec = DataFileRecord.objects.filter(data_file=data_file,
                                                                date_time__lt=new_record_datetime.date()).order_by('-date_time').first()
                    next_day_rec = DataFileRecord.objects.filter(data_file=data_file,
                                                                 date_time__gt=new_record_datetime.date()).order_by(
                        'date_time').first()
                    if not pre_day_rec and not next_day_rec:
                        create_data_file_record = True
                    elif pre_day_rec and pre_day_rec.size != new_record_size and (not next_day_rec or next_day_rec.size != new_record_size):
                        create_data_file_record = True
                    elif next_day_rec and next_day_rec.size != new_record_size and (not pre_day_rec or pre_day_rec.size != new_record_size):
                        create_data_file_record = True
                    elif pre_day_rec and pre_day_rec.size == new_record_size:
                        pre_day_rec.date_time = new_record_datetime
                        pre_day_rec.save()
                    elif next_day_rec and next_day_rec.size == new_record_size:
                        next_day_rec.date_time = new_record_datetime
                        next_day_rec.save()
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
            handle_uploaded_file(
                request.FILES['file'], request.POST['date_time_str'])
            return HttpResponse(f'success time elapsed:{time.time() - start}')
    else:
        form = UploadFileForm()
    return render(request, 'upload.html', {'form': form})
