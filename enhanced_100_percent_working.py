#!/usr/bin/env python3
"""
Enhanced Working Scraper - Path to 100% Completeness

This version builds on the working 47% scraper to add:
1. Section expansion for "More Details"
2. Better table parsing
3. Additional field extraction
"""

import os
import re
import sqlite3
from datetime import datetime
from selenium.webdriver.common.by import By
from dotenv import load_dotenv
from loguru import logger
import time
import sys

# --- AWS SecretsManager integration for credentials ---
def fetch_and_set_aws_secret(secret_name: str, region_name: str = None):
    try:
        import boto3
        import json as _json
        session = boto3.session.Session()
        if region_name is None:
            region_name = session.region_name or 'us-west-2'
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
        secret = get_secret_value_response['SecretString']
        secret_dict = _json.loads(secret)
        for k, v in secret_dict.items():
            os.environ[k] = v
    except Exception as e:
        print(f"[WARN] Could not fetch secret from AWS: {e}")

# Try to load from .env, else fetch from AWS
if not (os.getenv('CLARK_COUNTY_USERNAME') and os.getenv('CLARK_COUNTY_PASSWORD')):
    fetch_and_set_aws_secret('clark-county-permit-scraper')

load_dotenv()

# Import the working base scraper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from enhanced_detail_scraper_final import EnhancedDetailScraper

class Enhanced100PercentScraper:
    """Enhanced scraper targeting 100% completeness"""
    
    def __init__(self):
        # Use the working base scraper
        self._base_scraper = EnhancedDetailScraper()
        self.driver = None
        self.wait = None
        self.expanded_sections = set()
        
    def setup_driver(self):
        """Setup driver using base scraper"""
        self._base_scraper.setup_driver()
        self.driver = self._base_scraper.driver
        self.wait = self._base_scraper.wait
        logger.info("Enhanced driver ready for 100% extraction")
        
    def login_to_clark_county(self):
        """Login using base scraper"""
        self._base_scraper.login_to_clark_county()
        
    def search_for_permit(self, permit_number: str) -> bool:
        """Search using base scraper"""
        return self._base_scraper.search_for_permit(permit_number)
        
    def expand_all_sections(self):
        """Expand all collapsible sections to reveal hidden data"""
        logger.info("Expanding all sections for complete data access...")
        expanded_count = 0
        
        # Click patterns for expandable content
        expand_patterns = [
            "More Details",
            "Show More", 
            "View Details",
            "Additional Information",
            "Show All",
            "Fee Details",
            "View More"
        ]
        
        for pattern in expand_patterns:
            try:
                # Find elements with expand text
                elements = self.driver.find_elements(
                    By.XPATH,
                    f"//a[contains(text(), '{pattern}')] | //button[contains(text(), '{pattern}')] | //span[contains(text(), '{pattern}') and @onclick]"
                )
                
                for elem in elements:
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            # Scroll to element
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                            time.sleep(0.3)
                            
                            # Click
                            try:
                                elem.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", elem)
                            
                            expanded_count += 1
                            logger.debug(f"Clicked: {pattern}")
                            time.sleep(0.5)
                    except:
                        pass
            except:
                pass
                
        logger.info(f"Expanded {expanded_count} sections")
        return expanded_count
        
    def extract_enhanced_details(self, permit_number: str) -> Dict:
        """Extract all details including expanded sections"""
        # First get base details using working scraper
        base_details = self._base_scraper.extract_permit_details()
        
        # Expand all sections
        self.expand_all_sections()
        time.sleep(1)
        
        # Extract additional fields
        enhanced_details = {
            'permit_number': base_details.permit_number,
            'status': base_details.status,
            'type': base_details.permit_type,
            'owner_name': base_details.owner_name,
            'project_address': base_details.project_address,
            'contractor_name': base_details.contractor,
            'record_date': base_details.applied_date,
            'finaled_date': base_details.final_date,
            'scraped_date': datetime.now().isoformat()
        }
        
        # Extract additional high-value fields
        self._extract_dates(enhanced_details)
        self._extract_financial_data(enhanced_details)
        self._extract_property_data(enhanced_details)
        self._extract_from_tables(enhanced_details)
        
        # Calculate new completeness
        enhanced_details['completeness_score'] = self._calculate_completeness(enhanced_details)
        
        return enhanced_details
        
    def _extract_dates(self, details: Dict):
        """Extract all date fields"""
        date_mappings = {
            'Applied': 'applied_date',
            'Application Date': 'applied_date',
            'Issued': 'issued_date',
            'Issue Date': 'issued_date',
            'Expiration': 'expiration_date',
            'Final': 'finaled_date',
            'Last Inspection': 'last_inspection_date'
        }
        
        for label, field in date_mappings.items():
            if field not in details or not details.get(field):
                try:
                    # Try to find date
                    elem = self.driver.find_element(
                        By.XPATH,
                        f"//*[contains(text(), '{label}')]/.."
                    )
                    text = elem.text
                    date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
                    if date_match:
                        details[field] = date_match.group(1)
                        logger.debug(f"Found {field}: {date_match.group(1)}")
                except:
                    pass
                    
    def _extract_financial_data(self, details: Dict):
        """Extract financial fields including funded amount"""
        try:
            # Look for job value/valuation
            if 'valuation' not in details:
                try:
                    elem = self.driver.find_element(
                        By.XPATH,
                        "//*[contains(text(), 'Job Value') or contains(text(), 'Valuation')]/.."
                    )
                    value_match = re.search(r'\$?([0-9,]+(?:\.[0-9]{2})?)', elem.text)
                    if value_match:
                        details['valuation'] = value_match.group(1).replace(',', '')
                except:
                    pass
                    
            # Look for funded amount (from expanded sections)
            if 'funded_amount' not in details:
                try:
                    elem = self.driver.find_element(
                        By.XPATH,
                        "//*[contains(text(), 'Funded Amount') or contains(text(), 'Funding Amount')]/.."
                    )
                    value_match = re.search(r'\$?([0-9,]+(?:\.[0-9]{2})?)', elem.text)
                    if value_match:
                        details['funded_amount'] = value_match.group(1).replace(',', '')
                        logger.info(f"Found funded amount: ${value_match.group(1)}")
                except:
                    pass
                    
            # Total fees
            if 'total_fees' not in details:
                try:
                    elem = self.driver.find_element(
                        By.XPATH,
                        "//*[contains(text(), 'Total Fee')]/.."
                    )
                    value_match = re.search(r'\$?([0-9,]+(?:\.[0-9]{2})?)', elem.text)
                    if value_match:
                        details['total_fees'] = value_match.group(1).replace(',', '')
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Error extracting financial data: {e}")
            
    def _extract_property_data(self, details: Dict):
        """Extract property information"""
        try:
            # Parcel number
            if 'parcel_number' not in details:
                try:
                    elem = self.driver.find_element(
                        By.XPATH,
                        "//*[contains(text(), 'Parcel') or contains(text(), 'APN')]/.."
                    )
                    parcel_match = re.search(r'([0-9-]+)', elem.text)
                    if parcel_match:
                        details['parcel_number'] = parcel_match.group(1)
                except:
                    pass
                    
            # Square footage
            if 'square_footage' not in details:
                try:
                    elem = self.driver.find_element(
                        By.XPATH,
                        "//*[contains(text(), 'Square') or contains(text(), 'Sq Ft')]/.."
                    )
                    sq_match = re.search(r'(\d+(?:,\d+)?)', elem.text)
                    if sq_match:
                        details['square_footage'] = sq_match.group(1).replace(',', '')
                except:
                    pass
                    
            # Zoning
            if 'zoning' not in details:
                try:
                    elem = self.driver.find_element(
                        By.XPATH,
                        "//*[contains(text(), 'Zoning')]/.."
                    )
                    zone_match = re.search(r'Zoning[:\s]*([A-Z0-9-]+)', elem.text)
                    if zone_match:
                        details['zoning'] = zone_match.group(1)
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Error extracting property data: {e}")
            
    def _extract_from_tables(self, details: Dict):
        """Extract data from all tables"""
        try:
            tables = self.driver.find_elements(By.TAG_NAME, "table")
            
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    
                    if len(cells) == 2:
                        label = cells[0].text.strip().lower()
                        value = cells[1].text.strip()
                        
                        if value and value != 'N/A':
                            # Map common labels
                            if 'description' in label and 'description' not in details:
                                details['description'] = value
                            elif 'subdivision' in label and 'subdivision' not in details:
                                details['subdivision'] = value
                            elif 'lot' in label and 'lot' not in details:
                                details['lot'] = value
                            elif 'block' in label and 'block' not in details:
                                details['block'] = value
                            elif 'construction type' in label and 'construction_type' not in details:
                                details['construction_type'] = value
                            elif 'dwelling unit' in label and 'dwelling_units' not in details:
                                details['dwelling_units'] = value
                                
        except Exception as e:
            logger.debug(f"Error extracting from tables: {e}")
            
    def _calculate_completeness(self, details: Dict) -> float:
        """Calculate completeness with all fields"""
        field_weights = {
            'permit_number': 10, 'project_address': 10,
            'type': 8, 'status': 8,
            'applied_date': 7,
            'owner_name': 6, 'valuation': 6, 'funded_amount': 6,
            'description': 5, 'issued_date': 5, 'parcel_number': 5,
            'contractor_name': 3, 'total_fees': 3, 'square_footage': 3, 'zoning': 3,
            'subdivision': 2, 'lot': 2, 'block': 2, 'construction_type': 2,
            'dwelling_units': 2, 'record_date': 2,
            'finaled_date': 1, 'expiration_date': 1, 'last_inspection_date': 1
        }
        
        total_weight = sum(field_weights.values())
        achieved_weight = 0
        
        for field, weight in field_weights.items():
            if details.get(field) and str(details[field]).strip():
                achieved_weight += weight
                
        return round((achieved_weight / total_weight) * 100, 1)
        
    def save_to_database(self, details: Dict):
        """Save enhanced details to database"""
        conn = sqlite3.connect('data/permits/automated_permits.db')
        cursor = conn.cursor()
        
        # Add new columns if needed
        try:
            cursor.execute("ALTER TABLE permits ADD COLUMN funded_amount TEXT")
            cursor.execute("ALTER TABLE permits ADD COLUMN applied_date TEXT")
            cursor.execute("ALTER TABLE permits ADD COLUMN issued_date TEXT")
            cursor.execute("ALTER TABLE permits ADD COLUMN expiration_date TEXT")
            cursor.execute("ALTER TABLE permits ADD COLUMN last_inspection_date TEXT")
        except:
            pass
            
        # Update permit record
        cursor.execute("""
        UPDATE permits SET
            status = ?,
            type = ?,
            valuation = ?,
            funded_amount = ?,
            owner_name = ?,
            project_address = ?,
            contractor_name = ?,
            record_date = ?,
            finaled_date = ?,
            completeness_score = ?,
            scraped_date = ?,
            description = ?,
            parcel_number = ?,
            square_footage = ?,
            zoning = ?,
            subdivision = ?,
            lot = ?,
            block = ?,
            construction_type = ?,
            dwelling_units = ?,
            total_fees = ?,
            applied_date = ?,
            issued_date = ?,
            expiration_date = ?,
            last_inspection_date = ?
        WHERE permit_number = ?
        """, (
            details.get('status'),
            details.get('type'),
            details.get('valuation'),
            details.get('funded_amount'),
            details.get('owner_name'),
            details.get('project_address'),
            details.get('contractor_name'),
            details.get('record_date'),
            details.get('finaled_date'),
            details.get('completeness_score'),
            details.get('scraped_date'),
            details.get('description'),
            details.get('parcel_number'),
            details.get('square_footage'),
            details.get('zoning'),
            details.get('subdivision'),
            details.get('lot'),
            details.get('block'),
            details.get('construction_type'),
            details.get('dwelling_units'),
            details.get('total_fees'),
            details.get('applied_date'),
            details.get('issued_date'),
            details.get('expiration_date'),
            details.get('last_inspection_date'),
            details.get('permit_number')
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Updated permit {details['permit_number']} with {details['completeness_score']}% completeness")
        
    def scrape_permit(self, permit_number: str) -> Dict:
        """Main scraping method"""
        if self.search_for_permit(permit_number):
            time.sleep(2)
            details = self.extract_enhanced_details(permit_number)
            self.save_to_database(details)
            return details
        else:
            return {'permit_number': permit_number, 'completeness_score': 0}
            
    def close(self):
        """Close browser"""
        self._base_scraper.close()

# Example usage
if __name__ == "__main__":
    test_permits = ['BD25-23553', 'BD25-23477', 'BD25-23463']
    
    scraper = Enhanced100PercentScraper()
    scraper.setup_driver()
    
    try:
        scraper.login_to_clark_county()
        
        results = []
        for permit_number in test_permits:
            print(f"\n{'='*60}")
            print(f"Scraping: {permit_number}")
            print('='*60)
            
            details = scraper.scrape_permit(permit_number)
            results.append(details)
            
            print(f"\n✓ Completeness: {details['completeness_score']}%")
            
            # Show key fields
            key_fields = ['type', 'status', 'owner_name', 'project_address', 
                         'valuation', 'funded_amount', 'applied_date', 'parcel_number']
            
            print("\nKey Fields:")
            for field in key_fields:
                if field in details and details[field]:
                    print(f"  • {field}: {details[field]}")
                    
            # Show additional fields
            print("\nAdditional Fields:")
            other_fields = [k for k in details.keys() 
                          if k not in key_fields and k not in ['permit_number', 'completeness_score', 'scraped_date']]
            
            for field in other_fields:
                if details.get(field):
                    print(f"  • {field}: {details[field]}")
                    
        # Summary
        print(f"\n{'='*80}")
        print("ENHANCED SCRAPING SUMMARY")
        print('='*80)
        print(f"Total permits: {len(results)}")
        avg_completeness = sum(r['completeness_score'] for r in results) / len(results)
        print(f"Average completeness: {avg_completeness:.1f}%")
        print(f"Improvement: {avg_completeness - 47:.1f}% (from 47% baseline)")
        
    finally:
        scraper.close()