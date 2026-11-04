from django import forms
from django.utils import timezone
from .models import Session


class SessionForm(forms.ModelForm):

    class Meta:
        model  = Session
        fields = [
            'title', 'description', 'skill', 'date',
            'start_time', 'end_time', 'credits_required',
            'session_type', 'level', 'max_participants',
        ]
        widgets = {
            'date':        forms.DateInput(attrs={'type': 'date'}),
            'start_time':  forms.TimeInput(attrs={'type': 'time'}),
            'end_time':    forms.TimeInput(attrs={'type': 'time'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'credits_required': 'Credits Required',
            'session_type':     'Session Type',
            'level':            'Skill Level',
            'max_participants': 'Max Participants',
        }

    def clean_date(self):
        date  = self.cleaned_data.get('date')
        today = timezone.now().date()
        if date and date < today:
            raise forms.ValidationError('Session date cannot be in the past.')
        return date

    def clean(self):
        cleaned_data = super().clean()
        start_time   = cleaned_data.get('start_time')
        end_time     = cleaned_data.get('end_time')
        if start_time and end_time and end_time <= start_time:
            raise forms.ValidationError('End time must be after start time.')
        return cleaned_data


class RescheduleForm(forms.Form):
    date       = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))
    end_time   = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))

    def clean_date(self):
        date  = self.cleaned_data.get('date')
        today = timezone.now().date()
        if date and date < today:
            raise forms.ValidationError('Reschedule date cannot be in the past.')
        return date

    def clean(self):
        cleaned_data = super().clean()
        start_time   = cleaned_data.get('start_time')
        end_time     = cleaned_data.get('end_time')
        if start_time and end_time and end_time <= start_time:
            raise forms.ValidationError('End time must be after start time.')
        return cleaned_data