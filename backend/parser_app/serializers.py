"""
Serializers для API endpoints.
"""

from rest_framework import serializers
from .models import (
    File, ParsedItem, FileMetadata, Order, Supplier,
    TapLocation, Tap, AvailableBeer
)


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
    
    class Meta:
        model = Order
        fields = ['id', 'created_at', 'items', 'export_format', 
                 'export_file_path', 'items_count']
    
    def get_items_count(self, obj):
        """Возвращает количество позиций в заказе."""
        return len(obj.items)


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
                 'beer_name', 'price_per_liter', 'next_beer_1',
                 'next_beer_2', 'color_current', 'color_next1', 
                 'color_next2', 'status', 'current_beer', 'updated_at']
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
        if obj.price_per_liter:
            result += f'({int(obj.price_per_liter)})'
        return result


class AvailableBeerSerializer(serializers.ModelSerializer):
    """Serializer для модели AvailableBeer."""
    
    display_name = serializers.SerializerMethodField()
    
    class Meta:
        model = AvailableBeer
        fields = ['id', 'location', 'brewery', 'beer_name', 
                 'price_per_liter', 'display_name', 'created_at']
        read_only_fields = ['created_at']
    
    def get_display_name(self, obj):
        """Возвращает строку 'Пивоварня | Название(Цена)'."""
        result = f"{obj.brewery} | {obj.beer_name}"
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
    
    taps_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TapLocation
        fields = ['id', 'name', 'created_at', 'taps_count']
    
    def get_taps_count(self, obj):
        return obj.taps.count()

