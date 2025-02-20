from django.db import models

# Create your models here.

class Train(models.Model):
    train_number = models.CharField(max_length=10, unique=True)
    station = models.CharField(max_length=100)
    time = models.TimeField()
    week_day = models.CharField(max_length=50, help_text="Comma-separated days or 'All'")
    weekly = models.CharField(max_length=50, blank=True)
    day_reach_station = models.CharField(max_length=100, blank=True)
    direction = models.CharField(
        max_length=10,
        choices=[('ERS-SRT', 'ERS to SRT'), ('SRT-ERS', 'SRT to ERS')],
        default='ERS-SRT'
    )

    def __str__(self):
        return f"Train {self.train_number} - {self.station}"

class CrossedTrain(models.Model):
    train = models.ForeignKey(Train, on_delete=models.CASCADE)
    crossed_date = models.DateField(auto_now_add=True)
    crossed_time = models.TimeField(auto_now_add=True)

    class Meta:
        unique_together = ['train', 'crossed_date']

class TrainStatus(models.Model):
    train = models.ForeignKey(Train, on_delete=models.CASCADE)
    current_station = models.CharField(max_length=200)
    status_as_of = models.CharField(max_length=100)
    last_update = models.DateTimeField(auto_now=True)
    delay = models.IntegerField(default=0)
    
    class Meta:
        get_latest_by = 'last_update'
