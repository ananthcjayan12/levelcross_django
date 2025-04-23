from django.contrib import admin
from .models import Train, CrossedTrain

@admin.register(Train)
class TrainAdmin(admin.ModelAdmin):
    list_display = ['train_number', 'station', 'time', 'week_day', 'direction']
    search_fields = ['train_number', 'station']
    list_filter = ['week_day', 'station', 'direction']

@admin.register(CrossedTrain)
class CrossedTrainAdmin(admin.ModelAdmin):
    list_display = ['train', 'crossed_date', 'crossed_time']
    list_filter = ['crossed_date']
