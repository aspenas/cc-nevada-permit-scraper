import pytest
from unittest.mock import MagicMock, patch
from scraper.enhanced_detail_scraper_final import (
    EnhancedDetailScraper, PermitDetails
)


@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    monkeypatch.setenv('CLARK_COUNTY_USERNAME', 'testuser')
    monkeypatch.setenv('CLARK_COUNTY_PASSWORD', 'testpass')


def test_constructor_env_vars():
    scraper = EnhancedDetailScraper(headless=True)
    assert scraper.username == 'testuser'
    assert scraper.password == 'testpass'


def test_parse_address_advanced_valid():
    scraper = EnhancedDetailScraper(headless=True)
    address = '123 Main St, Las Vegas, NV 89101'
    parsed = scraper.parse_address_advanced(address)
    assert parsed['street_number'] == '123'
    assert parsed['city'] == 'Las Vegas'
    assert parsed['state'] == 'NV' or parsed['state'] == 'Nevada'
    assert parsed['zip'] == '89101'


def test_parse_address_advanced_fallback(monkeypatch):
    scraper = EnhancedDetailScraper(headless=True)
    # Patch usaddress.tag to raise Exception
    with patch(
        'scraper.enhanced_detail_scraper_final.usaddress.tag',
        side_effect=Exception('fail'),
    ):
        fallback = scraper.parse_address_advanced('bad address')
        assert isinstance(fallback, dict)
        assert fallback['state'] == 'NV'


def test_extract_financial_value_edge_cases():
    scraper = EnhancedDetailScraper(headless=True)
    # Negative value
    assert scraper.extract_financial_value('-100') is None
    # Empty string
    assert scraper.extract_financial_value('') is None
    # Non-numeric
    assert scraper.extract_financial_value('notanumber') is None
    # Zero
    assert scraper.extract_financial_value('0') == 0.0
    # Large value
    assert scraper.extract_financial_value('1000000000') == 1_000_000_000.0


def test_extraction_error_logging_on_login_failure(monkeypatch):
    scraper = EnhancedDetailScraper(headless=True)
    scraper.setup_driver = MagicMock()
    # Simulate login failure
    scraper.login_to_clark_county = MagicMock(return_value=False)
    # Patch extract_permit_details to avoid real Selenium
    with patch.object(
        scraper, 'extract_permit_details', wraps=scraper.extract_permit_details
    ):
        result = scraper.scrape_permit('BAD-LOGIN')
        # Should return None due to login failure
        assert result is None or (
            hasattr(result, 'extraction_errors') and 
            'Login failed' in result.extraction_errors
        )


def test_validate_financial_data_flags():
    scraper = EnhancedDetailScraper(headless=True)
    data = {'job_value': 50}
    data['data_quality_flags'] = []
    scraper.validate_financial_data(data)
    assert 'low_job_value' in data['data_quality_flags']
    data = {'job_value': 1e9, 'data_quality_flags': []}
    scraper.validate_financial_data(data)
    assert 'high_job_value' in data['data_quality_flags']
    data = {'job_value': 60_000_000, 'data_quality_flags': []}
    scraper.validate_financial_data(data)
    assert 'high_job_value_warning' in data['data_quality_flags']


def test_scrape_permit_smoke(monkeypatch):
    # Patch Selenium driver and methods for a fast smoke test
    scraper = EnhancedDetailScraper(headless=True)
    scraper.setup_driver = MagicMock()
    scraper.login_to_clark_county = MagicMock(return_value=True)
    scraper.extract_permit_details = MagicMock(
        return_value=PermitDetails(permit_number='TEST123')
    )
    scraper.save_to_database = MagicMock()
    result = scraper.scrape_permit('TEST123')
    assert result.permit_number == 'TEST123' 