"""
Serializers для API endpoints.
"""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import (
    File, ParsedItem, FileMetadata, Order, Supplier,
    TapLocation, Tap, AvailableBeer, UserProfile,
    ParseRun, ParsingFeedback, SupplierColumnMapping
)

User = get_user_model()


class SupplierSerializer(serializers.ModelSerializer):
    """Serializer для настроек поставщика (маппинг колонок)."""
    class Meta:
        model = Supplier
        fields = ['id', 'name', 'column_mapping', 'created_at', 'updated_at']


class FileSerializer(serializers.ModelSerializer):
    """Serializer для модели File."""
    
    class Meta:
        model = File
        fields = ['id', 'original_filename', 'file_type', 
                 'uploaded_at', 'google_sheet_url']


class ParsedItemSerializer(serializers.ModelSerializer):
    """Serializer для модели ParsedItem."""
    
    file = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = ParsedItem
        fields = ['id', 'file', 'brewery', 'beer_name', 'style', 
                 'abv', 'ibu', 'price', 'currency', 'volume', 
                 'format_type', 'stock', 'supplier_name', 
                 'description', 'raw_source_location', 'is_selected']


class FileMetadataSerializer(serializers.ModelSerializer):
    """Serializer для модели FileMetadata."""
    
    file = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = FileMetadata
        fields = ['id', 'file', 'contacts', 'extra_text', 
                 'summary', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    """Serializer для модели Order."""
    
    items_count = serializers.SerializerMethodField()
    resolved_items = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = ['id', 'created_at', 'items', 'resolved_items', 'export_format',
                 'export_file_path', 'items_count']
    
    def get_items_count(self, obj):
        """Возвращает количество позиций в заказе."""
        return len(obj.items or [])

    def get_resolved_items(self, obj):
        """
        Возвращает позиции заказа с человекочитаемыми полями.
        Для старых заказов, где в JSON только item_id/quantity, подтягиваем данные из ParsedItem.
        """
        rows = obj.items or []
        item_map = self.context.get('parsed_item_map')
        if item_map is None:
            item_ids = [row.get('item_id') or row.get('id') for row in rows]
            item_ids = [item_id for item_id in item_ids if item_id]
            item_map = ParsedItem.objects.in_bulk(item_ids) if item_ids else {}

        result = []
        for row in rows:
            item_id = row.get('item_id') or row.get('id')
            item = item_map.get(item_id)
            quantity = row.get('quantity') or 1
            result.append({
                'item_id': item_id,
                'quantity': quantity,
                'brewery': row.get('brewery') or (item.brewery if item else ''),
                'beer_name': row.get('beer_name') or (item.beer_name if item else ''),
                'format_type': row.get('format_type') or (item.format_type if item else ''),
                'price': row.get('price') if row.get('price') is not None else (float(item.price) if item and item.price is not None else None),
            })
        return result


class OrderCreateSerializer(serializers.Serializer):
    """Serializer для создания заказа."""
    
    items = serializers.ListField(
        child=serializers.DictField(),
        help_text='Список позиций: [{"item_id": 1, "quantity": 5}, ...]'
    )
    export_format = serializers.ChoiceField(
        choices=['pdf', 'excel'],
        default='excel'
    )
    
    def validate_items(self, value):
        """Валидация списка позиций."""
        if not value:
            raise serializers.ValidationError("Список позиций не может быть пустым")
        
        for item in value:
            if 'item_id' not in item or 'quantity' not in item:
                raise serializers.ValidationError(
                    "Каждая позиция должна содержать item_id и quantity"
                )
            if not isinstance(item['quantity'], int) or item['quantity'] <= 0:
                raise serializers.ValidationError(
                    "Количество должно быть положительным числом"
                )
        
        return value


class TapSerializer(serializers.ModelSerializer):
    """Serializer для модели Tap."""
    
    # Комбинированное поле для отображения
    current_beer = serializers.SerializerMethodField()
    
    class Meta:
        model = Tap
        fields = ['id', 'location', 'position', 'brewery',
                 'beer_name', 'price_per_liter', 'description',
                 'volume_price_text', 'bitterness_ibu', 'abv_text',
                 'label_image_url',
                 'next_beer_1',
                 'next_beer_2', 'color_current', 'color_next1',
                 'color_next2', 'status', 'is_visible', 'current_beer', 'updated_at']
        read_only_fields = ['updated_at']
    
    def get_current_beer(self, obj):
        """Возвращает строку 'Пивоварня | Название(Цена)'."""
        if not obj.brewery and not obj.beer_name:
            return ''
        parts = []
        if obj.brewery:
            parts.append(obj.brewery)
        if obj.beer_name:
            parts.append(obj.beer_name)
        result = ' | '.join(parts)
        # Цена в скобках — из price_per_liter; если задана строка объём/цена для экрана, не подмешиваем «за литр» (часто другая величина).
        vp = (obj.volume_price_text or '').strip()
        if vp:
            return result
        if obj.price_per_liter:
            result += f'({int(obj.price_per_liter)})'
        return result


class AvailableBeerSerializer(serializers.ModelSerializer):
    """Serializer для модели AvailableBeer."""
    
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AvailableBeer
        fields = ['id', 'location', 'brewery', 'beer_name',
                 'price_per_liter', 'description',
                 'volume_price_text', 'bitterness_ibu', 'abv_text',
                 'label_image_url',
                 'sort_order',
                 'display_name', 'created_at']
        read_only_fields = ['created_at']
    
    def get_display_name(self, obj):
        """Возвращает строку 'Пивоварня | Название(Цена)'."""
        result = f"{obj.brewery} | {obj.beer_name}"
        vp = (obj.volume_price_text or '').strip()
        if vp:
            return result
        if obj.price_per_liter:
            result += f'({int(obj.price_per_liter)})'
        return result


class TapLocationSerializer(serializers.ModelSerializer):
    """Serializer для модели TapLocation."""
    
    taps = TapSerializer(many=True, read_only=True)
    available_beers = AvailableBeerSerializer(many=True, read_only=True)
    taps_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TapLocation
        fields = ['id', 'name', 'created_at', 'taps', 
                 'available_beers', 'taps_count']
        read_only_fields = ['created_at']
    
    def get_taps_count(self, obj):
        """Возвращает количество кранов в локации."""
        return obj.taps.count()


class TapLocationListSerializer(serializers.ModelSerializer):
    """Краткий serializer для списка локаций."""
    
    taps_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = TapLocation
        fields = ['id', 'name', 'created_at', 'taps_count']


# --- Управление пользователями (админ-панель) ---


class UserSerializer(serializers.ModelSerializer):
    """Список пользователей: id, username, имена, роль."""
    role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role', 'is_active']
        read_only_fields = ['id', 'username']

    def get_role(self, obj):
        try:
            return obj.profile.role
        except UserProfile.DoesNotExist:
            return UserProfile.ROLE_USER


class UserCreateSerializer(serializers.Serializer):
    """Создание пользователя."""
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=1)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, default=UserProfile.ROLE_USER)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Пользователь с таким логином уже существует.')
        return value

    def create(self, validated_data):
        role = validated_data.pop('role')
        password = validated_data.pop('password')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email') or '',
            password=password,
            first_name=validated_data.get('first_name') or '',
            last_name=validated_data.get('last_name') or '',
        )
        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': role})
        profile.role = role
        profile.save()
        return user


class UserUpdateSerializer(serializers.Serializer):
    """Обновление пользователя: роль, имена, опционально пароль."""
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, required=False)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(required=False, allow_blank=True, write_only=True, min_length=1)


class ParseRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParseRun
        fields = [
            'id', 'file', 'supplier', 'user', 'pipeline_version', 'status',
            'items_count', 'warning_count', 'error_count', 'parse_kwargs',
            'summary', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class SupplierColumnMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierColumnMapping
        fields = [
            'id', 'supplier', 'scope', 'source_column', 'target_field',
            'file_pattern', 'confidence', 'meta', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class ParsingFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParsingFeedback
        fields = [
            'id', 'supplier', 'parse_run', 'user', 'source_column', 'suggested_field',
            'accepted', 'confidence', 'note', 'context', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'user']

