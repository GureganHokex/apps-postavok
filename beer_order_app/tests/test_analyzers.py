"""Тесты для анализаторов."""

import pytest
from src.analyzers import ContainerDetector, BeerAnalyzer


class TestContainerDetector:
    """Тесты для детектора тары."""

    def test_detect_keg(self):
        """Проверка определения кеги."""
        container_type, volume = ContainerDetector.detect("30л кега")
        assert container_type == 'keg'
        assert volume == 30.0

    def test_detect_can(self):
        """Проверка определения банки."""
        container_type, volume = ContainerDetector.detect("Банка 0.5л")
        assert container_type == 'can'
        assert volume == 0.5

    def test_detect_bottle(self):
        """Проверка определения бутылки."""
        container_type, volume = ContainerDetector.detect("Бутылка 0.33л")
        assert container_type == 'bottle'
        assert volume == 0.33

    def test_extract_volume_ml(self):
        """Проверка извлечения объема в миллилитрах."""
        _, volume = ContainerDetector.detect("500мл")
        assert volume == 0.5


class TestBeerAnalyzer:
    """Тесты для анализатора пива."""

    def test_detect_ipa_style(self):
        """Проверка определения IPA."""
        style = BeerAnalyzer.detect_style("IPA Pale Ale")
        assert style == 'IPA'

    def test_detect_lager_style(self):
        """Проверка определения Lager."""
        style = BeerAnalyzer.detect_style("Pilsner Lager")
        assert style == 'Lager'

    def test_is_beer(self):
        """Проверка определения пива."""
        assert BeerAnalyzer.is_beer("IPA пиво")
        assert not BeerAnalyzer.is_beer("Кола")

    def test_extract_brewery(self):
        """Проверка извлечения пивоварни."""
        brewery = BeerAnalyzer.extract_brewery("Мантра IPA")
        assert brewery == "Мантра"
