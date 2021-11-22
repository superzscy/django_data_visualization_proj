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
