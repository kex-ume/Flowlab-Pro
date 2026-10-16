import json
from datetime import date

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from django.utils import timezone

from .models import (
    CalibrationLog, CalibrationProcedure, CalibrationType, Client, CompanyAddress,
    CompanyProfile, EnvironmentRecord, Job, Personnel,
    PreCalibrationLog, Primary, Role, Permission, Unit, Waybill, WaybillItem, Notification
)


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'w-full px-5 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 dark:focus:ring-blue-400',
        'placeholder': '\uf007  Username',
        'autocomplete': 'username',
        'id': 'id_username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-5 py-3 border border-gray-300 rounded-2xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 dark:focus:ring-blue-400',
        'placeholder': '\uf023  Password',
        'autocomplete': 'current-password',
        'id': 'id_password'
    }))


class CustomPasswordChangeForm(PasswordChangeForm):
    old_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
        'placeholder': 'Current Password',
        'autocomplete': 'current-password'
    }))
    new_password1 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
        'placeholder': 'New Password',
        'autocomplete': 'new-password'
    }))
    new_password2 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
        'placeholder': 'Confirm New Password',
        'autocomplete': 'new-password'
    }))


class ProfileForm(forms.ModelForm):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
            'placeholder': 'Email Address',
            'autocomplete': 'email'
        })
    )

    class Meta:
        model = Personnel
        fields = ['name', 'location_text', 'qualifications', 'signature']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Full Name',
                'autocomplete': 'name'
            }),
            'location_text': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. Lab 1, Building A'
            }),
            'qualifications': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'List qualifications',
                'rows': 3
            }),
        }
        labels = {'signature': 'Signature (uploaded once, auto-applied to your calibration logs)'}


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'abbreviation', 'email', 'phone', 'address']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Client Name',
                'autocomplete': 'organization'
            }),
            'abbreviation': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 uppercase',
                'placeholder': "e.g. ABC (used in certificate numbers)",
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Email Address',
                'autocomplete': 'email'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Phone Number',
                'autocomplete': 'tel'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Physical Address',
                'rows': 3,
                'autocomplete': 'street-address'
            }),
        }


class JobForm(forms.ModelForm):
    client = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
            'placeholder': 'Enter client name'
        })
    )

    class Meta:
        model = Job
        fields = [
            'purchase_order_number', 'client',
            'job_description', 'job_type', 'request_type',
            'received_started_date', 'scheduled_end_date', 'incoming_waybill',
            'job_status', 'invoice_status',
            'remarks', 'delay_remark'
        ]
        widgets = {
            'purchase_order_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. PO-2024-001'
            }),
            'job_description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Describe the calibration job',
                'rows': 3
            }),
            'job_type': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg'}),
            'request_type': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg'}),
            'received_started_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg'}),
            'scheduled_end_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg'}),
            'incoming_waybill': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'job_status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'invoice_status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Additional remarks',
                'rows': 2
            }),
            'delay_remark': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg', 'rows': 2, 'placeholder': 'Explain the delay and next action'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['purchase_order_number'].required = False
        self.fields['incoming_waybill'].queryset = Waybill.objects.filter(
            waybill_type='incoming'
        )
        self.fields['incoming_waybill'].required = False
        if not self.instance.pk:
            self.fields['received_started_date'].initial = date.today()
            self.fields['received_started_date'].required = True
            self.fields['scheduled_end_date'].required = True
        if self.instance and self.instance.pk and self.instance.client_id:
            self.initial['client'] = self.instance.client.name

    def clean_client(self):
        name = self.cleaned_data.get('client', '').strip()
        if not name:
            raise forms.ValidationError('Client name is required.')
        client = Client.objects.filter(name__iexact=name).first()
        if client:
            return client
        client = Client.objects.create(name=name, status='pending_info')
        self._new_pending_client = client
        return client

    def clean(self):
        cleaned_data = super().clean()
        job_status = cleaned_data.get('job_status')
        invoice_status = cleaned_data.get('invoice_status')
        purchase_order_number = cleaned_data.get('purchase_order_number')
        started = cleaned_data.get('received_started_date')
        scheduled_end = cleaned_data.get('scheduled_end_date')
        if started and scheduled_end and scheduled_end < started:
            self.add_error('scheduled_end_date', 'Scheduled end date cannot precede the received/started date.')
        if self.instance.pk and self.instance.is_overdue and not (cleaned_data.get('delay_remark') or '').strip():
            self.add_error('delay_remark', 'An overdue job requires a remark explaining the delay before it can be updated.')

        if self.instance and self.instance.pk:
            current_status = self.instance.job_status
        else:
            current_status = None

        if job_status == 'completed':
            if not purchase_order_number:
                self.add_error('purchase_order_number',
                    'Purchase Order Number is required before a job can be marked as Completed.')
            if invoice_status != 'paid':
                self.add_error('invoice_status',
                    'Invoice must be marked as Paid before a job can be marked as Completed.')

        elif job_status == 'dispatched':
            if current_status == 'completed':
                # Normal dispatch path
                if not purchase_order_number:
                    self.add_error('purchase_order_number',
                        'Purchase Order Number is required before a job can be dispatched.')
                if invoice_status != 'paid':
                    self.add_error('invoice_status',
                        'Invoice must be marked as Paid before a job can be dispatched.')
                if self.instance and self.instance.incoming_waybill:
                    all_completed = all(
                        item.status in ('completed', 'dispatched')
                        for item in self.instance.incoming_waybill.items.all()
                    )
                    if not all_completed:
                        self.add_error('job_status',
                            'All equipment items must be completed or dispatched before the job can be dispatched.')
            elif current_status in ('pre_calibration_pending', 'calibration_pending', 'repair_due'):
                # Pre-cal fail dispatch path
                pass

        return cleaned_data


class PersonnelForm(forms.ModelForm):
    login_username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'autocomplete':'username','class':'w-full px-3 py-2 border rounded-lg'}))
    temporary_password = forms.CharField(min_length=10, widget=forms.PasswordInput(attrs={'autocomplete':'new-password','class':'w-full px-3 py-2 border rounded-lg'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['temporary_password'].required = not bool(self.instance.pk)
        self.fields['login_username'].required = not bool(self.instance.pk)
        if not self.instance.pk:
            self.fields['experience_as_of'].initial = date.today()

    def clean_login_username(self):
        value = (self.cleaned_data.get('login_username') or '').strip()
        if value and User.objects.filter(username__iexact=value).exclude(pk=self.instance.user_id).exists():
            raise forms.ValidationError('This E&I username is already registered.')
        if value:
            from django.contrib.auth.validators import UnicodeUsernameValidator
            UnicodeUsernameValidator()(value)
        return value

    def clean_temporary_password(self):
        value = self.cleaned_data.get('temporary_password')
        if value:
            validate_password(value)
        return value

    class Meta:
        model = Personnel
        fields = [
            'name', 'role', 'location_text',
            'qualifications', 'years_of_experience', 'scope_of_expertise',
            'position', 'department', 'employment_status', 'contact_phone', 'experience_as_of'
        ]
        widgets = {
            'experience_as_of': forms.DateInput(attrs={'type':'date'}),
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Full name',
                'autocomplete': 'name'
            }),
            'role': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'location_text': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. Lab 1, Building A'
            }),
            'qualifications': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'List qualifications',
                'rows': 3
            }),
            'years_of_experience': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Years'
            }),
            'scope_of_expertise': forms.SelectMultiple(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
        }


class CalibrationLogForm(forms.ModelForm):
    use_manual_env = forms.BooleanField(
        required=False,
        label='Enter environmental data manually',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded dark:bg-gray-700 dark:border-gray-600'
        })
    )

    readings_found_json = forms.CharField(widget=forms.HiddenInput(), required=False)
    readings_left_json = forms.CharField(widget=forms.HiddenInput(), required=False)
    specs_json = forms.CharField(widget=forms.HiddenInput(), required=False)

    scopes = forms.ModelMultipleChoiceField(
        queryset=CalibrationType.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'space-y-1'}),
        required=False,
        label='Scope(s) of Calibration',
        help_text='A single calibration log may cover several scopes.'
    )

    class Meta:
        model = CalibrationLog
        fields = [
            'scopes', 'standards', 'equipment_owner', 'asset_id', 'equipment_desc',
            'manufacturer', 'model_no', 'serial_no', 'range_value',
            'physical_condition', 'environmental_condition',
            'manual_temperature', 'manual_humidity', 'use_manual_env',
            'temp_tolerance', 'rh_tolerance',
            'supply_voltage', 'supply_voltage_tolerance',
            'supply_frequency', 'supply_frequency_tolerance',
            'calibrated_at_location', 'calibrated_at_date', 'date_of_issue',
            'calibrated_by', 'reviewer', 'pass_fail', 'notes'
        ]
        widgets = {
            'standards': forms.SelectMultiple(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'size': 5
            }),
            'equipment_owner': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'equipment_desc': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Equipment Description'
            }),
            'manufacturer': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Manufacturer'
            }),
            'model_no': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Model Number'
            }),
            'serial_no': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Serial Number'
            }),
            'range_value': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Range'
            }),
            'physical_condition': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. Good, Damaged, Worn'
            }),
            'environmental_condition': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'manual_temperature': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Temperature (°C)',
                'step': '0.01'
            }),
            'manual_humidity': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Humidity (%)',
                'step': '0.01'
            }),
            'temp_tolerance': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': "e.g. ±1 °C"
            }),
            'rh_tolerance': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': "e.g. ±10 %RH"
            }),
            'supply_voltage': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'step': '0.01'
            }),
            'supply_voltage_tolerance': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': "e.g. ±5 %"
            }),
            'supply_frequency': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'step': '0.01'
            }),
            'supply_frequency_tolerance': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': "e.g. ±0.5 Hz"
            }),
            'asset_id': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Asset / Equipment ID'
            }),
            'date_of_issue': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'type': 'date'
            }),
            'calibrated_at_location': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'calibrated_at_date': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'type': 'date'
            }),
            'calibrated_by': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'reviewer': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'pass_fail': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Comments on the calibration',
                'rows': 2,
                'label': 'Comments'
            }),
        }

    def __init__(self, *args, **kwargs):
        waybill_item = kwargs.pop('waybill_item', None)
        job = kwargs.pop('job', None)
        super().__init__(*args, **kwargs)

        self.fields['notes'].label = 'Comments'

        self.fields['environmental_condition'].queryset = EnvironmentRecord.objects.all()
        self.fields['environmental_condition'].required = False
        self.fields['manual_temperature'].required = False
        self.fields['manual_humidity'].required = False
        for fname in ('temp_tolerance', 'rh_tolerance', 'supply_voltage',
                      'supply_voltage_tolerance', 'supply_frequency',
                      'supply_frequency_tolerance'):
            self.fields[fname].required = False

        scope_ids = []
        if waybill_item and getattr(waybill_item, 'scope_id', None):
            scope_ids = [waybill_item.scope_id]
            pre_cal = waybill_item.pre_calibration_logs.first()
            if pre_cal and pre_cal.scopes.exists():
                scope_ids = list(pre_cal.scopes.values_list('id', flat=True))
        elif self.instance.pk and self.instance.scopes.exists():
            scope_ids = list(self.instance.scopes.values_list('id', flat=True))
        elif self.instance.pk and self.instance.scope_id:
            scope_ids = [self.instance.scope_id]

        def _standards_qs(sc_ids):
            qs = Primary.objects.filter(status='active',is_reference=True)
            return qs.filter(scope_id__in=sc_ids) if sc_ids else qs
        self.fields['standards'].queryset = _standards_qs(scope_ids)
        self.fields['standards'].required = False

        latest_env = EnvironmentRecord.objects.order_by('-date', '-time').first()
        if latest_env:
            self.fields['environmental_condition'].initial = latest_env

        if waybill_item:
            self.fields['equipment_desc'].initial = waybill_item.equipment_description
            self.fields['manufacturer'].initial = waybill_item.manufacturer or ''
            self.fields['model_no'].initial = waybill_item.model_no or ''
            self.fields['serial_no'].initial = waybill_item.serial_no
            self.fields['range_value'].initial = waybill_item.range_field or ''
            if scope_ids:
                self.fields['scopes'].initial = scope_ids

        if job:
            self.fields['equipment_owner'].initial = job.client

        # Reviewer options: users who can review calibration data
        from .auth_utils import get_users_with_perm
        reviewers = get_users_with_perm('review_calibration')
        self.fields['reviewer'].queryset = reviewers
        self.fields['reviewer'].required = False
        self.fields['reviewer'].empty_label = 'Select a reviewer…'
        if self.instance and self.instance.reviewer_id:
            self.fields['reviewer'].initial = self.instance.reviewer_id

        if self.is_bound:
            # Scopes may have changed in this submission — re-filter standards to the posted scopes
            posted_scope_ids = []
            for v in self.data.getlist(self.add_prefix('scopes')):
                try:
                    posted_scope_ids.append(int(v))
                except (ValueError, TypeError):
                    continue
            if posted_scope_ids and sorted(posted_scope_ids) != sorted(scope_ids):
                self.fields['standards'].queryset = _standards_qs(posted_scope_ids)
        elif self.instance.pk:
            self.fields['standards'].initial = self.instance.standards.all()
            self.fields['specs_json'].initial = json.dumps([
                {'spec_name': s.spec_name, 'spec_value': s.spec_value}
                for s in self.instance.specs.all()
            ])


class IncomingWaybillForm(forms.ModelForm):
    class Meta:
        model = Waybill
        fields = ['waybill_no', 'file_upload']
        widgets = {
            'waybill_no': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Incoming Waybill Number'
            }),
            'file_upload': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
        }


class EnvironmentRecordForm(forms.ModelForm):
    class Meta:
        model = EnvironmentRecord
        fields = ['location', 'date', 'time', 'relative_humidity', 'temperature']
        widgets = {
            'location': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'date': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'type': 'date'
            }),
            'time': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'relative_humidity': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. 45.50',
                'step': '0.01'
            }),
            'temperature': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. 23.50',
                'step': '0.01'
            }),
        }


class PreCalibrationForm(forms.ModelForm):
    use_manual_env = forms.BooleanField(
        required=False,
        label='Enter environmental data manually',
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded dark:bg-gray-700 dark:border-gray-600'
        })
    )

    class Meta:
        model = PreCalibrationLog
        fields = [
            'scopes', 'units', 'range_value', 'location', 'physical_condition',
            'visual_inspection_notes', 'ready_for_calibration', 'issues_found',
            'environmental_condition', 'manual_temperature', 'manual_humidity',
            'use_manual_env', 'remarks'
        ]
        widgets = {
            'scopes': forms.CheckboxSelectMultiple(attrs={
                'class': 'space-y-1'
            }),
            'units': forms.CheckboxSelectMultiple(attrs={
                'class': 'space-y-1'
            }),
            'range_value': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. 0–10 bar'
            }),
            'location': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'physical_condition': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'visual_inspection_notes': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Visual inspection findings',
                'rows': 3
            }),
            'ready_for_calibration': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 border-gray-300 rounded dark:bg-gray-700 dark:border-gray-600'
            }),
            'issues_found': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Any issues or defects found',
                'rows': 3
            }),
            'environmental_condition': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'manual_temperature': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Temperature (°C)',
                'step': '0.01'
            }),
            'manual_humidity': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Humidity (%)',
                'step': '0.01'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Additional remarks (will be added to Job)',
                'rows': 3
            }),
        }

    def __init__(self, *args, **kwargs):
        waybill_item = kwargs.pop('waybill_item', None)
        super().__init__(*args, **kwargs)
        self.fields['environmental_condition'].queryset = EnvironmentRecord.objects.all()
        self.fields['environmental_condition'].required = False
        self.fields['manual_temperature'].required = False
        self.fields['manual_humidity'].required = False
        self.fields['range_value'].required = False

        # Units must belong to a selected scope; when bound (failed submit),
        # re-filter to the posted scopes so invalid choices show errors.
        posted_scopes = []
        if self.is_bound:
            for v in self.data.getlist(self.add_prefix('scopes')):
                try:
                    posted_scopes.append(int(v))
                except (ValueError, TypeError):
                    continue
        if posted_scopes:
            self.fields['units'].queryset = Unit.objects.filter(scope_id__in=posted_scopes)

        if waybill_item and getattr(waybill_item, 'scope_id', None) and not self.instance.pk:
            self.fields['scopes'].initial = [waybill_item.scope_id]

        if waybill_item and not self.is_bound and not self.instance.pk \
                and getattr(waybill_item, 'range_field', None):
            self.fields['range_value'].initial = waybill_item.range_field

        latest_env = EnvironmentRecord.objects.order_by('-date', '-time').first()
        if latest_env:
            self.fields['environmental_condition'].initial = latest_env

    def clean(self):
        cleaned = super().clean()
        scopes = cleaned.get('scopes') or []
        units = cleaned.get('units') or []

        if not scopes:
            self.add_error('scopes', 'Select at least one scope of calibration.')
        if units and scopes:
            scope_ids = {s.pk for s in scopes}
            mismatched = [u for u in units if u.scope_id not in scope_ids]
            if mismatched:
                self.add_error(
                    'units',
                    'Each selected unit must belong to one of the selected scopes: '
                    + ', '.join(u.symbol for u in mismatched)
                )
        if not units:
            self.add_error('units', 'Select at least one unit of measurement.')

        # Reference-standard availability / range containment.
        if units:
            from .matching import _equipment_bounds
            lo, hi = _equipment_bounds(cleaned.get('range_value'))
            std_qs = Primary.objects.filter(status='active',is_reference=True).filter(
                Q(unit__in=[u.id for u in units]) | Q(units__in=units)
            ).distinct()
            per_unit = {}
            for std in std_qs.prefetch_related('units'):
                for u in std.units.all():
                    per_unit.setdefault(u.id, []).append(std)
                if std.unit_id:
                    per_unit.setdefault(std.unit_id, []).append(std)
            for u in units:
                standards = per_unit.get(u.id) or []
                if not standards:
                    self.add_error(
                        'units',
                        f'No active reference standard is available in {u.symbol}. '
                        'Add one under Primaries first.'
                    )
                elif lo is not None and not any(
                    p.contains_range(lo, hi) for p in standards
                ):
                    self.add_error(
                        'units',
                        f'No active reference standard in {u.symbol} covers the range '
                        f'"{cleaned.get("range_value")}". Widen the range or pick another unit.'
                    )
        return cleaned


class PreCalReviewForm(forms.Form):
    DECISION_CHOICES = [
        ('repair', 'Approve Repair — Equipment can be repaired in-house'),
        ('dispatch', 'Approve Dispatch — Equipment cannot be repaired, send back to client'),
    ]
    decision = forms.ChoiceField(choices=DECISION_CHOICES, widget=forms.RadioSelect)
    review_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
            'rows': 3,
            'placeholder': 'Enter review notes / repair instructions...'
        }),
        required=False,
        label='Review Notes'
    )

    # Outgoing waybill fields (shown when dispatch is selected)
    waybill_no = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
            'placeholder': 'Enter outgoing waybill number'
        }),
        required=False,
        label='Outgoing Waybill Number'
    )
    waybill_file = forms.FileField(
        widget=forms.FileInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
        }),
        required=False,
        label='Waybill Document (optional)'
    )

    def clean(self):
        cleaned_data = super().clean()
        decision = cleaned_data.get('decision')
        waybill_no = cleaned_data.get('waybill_no')
        if decision == 'dispatch' and not waybill_no:
            self.add_error('waybill_no',
                'Outgoing waybill number is required when approving dispatch.')
        return cleaned_data


class CompanyAddressForm(forms.ModelForm):
    class Meta:
        model = CompanyAddress
        fields = ['label', 'address']
        widgets = {
            'label': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. Main Lab, Abuja Office'
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Full address',
                'rows': 2,
                'autocomplete': 'street-address'
            }),
        }


class CompanyProfileForm(forms.ModelForm):
    class Meta:
        model = CompanyProfile
        fields = [
            'company_name', 'abbreviation', 'phone', 'email', 'logo',
            'certificate_footer', 'certificate_format',
            'accreditation_statement', 'narrative_template',
            'traceability_body', 'compliance_standard', 'software',
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Company Name',
                'autocomplete': 'organization'
            }),
            'abbreviation': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 uppercase',
                'placeholder': "e.g. EATL (used in certificate numbers)",
            }),
            'phone': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Phone Number',
                'autocomplete': 'tel'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Email Address',
                'autocomplete': 'email'
            }),
            'logo': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'certificate_footer': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Footer text for certificates',
                'rows': 4
            }),
            'certificate_format': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': '{company_abbr}/{client_abbr}/{scope_abbr}/{seq:04d}',
            }),
            'accreditation_statement': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'rows': 3
            }),
            'narrative_template': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 font-mono text-xs',
                'rows': 4,
                'help_text': 'Placeholders: {uuc_description} {standard_used} {standard_cert_no} {traceability_body} {compliance_standard} {software} {procedure_manual}'
            }),
            'traceability_body': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': "e.g. National Metrology Institute (NMI)"
            }),
            'compliance_standard': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': "e.g. ISO/IEC 17025:2017"
            }),
            'software': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': "e.g. CalWin 5.2 / Excel-based worksheet"
            }),
        }


class CalibrationTypeForm(forms.ModelForm):
    class Meta:
        model = CalibrationType
        fields = [
            'name', 'abbreviation', 'description',
            'instrument_column_label', 'uut_column_label', 'error_column_label',
            'certificate_format', 'validity_months',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. Pressure Calibration'
            }),
            'abbreviation': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 uppercase',
                'placeholder': "e.g. PCAL (used in certificate numbers)",
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Description',
                'rows': 2
            }),
            'instrument_column_label': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Instrument Reading'
            }),
            'uut_column_label': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'UUT Reading'
            }),
            'error_column_label': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Error'
            }),
            'certificate_format': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 font-mono text-xs',
                'placeholder': '{company_abbr}/{client_abbr}/{scope_abbr}/{seq:04d}',
            }),
            'validity_months': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'min': 1,
            }),
        }

    def clean_abbreviation(self):
        abbr = (self.cleaned_data.get('abbreviation') or '').strip().upper()
        if not abbr:
            raise forms.ValidationError('An abbreviation is required (e.g. PCAL for Pressure Calibration).')
        qs = CalibrationType.objects.filter(abbreviation__iexact=abbr)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('This abbreviation is already used by another scope.')
        return abbr


class OutgoingWaybillForm(forms.ModelForm):
    class Meta:
        model = Waybill
        fields = ['waybill_no', 'file_upload', 'job']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['job'].required = True
        self.fields['job'].queryset = Job.objects.select_related('client').order_by('-created_at')
        self.fields['job'].empty_label = '-- Select Job --'

    def clean_job(self):
        job = self.cleaned_data.get('job')
        if not job:
            raise forms.ValidationError('Select the job this outgoing waybill belongs to.')
        if not (job.purchase_order_number or '').strip():
            raise forms.ValidationError(
                'This job has no Purchase Order number. An outgoing waybill cannot be created '
                'until a PO is established for the job.'
            )
        return job


class IncomingWaybillWithAutoNumberForm(forms.ModelForm):
    class Meta:
        model = Waybill
        fields = ['waybill_no', 'file_upload']
        widgets = {
            'waybill_no': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Auto-generated if left blank'
            }),
            'file_upload': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.auto_number = kwargs.pop('auto_number', None)
        super().__init__(*args, **kwargs)
        if self.auto_number:
            self.fields['waybill_no'].widget.attrs['placeholder'] = self.auto_number

    def clean_waybill_no(self):
        value = self.cleaned_data.get('waybill_no', '').strip()
        if not value and self.auto_number:
            return self.auto_number
        return value


class RoleForm(forms.ModelForm):
    def clean_name(self):
        name=self.cleaned_data['name'].strip()
        from .auth_utils import AUTHORITY_ROLES
        if self.instance.pk and self.instance.name in (*AUTHORITY_ROLES,'Supervisor') and name!=self.instance.name:
            raise forms.ValidationError('System role names are fixed to preserve authorization and shared-account links. Edit the description instead.')
        return name

    class Meta:
        model = Role
        fields = ['name', 'description', 'permissions']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. Senior Technician'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Description of this role',
                'rows': 2
            }),
            'permissions': forms.SelectMultiple(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
        }


class ProcedureAssignForm(forms.ModelForm):
    class Meta:
        model = CalibrationProcedure
        fields = ['scope', 'assigned_to', 'title', 'manual_reference']
        widgets = {
            'scope': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'assigned_to': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. Pressure Gauge Calibration — Dead Weight Tester'
            }),
            'manual_reference': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': "e.g. Manual §7.2, Fluke 754"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assigned_to'].queryset = (
            Personnel.objects.select_related('user').filter(user__isnull=False).order_by('name')
        )
        self.fields['assigned_to'].required = False
        self.fields['assigned_to'].empty_label = '-- Unassigned --'


class PrimaryForm(forms.ModelForm):
    def clean_asset_number(self):
        value=(self.cleaned_data.get('asset_number') or '').strip().upper()
        if not value:raise forms.ValidationError('Enter a unique equipment ID.')
        return value

    class Meta:
        model = Primary
        fields = [
            'asset_number','equipment_type','laboratory_location','is_reference','include_programme',
            'name', 'serial_no', 'manufacturer', 'model_no',
            'scope', 'units', 'range_min', 'range_max',
            'certificate_no', 'purchase_date', 'calibration_frequency',
            'last_calibrated', 'calibration_due_date',
            'operating_temp_min', 'operating_temp_max',
            'operating_humidity_min', 'operating_humidity_max',
            'standard_uncertainty', 'coverage_factor', 'tolerance',
            'uncertainty_equation',
            'status', 'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Primary / Reference Instrument name'
            }),
            'serial_no': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Serial Number'
            }),
            'manufacturer': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Manufacturer'
            }),
            'model_no': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Model Number'
            }),
            'scope': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'units': forms.CheckboxSelectMultiple(attrs={
                'class': 'space-y-1'
            }),
            'range_min': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': '0.0',
                'inputmode': 'decimal'
            }),
            'range_max': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': '100',
                'inputmode': 'decimal'
            }),
            'certificate_no': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': "e.g. EATL/LAB/UNC/01"
            }),
            'purchase_date': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'type': 'date'
            }),
            'calibration_frequency': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Months (e.g. 12)'
            }),
            'last_calibrated': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'type': 'date'
            }),
            'calibration_due_date': forms.DateInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'type': 'date'
            }),
            'operating_temp_min': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. 18.0',
                'step': '0.01'
            }),
            'operating_temp_max': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. 25.0',
                'step': '0.01'
            }),
            'operating_humidity_min': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. 30.0',
                'step': '0.01'
            }),
            'operating_humidity_max': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. 80.0',
                'step': '0.01'
            }),
            'standard_uncertainty': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. 0.1500 (u_std, in %)',
                'step': '0.0001'
            }),
            'coverage_factor': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. 2.00',
                'step': '0.01'
            }),
            'tolerance': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'e.g. 1.0000 (in %)',
                'step': '0.0001'
            }),
            'uncertainty_equation': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'k * sqrt(u_std**2 + error_max**2)'
            }),
            'status': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100',
                'placeholder': 'Notes',
                'rows': 2
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.retained_records.filter(kind='calibration',status='approved').exists():
            for field in ('last_calibrated','calibration_due_date','calibration_frequency','certificate_no'):
                self.fields[field].disabled=True
                self.fields[field].help_text='Updated through an independently verified calibration record.'
        self.fields['range_min'].required = False
        self.fields['range_max'].required = False
        self.fields['certificate_no'].required = False
        self.fields['units'].required = False
        instance = getattr(self, 'instance', None)
        scope_ids = []
        if self.is_bound:
            for v in self.data.getlist(self.add_prefix('scope')):
                try:
                    scope_ids.append(int(v))
                except (TypeError, ValueError):
                    continue
        elif instance and instance.pk and instance.scope_id:
            scope_ids = [instance.scope_id]
        self.fields['units'].queryset = (
            Unit.objects.filter(scope_id__in=scope_ids) if scope_ids else Unit.objects.none())

    def clean(self):
        cleaned = super().clean()
        scope = cleaned.get('scope') or getattr(self.instance, 'scope', None)
        units = cleaned.get('units') or []

        if units and scope:
            bad = [u for u in units if u.scope_id != scope.pk]
            if bad:
                self.add_error(
                    'units',
                    'Each selected unit must belong to the chosen scope: '
                    + ', '.join(u.symbol for u in bad)
                )

        for field in ('range_min', 'range_max'):
            val = cleaned.get(field)
            if val in (None, ''):
                continue
            try:
                float(val)
            except (TypeError, ValueError):
                self.add_error(field, 'Enter a number (digits with optional decimal point).')

        rmin, rmax = cleaned.get('range_min'), cleaned.get('range_max')
        try:
            if rmin not in (None, '') and rmax not in (None, '') and float(rmin) > float(rmax):
                self.add_error('range_max', 'Must be ≥ Range Min.')
        except (TypeError, ValueError):
            pass

        if cleaned.get('status') == 'active' and cleaned.get('is_reference', True):
            if not units:
                self.add_error('units', 'Active primaries must be linked to at least one unit.')
            if not cleaned.get('range_min') or not cleaned.get('range_max'):
                self.add_error(
                    'range_min',
                    'Active primaries require a calibrated Range (Min and Max) so availability '
                    'and range containment can be evaluated.'
                )
                self.add_error('range_max', '')
        last=cleaned.get('last_calibrated');due=cleaned.get('calibration_due_date')
        if last and last>timezone.localdate():self.add_error('last_calibrated','Actual calibration date cannot be in the future.')
        if due and last and due<last:self.add_error('calibration_due_date','Due date cannot precede calibration.')
        if cleaned.get('include_programme') and not cleaned.get('calibration_frequency'):self.add_error('calibration_frequency','A positive calibration interval is required.')
        if last and not due and cleaned.get('include_programme') and cleaned.get('calibration_frequency'):
            from .equipment_records import add_months
            cleaned['calibration_due_date']=add_months(last,cleaned['calibration_frequency'])
        return cleaned
