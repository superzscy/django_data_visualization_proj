from django.contrib import admin
from . import models

admin.site.register(models.DataFileRecord)


@admin.register(models.DataFile)
class DataFileAdmin(admin.ModelAdmin):
    pass
