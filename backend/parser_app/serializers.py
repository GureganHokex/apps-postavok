"""
Serializers для API endpoints.
"""

from rest_framework import serializers
from .models import File, ParsedItem, FileMetadata, Order


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

