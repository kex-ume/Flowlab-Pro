# ─── API for Certiview Integration ───────────────────────────────────────────

from decimal import Decimal

from rest_framework import serializers
from core.models import (
    CalibrationLog, CalibrationLogReading, CalibrationType,
    Client, EnvironmentRecord, Job, Notification, Personnel,
    PreCalibrationLog, Primary, Role, Unit, Waybill, WaybillItem,
)


# ─── Nested / Lightweight ────────────────────────────────────────────────────

class CalibrationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalibrationType
        fields = ['id', 'name', 'description',
                  'instrument_column_label', 'uut_column_label', 'error_column_label']


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'name', 'symbol', 'scope']


class PersonnelSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source='role.name', read_only=True, allow_null=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Personnel
        fields = ['id', 'name', 'role_name', 'username', 'qualifications',
                  'years_of_experience', 'location_text']


class RoleSerializer(serializers.ModelSerializer):
    permission_codenames = serializers.ListField(
        source='permissions.values_list', read_only=True
    )

    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'permission_codenames']


# ─── Client ──────────────────────────────────────────────────────────────────

class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['id', 'name', 'email', 'phone',
                  'address', 'status', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


# ─── Waybill → WaybillItem (nested) ─────────────────────────────────────────

class WaybillItemSerializer(serializers.ModelSerializer):
    latest_log_status = serializers.CharField(read_only=True, allow_null=True)
    calibration_logs = serializers.SerializerMethodField()

    class Meta:
        model = WaybillItem
        fields = ['id', 'waybill', 'equipment_description', 'quantity',
                  'serial_no', 'model_no', 'manufacturer', 'range_field',
                  'status', 'latest_log_status', 'calibration_logs']

    @staticmethod
    def get_calibration_logs(obj):
        return [log.id for log in obj.calibration_logs.all()]

    def validate_serial_no(self, value):
        if self.instance is None and value and WaybillItem.objects.filter(serial_no=value).exists():
            raise serializers.ValidationError('A waybill item with this serial number already exists.')
        return value


class WaybillSerializer(serializers.ModelSerializer):
    items = WaybillItemSerializer(many=True, read_only=True)
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Waybill
        fields = ['id', 'waybill_no', 'waybill_type', 'file_upload',
                  'linked_incoming_waybill', 'items', 'item_count',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    @staticmethod
    def get_item_count(obj):
        return obj.items.count()


class WaybillWriteSerializer(serializers.ModelSerializer):
    items_data = WaybillItemSerializer(many=True, required=False)

    class Meta:
        model = Waybill
        fields = ['id', 'waybill_no', 'waybill_type', 'file_upload',
                  'linked_incoming_waybill', 'items_data']
        read_only_fields = ['id']

    def create(self, validated_data):
        items_data = validated_data.pop('items_data', [])
        waybill = Waybill.objects.create(**validated_data)
        for item_data in items_data:
            WaybillItem.objects.create(waybill=waybill, **item_data)
        return waybill


# ─── CalibrationLog (+ readings) ────────────────────────────────────────────

class CalibrationLogReadingSerializer(serializers.ModelSerializer):
    unit_symbol = serializers.CharField(source='unit.symbol', read_only=True, allow_null=True)

    class Meta:
        model = CalibrationLogReading
        fields = ['id', 'reading_type', 'instrument_reading', 'uut_reading', 'unit',
                  'unit_symbol', 'error', 'maximum_permissible_error', 'remark']


class CalibrationLogSerializer(serializers.ModelSerializer):
    readings = CalibrationLogReadingSerializer(many=True, read_only=True)
    calibrated_by_name = serializers.CharField(source='calibrated_by.name', read_only=True, allow_null=True)
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True, allow_null=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.get_full_name', read_only=True, allow_null=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True, allow_null=True)
    scope_name = serializers.CharField(source='scope.name', read_only=True, allow_null=True)
    scopes = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    scope_names = serializers.SerializerMethodField()
    equipment_serial = serializers.CharField(source='waybill_item.serial_no', read_only=True)
    equipment_desc = serializers.CharField(source='waybill_item.equipment_description', read_only=True)
    certificate_url = serializers.SerializerMethodField()
    reviewer_signature = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = CalibrationLog
        fields = ['id', 'waybill_item', 'calibrated_by', 'calibrated_by_name',
                  'calibrated_at_date', 'calibrated_at_location', 'equipment_desc',
                  'equipment_serial', 'scope', 'scope_name', 'scopes', 'scope_names',
                  'physical_condition',
                  'environmental_condition', 'pass_fail', 'status',
                  'reviewer', 'reviewer_name',
                  'reviewed_by', 'reviewed_by_name', 'reviewed_at',
                  'approved_by', 'approved_by_name', 'approved_at',
                  'reviewer_signature',
                  'certificate_no', 'certificate_url', 'readings',
                  'notes', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'status',
                            'reviewer', 'reviewed_by', 'reviewed_at',
                            'approved_by', 'approved_at']

    @staticmethod
    def get_scope_names(obj):
        return [s.name for s in obj.scopes.all()]

    @staticmethod
    def get_certificate_url(obj):
        if obj.certificate:
            return obj.certificate.url
        return None


class CalibrationLogWriteSerializer(serializers.ModelSerializer):
    readings_data = CalibrationLogReadingSerializer(many=True, required=False)
    standards = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Primary.objects.all(), required=False)

    class Meta:
        model = CalibrationLog
        fields = ['id', 'waybill_item', 'calibrated_by', 'calibrated_at_date', 'calibrated_at_location', 'scope', 'scopes', 'standards', 'physical_condition',
                  'environmental_condition', 'pass_fail', 'certificate',
                  'reviewer', 'asset_id', 'date_of_issue',
                  'readings_data', 'notes']

    @staticmethod
    def _normalize_readings(readings_data):
        """Add reading-type default + compute error = inst - uut when missing,
        mirroring the web create/update paths (_save_log_readings)."""
        normalized = []
        for reading_data in readings_data:
            item = dict(reading_data)
            item['reading_type'] = item.get('reading_type') or 'as_found'
            if item.get('error') in (None, '') and \
                    item.get('instrument_reading') is not None and \
                    item.get('uut_reading') is not None:
                try:
                    item['error'] = Decimal(item['instrument_reading']) - Decimal(item['uut_reading'])
                except (TypeError, ValueError, InvalidOperation):
                    pass
            normalized.append(item)
        return normalized

    def _after_readings(self, log):
        log.compute_uncertainty()
        log.derive_pass_fail_from_remarks()
        log.save(update_fields=[
            'expanded_uncertainty', 'uncertainty_in_tolerance', 'pass_fail'])

    def create(self, validated_data):
        readings_data = validated_data.pop('readings_data', [])
        validated_data['status'] = 'pending_review'
        scopes = validated_data.pop('scopes', [])
        standards = validated_data.pop('standards', [])
        log = CalibrationLog.objects.create(**validated_data)
        if scopes:
            log.scopes.set(scopes)
        if not log.scope_id:
            log.scope = log.scopes.first()
            log.save(update_fields=['scope'])
        log.standards.set(standards)
        for reading_data in self._normalize_readings(readings_data):
            CalibrationLogReading.objects.create(calibration_log=log, **reading_data)
        self._after_readings(log)
        return log

    def update(self, instance, validated_data):
        readings_data = validated_data.pop('readings_data', None)
        scopes = validated_data.pop('scopes', None)
        standards = validated_data.pop('standards', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if scopes is not None:
            instance.scopes.set(scopes)
            if not instance.scope_id:
                instance.scope = instance.scopes.first()
                instance.save(update_fields=['scope'])
        if standards is not None:
            instance.standards.set(standards)
        if readings_data is not None:
            instance.readings.all().delete()
            for reading_data in self._normalize_readings(readings_data):
                CalibrationLogReading.objects.create(calibration_log=instance, **reading_data)
            self._after_readings(instance)
        return instance


# ─── Job ─────────────────────────────────────────────────────────────────────

class JobSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True, allow_null=True)
    incoming_waybill_no = serializers.CharField(source='incoming_waybill.waybill_no', read_only=True, allow_null=True)
    outgoing_waybill_no = serializers.SerializerMethodField()
    equipment_items = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = ['id', 'client', 'client_name', 'purchase_order_number',
                  'job_status', 'remarks',
                  'incoming_waybill', 'incoming_waybill_no',
                  'outgoing_waybill_no',
                  'equipment_items',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'job_status']

    @staticmethod
    def get_outgoing_waybill_no(obj):
        return ', '.join(
            wb.waybill_no for wb in obj.waybills.filter(waybill_type='outgoing')
        ) or None

    @staticmethod
    def get_equipment_items(obj):
        if not obj.incoming_waybill:
            return []
        items = obj.incoming_waybill.items.all()
        return [{
            'id': item.id,
            'equipment_description': item.equipment_description,
            'serial_no': item.serial_no,
            'status': item.status,
            'calibration_log_id': item.calibration_logs.first().id if item.calibration_logs.exists() else None,
        } for item in items]


class JobWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ['id', 'client', 'purchase_order_number',
                  'incoming_waybill', 'remarks']
        read_only_fields = ['id', 'job_status']

    def create(self, validated_data):
        validated_data['job_status'] = 'not_received'
        return super().create(validated_data)


# ─── PreCalibrationLog ──────────────────────────────────────────────────────

class PreCalibrationLogSerializer(serializers.ModelSerializer):
    inspected_by_name = serializers.CharField(source='inspected_by.get_full_name', read_only=True)
    equipment_desc = serializers.CharField(source='waybill_item.equipment_description', read_only=True)
    equipment_serial = serializers.CharField(source='waybill_item.serial_no', read_only=True)
    unit_symbol = serializers.CharField(source='unit.symbol', read_only=True)
    scope_name = serializers.CharField(source='scope.name', read_only=True)
    scopes = serializers.PrimaryKeyRelatedField(many=True, queryset=CalibrationType.objects.all(), required=False)
    scope_names = serializers.SerializerMethodField()
    units = serializers.PrimaryKeyRelatedField(many=True, queryset=Unit.objects.all(), required=False)
    unit_symbols = serializers.SerializerMethodField()

    class Meta:
        model = PreCalibrationLog
        fields = ['id', 'waybill_item', 'equipment_desc', 'equipment_serial',
                  'inspected_by', 'inspected_by_name',
                  'scope', 'scope_name', 'scopes', 'scope_names',
                  'unit', 'unit_symbol', 'units', 'unit_symbols',
                  'range_value',
                  'physical_condition', 'environmental_condition',
                  'ready_for_calibration', 'review_decision',
                  'remarks', 'outgoing_waybill',
                  'doc_no',
                  'created_at']
        read_only_fields = ['created_at', 'review_decision']

    @staticmethod
    def get_scope_names(obj):
        return [s.name for s in obj.scopes.all()]

    @staticmethod
    def get_unit_symbols(obj):
        return [u.symbol for u in obj.units.all()]

    def create(self, validated_data):
        scopes = validated_data.pop('scopes', [])
        units = validated_data.pop('units', [])
        instance = self.Meta.model.objects.create(**validated_data)
        if scopes:
            instance.scopes.set(scopes)
        if not instance.scope_id:
            instance.scope = instance.scopes.first()
        if units:
            instance.units.set(units)
        if not instance.unit_id:
            instance.unit = instance.units.first()
        if instance.scope_id or instance.unit_id:
            instance.save(update_fields=['scope', 'unit'])
        return instance

    def update(self, instance, validated_data):
        scopes = validated_data.pop('scopes', None)
        units = validated_data.pop('units', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if scopes is not None:
            instance.scopes.set(scopes)
            if not instance.scope_id:
                instance.scope = instance.scopes.first()
                instance.save(update_fields=['scope'])
        if units is not None:
            instance.units.set(units)
            if not instance.unit_id:
                instance.unit = instance.units.first()
                instance.save(update_fields=['unit'])
        return instance


# ─── EnvironmentRecord ──────────────────────────────────────────────────────

class EnvironmentRecordSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True)
    location_name = serializers.CharField(source='location.name', read_only=True)

    class Meta:
        model = EnvironmentRecord
        fields = ['id', 'date', 'time', 'location', 'location_name', 'temperature',
                  'relative_humidity', 'recorded_by', 'recorded_by_name', 'created_at']
        read_only_fields = ['created_at', 'recorded_by']


# ─── Notification ────────────────────────────────────────────────────────────

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'message', 'link', 'is_read', 'notification_type',
                  'created_at']
        read_only_fields = ['id', 'message', 'link', 'notification_type', 'created_at']
