import os
import statistics
import sys
import time
import random
from datetime import datetime

from django import forms
from django.http import HttpResponse, request
from django.shortcuts import render, HttpResponseRedirect
from django.urls import get_resolver, reverse
from django.db.models import Avg
from django.utils.dateparse import parse_datetime
from jinja2 import Environment, FileSystemLoader
from pyecharts import options as opts
from pyecharts.charts import Bar, Line, Page, Tab, HeatMap, Grid
from pyecharts.globals import CurrentConfig
from pyecharts.faker import Faker

from .common.util.file import (parse_file_size_int_to_str,
                               parse_file_size_str_to_int)
from .models import DataFile, DataFileRecord, StatFileRecord

CurrentConfig.GLOBAL_ENV = Environment(
    loader=FileSystemLoader("stats/templates/stats/"))
CurrentConfig.ONLINE_HOST = '/static/stats/'


def index(request):
    context = {'url_list': set(v[1].replace(
        'stats/', '') for k, v in get_resolver(None).reverse_dict.items() if '$' not in v[1])}
    return render(request, 'stats/index.html', context)


def get_changed_data_files(datatime):
    records = DataFileRecord.objects.filter(date_time__date=datatime.date())

    ret = []
    for r in records:
        pre_day_rec = DataFileRecord.objects.filter(
            data_file=r.data_file, date_time__lt=r.date_time.date()).order_by('date_time').first()
        if not pre_day_rec:
            ret.append((r.data_file.full_name, r.size))
        else:
            ret.append((r.data_file.full_name, r.size - pre_day_rec.size))

    return ret


def data_file_changes(request):
    date = request.GET.get('date', '')
    if date == '':
        date = datetime.today()
    else:
        try:
            date = datetime.strptime(date + ' 23:59:59', "%Y-%m-%d %H:%M:%S")
        except ValueError as e:
            pass
    if isinstance(date, datetime):
        datas = get_changed_data_files(date)
        datas = sorted(datas, key=lambda d: d[1], reverse=True)
        datas = [
            {'file_name': k, 'size': parse_file_size_int_to_str(v)} for k, v in datas]
        context = {'d': datas}
        return render(request, 'stats/table.html', context)
    else:
        return HttpResponse('Wrong date parameter')


def data_file_list(request):
    file_name_count = request.GET.get('count', '')
    if file_name_count is not None and file_name_count.isnumeric():
        file_name_count = int(file_name_count)
    else:
        file_name_count = 10

    data_files = DataFile.objects.all()
    datas = []
    for obj in data_files:
        datas.append({'file_name': obj.full_name, 'size': obj.current_size()})
    datas = sorted(datas, key=lambda d: d['size'], reverse=True)
    datas = [{'file_name': obj['file_name'], 'size': parse_file_size_int_to_str(
        obj['size'])} for obj in datas][:file_name_count]
    context = {'d': datas}
    return render(request, 'stats/table.html', context)


def data_file_info(request):
    file_names = request.GET.getlist('file_name')
    if not file_names:
        return HttpResponse("file_name parameter missing")

    tab = Tab()

    for file_name in file_names:
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
            size_list.append(max(round(r.size / 1024 / 1024, 2), 0.01))
            date_list.append(r.date_time.date())

        bar = (
            Bar()
            .add_xaxis(date_list)
            .add_yaxis(file_name, size_list)
            .set_global_opts(title_opts=opts.TitleOpts(title="Size(MB)"))
        )
        tab.add(bar, file_name)
    return HttpResponse(tab.render_embed())


def handle_uploaded_data_file(f):
    lines = []
    for chunk in f.chunks():
        for line in chunk.splitlines():
            if line != '':
                lines.append(line)

    version = lines[0].decode('utf-8').split('_')[0]
    date_time_str = lines[1].decode('utf-8').replace('/', '-')

    for line in lines[2:]:
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
                # same size record in a row, keep the first one
                if next_day_rec and next_day_rec.size == new_record_size:
                    next_day_rec.date_time = new_record_datetime
                    next_day_rec.save()

        if create_data_file_record:
            data_file_record = DataFileRecord(size=new_record_size,
                                              date_time=new_record_datetime,
                                              data_file=data_file)
            data_file_record.save()


class UploadDataFileForm(forms.Form):
    file = forms.FileField()


def add_data_file_record(request):
    if request.method == 'POST':
        form = UploadDataFileForm(request.POST, request.FILES)
        if form.is_valid():
            start = time.time()
            handle_uploaded_data_file(request.FILES['file'])
            return HttpResponse(f'success, time elapsed:{time.time() - start}')
    else:
        form = UploadDataFileForm()
    return render(request, 'stats/upload.html', {'form': form, 'title': 'Add data file record'})


def phase_record(request):
    phase_name = request.GET.get('phase_name', '')
    sub_phase_name = request.GET.get('sub_phase_name', '')
    date_time_str = request.GET.get('date_time_str', '')

    if not phase_name or not sub_phase_name:
        return HttpResponse('Invalid paramaters')

    statFileRecord = StatFileRecord.objects.filter(
        phase_name=phase_name, sub_phase_name=sub_phase_name, date_time__date=parse_datetime(date_time_str).date()).first()
    if statFileRecord:
        return HttpResponse("no recored")

    lines = []

    lines = statFileRecord.file.open(mode="r").read().splitlines()
    statFileRecord.file.close()

    frames = []
    cpu_times = []
    gpu_times = []
    drawcall_cnts = []

    # Frame_Time(ms),CPU_Time(ms),GPU_Time(ms),Draw_Call(100),ESP2D(ms),SORT3D(ms),EVENTS
    for line in lines[2:]:
        attrs = line.split(',')
        frames.append(round(1000 / float(attrs[0]), 2))
        cpu_times.append(round(float(attrs[1]), 2))
        gpu_times.append(round(float(attrs[2]), 2))
        drawcall_cnts.append(round(float(attrs[3]), 2))

    page = Page()
    opt_avg = opts.MarkPointOpts(data=[opts.MarkPointItem(type_="average")])

    perf_line = (
        Line(init_opts=opts.InitOpts(width="1800px", height="900px"))
        .add_xaxis(list(range(1, len(frames))))
        .add_yaxis("frames", frames, markpoint_opts=opt_avg)
        .add_yaxis("cpu_times", cpu_times, markpoint_opts=opt_avg)
        .add_yaxis("gpu_times", gpu_times, markpoint_opts=opt_avg)
        .add_yaxis("drawcall_cnts", drawcall_cnts, markpoint_opts=opt_avg)
        .set_global_opts(
            title_opts=opts.TitleOpts(title=f'{phase_name}:{sub_phase_name}'),
            yaxis_opts=opts.AxisOpts(max_=100),
            datazoom_opts=[opts.DataZoomOpts(
                range_start=1, range_end=sys.maxsize)]
        )
    )
    page.add(perf_line)

    return HttpResponse(page.render_embed())


def phase_stat(request):
    phase_name = request.GET.get('phase_name', '')
    sub_phase_name = request.GET.get('sub_phase_name', '')

    if not phase_name or not sub_phase_name:
        return HttpResponse('Invalid paramaters')

    dates = []
    frames = []
    cpu_times = []
    gpu_times = []
    drawcall_cnts = []

    statFileRecords = StatFileRecord.objects.filter(
        phase_name=phase_name, sub_phase_name=sub_phase_name).order_by('date_time')
    for statFileRecord in statFileRecords:
        dates.append(statFileRecord.date_time.date())
        frames.append(statFileRecord.avg_fps)
        cpu_times.append(statFileRecord.avg_cpu)
        gpu_times.append(statFileRecord.avg_gpu)
        drawcall_cnts.append(statFileRecord.avg_drawcall)

    if len(dates) > 0:
        page = Page()
        opt_avg = opts.MarkPointOpts(
            data=[opts.MarkPointItem(type_="average")])

        perf_line = (
            Line(init_opts=opts.InitOpts(width="1800px", height="900px"))
            .add_xaxis(dates)
            .add_yaxis("frames", frames, markpoint_opts=opt_avg)
            .add_yaxis("cpu_times", cpu_times, markpoint_opts=opt_avg)
            .add_yaxis("gpu_times", gpu_times, markpoint_opts=opt_avg)
            .add_yaxis("drawcall_cnts", drawcall_cnts, markpoint_opts=opt_avg)
            .set_global_opts(
                title_opts=opts.TitleOpts(
                    title=f'{phase_name}:{sub_phase_name}'),
                yaxis_opts=opts.AxisOpts(max_=100),
                datazoom_opts=[opts.DataZoomOpts(
                    range_start=1, range_end=sys.maxsize)]
            )
        )
        page.add(perf_line)

        return HttpResponse(page.render_embed())
    else:
        return HttpResponse("no recored")


def create_uploaded_stats_file(file, version, phase_name, sub_phase_name, date_time_str):
    statFileRecord = StatFileRecord.objects.create(
        phase_name=phase_name, sub_phase_name=sub_phase_name, version=version, file=file, date_time=parse_datetime(date_time_str))
    lines = statFileRecord.file.open(mode="r").read().splitlines()
    statFileRecord.file.close()

    frames = []
    cpu_times = []
    gpu_times = []
    drawcall_cnts = []

    # Frame_Time(ms),CPU_Time(ms),GPU_Time(ms),Draw_Call(100),ESP2D(ms),SORT3D(ms),EVENTS
    for line in lines[2:]:
        attrs = line.split(',')
        frames.append(1000 / float(attrs[0]))
        cpu_times.append(float(attrs[1]))
        gpu_times.append(float(attrs[2]))
        drawcall_cnts.append(float(attrs[3]))

    statFileRecord.avg_fps = statistics.mean(frames)
    statFileRecord.avg_cpu = statistics.mean(cpu_times)
    statFileRecord.avg_gpu = statistics.mean(gpu_times)
    statFileRecord.avg_drawcall = statistics.mean(drawcall_cnts)
    statFileRecord.save()

    print(f'Added stat: P{phase_name} {sub_phase_name} {date_time_str}')


class UploadStatsFileForm(forms.Form):
    files = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'multiple': True}))


def add_stats_file_record(request):
    if request.method == 'POST':
        form = UploadStatsFileForm(request.POST, request.FILES)
        if form.is_valid():
            start = time.time()

            files = request.FILES.getlist('files')

            for file in files:
                for chunk in file.chunks():
                    lines = chunk.splitlines()[:2]
                    version = lines[0].decode('utf-8').split('_')[0]
                    date_time_str = lines[1].decode('utf-8').replace('/', '-')
                    break
                phase_name, sub_phase_name = file.name.replace(
                    '.csv', '').split('-')

                create_uploaded_stats_file(
                    file, version, phase_name, sub_phase_name, date_time_str)
            return HttpResponse(f'Upload finished，time elapsed:{round(time.time() - start, 2)}')
    else:
        form = UploadStatsFileForm()
    return render(request, 'stats/upload.html', {'form': form, 'title': 'Add fps record'})

def get_phase_avg_fps(date, phase_name, sub_phase_name):
    avg_fps = StatFileRecord.objects.filter(
        phase_name=phase_name, sub_phase_name=sub_phase_name, date_time__date=date).values('avg_fps').aggregate(Avg('avg_fps'))
    return list(avg_fps.values())[0]


def phase_fps_heatmap(request):
    phases = StatFileRecord.objects.values_list(
        'phase_name', 'sub_phase_name').distinct()
    date_times = StatFileRecord.objects.values_list(
        'date_time', flat=True).distinct()
    dates = sorted(list({item.date() for item in date_times}))
    if len(dates) == 0:
        return HttpResponse('No records for fps')
    # return HttpResponse(f'phase num:{len(phases)} date_time num:{len(dates)}\n' + '\n'.join( [f'{t[0]} {t[1]}' for t in list(phases)]), content_type="text/plain")
    # print(f'phase num:{len(phases)} date_time num:{len(dates)}')
    # print('P300', '250_CD_Unknown_9S', get_phase_avg_fps(parse_datetime('2021-11-26 0:0:0'), 'P300', '250_CD_Unknown_9S'))

    latest_date = dates[-1]
    latest_fps_list = []
    for phase_index, phase_info in enumerate(phases):
        latest_fps_list.append((phase_info[0], phase_info[1], get_phase_avg_fps(latest_date, phase_info[0], phase_info[1])))
    latest_fps_list.sort(key=lambda x: x[2], reverse=True)

    fps_datas = []
    for date_index, date in enumerate(dates):
        for phase_index, phase_info in enumerate(latest_fps_list):
            fps_datas.append([date_index, phase_index, round(get_phase_avg_fps(date, phase_info[0], phase_info[1]), 2)])
    c = (
        HeatMap()
        .add_xaxis(dates)
        .add_yaxis(
            series_name="phases", 
            yaxis_data=[f'{t[0]} {t[1]}' for t in latest_fps_list], 
            value=fps_datas,
            label_opts=opts.LabelOpts(
                is_show=True, color="#fff", position="inside"
            ),    
        )
        .set_global_opts(
            legend_opts=opts.LegendOpts(is_show=False),
            title_opts=opts.TitleOpts(title="FPS HeatMap"),
            yaxis_opts=opts.AxisOpts(axislabel_opts={"interval":"0"}),
            visualmap_opts=opts.VisualMapOpts(
                min_=0, max_=30, is_calculable=True, orient="horizontal", pos_left="center",
                range_color=["#d94e5d"]* 28 + ["#eac763", "#50a3ba"]
            ),
        )
    )

    grid = Grid(init_opts=opts.InitOpts(width="1200px", height="800px"))
    grid.add(c, grid_opts=opts.GridOpts(pos_left=260))
    return HttpResponse(grid.render_embed())

