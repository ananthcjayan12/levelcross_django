from django import forms

class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(label='Select CSV file')

class BoatCSVUploadForm(forms.Form):
    csv_file = forms.FileField(label='Select Boat CSV file') 