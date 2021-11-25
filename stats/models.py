from django.db import models
from .common.util.file import parse_file_size_int_to_str

class DataFile(models.Model):
    full_name = models.CharField(max_length=256)
    file_name = models.CharField(max_length=64)
    desc = models.TextField(default='')

    def __str__(self):
        return self.full_name + " " + parse_file_size_int_to_str(self.current_size())

    def current_size(self):
        data_file_record = DataFileRecord.objects.filter(data_file=self).order_by('-date_time').first()
        return data_file_record.size if data_file_record else 0


class DataFileRecord(models.Model):
    size = models.IntegerField(default=0)
    date_time = models.DateTimeField()
    data_file = models.ForeignKey(DataFile, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.data_file) + " " + str(parse_file_size_int_to_str(self.size)) + " " + str(self.date_time)

class StatFileRecord(models.Model):
    phase_name = models.CharField(max_length=3)
    sub_phase_name = models.CharField(max_length=32)
    version = models.CharField(max_length=16)
    file = models.FileField(upload_to='StatFileRecords/%Y/%m/%d/')
    desc = models.TextField(default='', blank=True)
    date_time = models.DateTimeField()
    avg_fps = models.FloatField(null=True, blank=True, default=None)
    avg_cpu = models.FloatField(null=True, blank=True, default=None)
    avg_gpu = models.FloatField(null=True, blank=True, default=None)
    avg_drawcall = models.FloatField(null=True, blank=True, default=None)

    def __str__(self):
        return f'{self.phase_name}:{self.sub_phase_name} {str(self.date_time.date())}'

class ScenePerf(models.Model):
    phase_name = models.CharField(max_length=3)
    sub_phase_name = models.CharField(max_length=32)
    build_version = models.CharField(max_length=16)
    desc = models.TextField(default='')

