#!/usr/bin/env python3
"""
Enhanced Clark County Permit Detail Scraper with Authentication
Extracts comprehensive permit details with data quality validation and
completeness scoring
"""

import re
import json
import time
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path
import os
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from loguru import logger
import usaddress
import boto3
import great_expectations as ge
import watchtower  # CloudWatch logging handler

# Load environment variables
load_dotenv()

# Configure logging
logger.add("scraper_errors.log", level="ERROR", rotation="10 MB")
logger.add(
    "scraper_debug.log",
    level="DEBUG",
    rotation="50 MB"
)

# Financial validation thresholds
JOB_VALUE_MIN = 100  # $100 minimum
JOB_VALUE_MAX = 500_000_000  # $500M maximum
JOB_VALUE_WARNING_THRESHOLD = 50_000_000  # $50M warning threshold

# --- CloudWatch Logging Integration ---
CLOUDWATCH_LOG_GROUP = os.getenv("CLOUDWATCH_LOG_GROUP", f"/aws/cc-nevada-permit-scraper/{os.getenv('ENVIRONMENT', 'prod')}")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")

try:
    logger.add(
        watchtower.CloudWatchLogHandler(
            log_group=CLOUDWATCH_LOG_GROUP,
            region_name=AWS_REGION,
        ),
        level="INFO",
        enqueue=True,
        serialize=True,
    )
    logger.info(f"CloudWatch logging enabled: {CLOUDWATCH_LOG_GROUP}")
except Exception as e:
    logger.warning(f"CloudWatch logging not enabled: {e}")

@dataclass
class PermitDetails:
    """Data class for permit details with validation"""
    # Basic info
    permit_number: str
    permit_type: Optional[str] = None
    permit_subtype: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    
    # Dates
    applied_date: Optional[str] = None
    issued_date: Optional[str] = None
    final_date: Optional[str] = None
    expiration_date: Optional[str] = None
    
    # Location
    address: Optional[str] = None
    parsed_address: Dict[str, Any] = field(default_factory=dict)
    parcel_number: Optional[str] = None
    subdivision: Optional[str] = None
    lot: Optional[str] = None
    block: Optional[str] = None
    
    # People
    owner_name: Optional[str] = None
    contractor_name: Optional[str] = None
    contractor_license: Optional[str] = None
    applicant_name: Optional[str] = None
    
    # Financial
    job_value: Optional[float] = None
    total_fees: Optional[float] = None
    fees_paid: Optional[float] = None
    fees_due: Optional[float] = None
    itemized_fees: List[Dict[str, Any]] = field(default_factory=list)
    
    # Additional details
    square_footage: Optional[int] = None
    dwelling_units: Optional[int] = None
    stories: Optional[int] = None
    construction_type: Optional[str] = None
    
    # Inspection info
    inspections_count: Optional[int] = None
    passed_inspections: Optional[int] = None
    failed_inspections: Optional[int] = None
    pending_inspections: Optional[int] = None
    
    # New fields for better data quality
    zoning: Optional[str] = None
    use_code: Optional[str] = None
    occupancy_type: Optional[str] = None
    lot_size: Optional[str] = None
    project_name: Optional[str] = None
    work_description: Optional[str] = None
    
    # Related permits
    related_permits: List[str] = field(default_factory=list)
    
    # Coordinates (if available)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Quality metrics
    completeness_score: float = 0.0
    extraction_errors: List[str] = field(default_factory=list)
    data_quality_flags: List[str] = field(default_factory=list)
    
    # Validation flags
    address_validation_flag: Optional[str] = None
    job_value_validation_flag: Optional[str] = None
    
    # Metadata
    scraped_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    page_structure_hash: Optional[str] = None

class EnhancedDetailScraper:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver = None
        self.wait = None
        
        # Get credentials from environment
        self.username = os.getenv('CLARK_COUNTY_USERNAME')
        self.password = os.getenv('CLARK_COUNTY_PASSWORD')
        
        if not self.username or not self.password:
            raise ValueError("Missing CLARK_COUNTY_USERNAME or CLARK_COUNTY_PASSWORD in environment variables")
        
        # Financial validation thresholds
        self.JOB_VALUE_MIN = JOB_VALUE_MIN
        self.JOB_VALUE_MAX = JOB_VALUE_MAX
        self.JOB_VALUE_WARNING_THRESHOLD = JOB_VALUE_WARNING_THRESHOLD
        
    def setup_driver(self):
        """Setup Chrome driver with options"""
        options = Options()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)
        logger.info(
            "Chrome driver initialized"
        )
        
    def login_to_clark_county(self) -> bool:
        """Login to Clark County permit system"""
        try:
            logger.info(
                f"Attempting to login as {self.username}"
            )
            
            # Navigate to login page
            login_url = "https://aca-prod.accela.com/CLARKCO/Login.aspx"
            self.driver.get(login_url)
            time.sleep(3)
            
            # Switch to login iframe
            login_frame = self.wait.until(
                EC.presence_of_element_located((By.ID, "LoginFrame"))
            )
            self.driver.switch_to.frame(login_frame)
            logger.debug(
                "Switched to login iframe"
            )
            
            # Enter username
            username_field = self.wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            username_field.clear()
            username_field.send_keys(self.username)
            logger.debug("Entered username")
            
            # Enter password
            password_field = self.driver.find_element(By.ID, "passwordRequired")
            password_field.clear()
            password_field.send_keys(self.password)
            logger.debug("Entered password")
            
            # Submit by pressing Enter (button may be hidden)
            from selenium.webdriver.common.keys import Keys
            password_field.send_keys(Keys.RETURN)
            logger.debug("Submitted login form via Enter key")
            
            # Switch back to main content
            self.driver.switch_to.default_content()
            
            # Wait for login to complete
            time.sleep(5)
            
            # Check if login was successful
            if "Login.aspx" not in self.driver.current_url:
                logger.info("Login successful")
                return True
            else:
                logger.error("Login failed - still on login page")
                return False
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def parse_address_advanced(self, address: str) -> Dict[str, Any]:
        """Parse address using usaddress library with fallback"""
        try:
            # Clean address
            address = re.sub(r'\s+', ' ', address.strip())
            
            # Use usaddress for parsing
            parsed, addr_type = usaddress.tag(address)
            
            # Convert to our format
            result = {
                'street_number': parsed.get('AddressNumber', ''),
                'street_direction': parsed.get('StreetNamePreDirectional', ''),
                'street_name': parsed.get('StreetName', ''),
                'street_type': parsed.get('StreetNamePostType', ''),
                'street_suffix': parsed.get('StreetNamePostDirectional', ''),
                'city': parsed.get('PlaceName', ''),
                'state': parsed.get('StateName', ''),
                'zip': parsed.get('ZipCode', ''),
                'unit': parsed.get('OccupancyIdentifier', ''),
                'parsed_type': addr_type
            }
            
            # Build full street address
            street_parts = [
                result['street_number'],
                result['street_direction'],
                result['street_name'],
                result['street_type'],
                result['street_suffix']
            ]
            result['street_address'] = ' '.join(p for p in street_parts if p)
            
            return result
            
        except Exception as e:
            logger.warning(
                f"Advanced address parsing failed: {e}"
            )
            # Fallback to basic regex parsing
            return self.parse_address_fallback(address)
    
    def parse_address_fallback(self, address: str) -> Dict[str, Any]:
        """Fallback address parsing using regex"""
        result = {
            'street_number': '',
            'street_name': '',
            'street_type': '',
            'city': '',
            'state': 'NV',
            'zip': '',
            'street_address': ''
        }
        
        # Try to extract components
        zip_match = re.search(r'\b(\d{5})(?:-\d{4})?\b', address)
        if zip_match:
            result['zip'] = zip_match.group(1)
        
        # Simple street parsing
        street_match = re.match(r'^(\d+)\s+(.+?)(?:,|$)', address)
        if street_match:
            result['street_number'] = street_match.group(1)
            result['street_address'] = street_match.group(0).strip().rstrip(',')
        
        return result
    
    def extract_financial_value(self, text: str) -> Optional[float]:
        """Extract and validate financial values"""
        if not text:
            return None
            
        # Remove currency symbols and commas
        cleaned = re.sub(r'[$,]', '', text.strip())
        
        try:
            value = float(cleaned)
            
            # Validate range
            if value < 0:
                logger.warning(f"Negative financial value: ${value}")
                return None
            
            return value
        except ValueError:
            logger.warning(
                f"Could not parse financial value: {text}"
            )
            return None
    
    def validate_financial_data(self, data: Dict[str, Any]) -> None:
        """Validate financial data and set flags"""
        if 'job_value' in data and data['job_value'] is not None:
            value = float(data['job_value'])
            
            if value < self.JOB_VALUE_MIN:
                logger.warning(
                    f"Suspiciously low job value: ${value:,.2f}"
                )
                data['job_value_validation_flag'] = 'too_low'
                data['data_quality_flags'].append('low_job_value')
            elif value > self.JOB_VALUE_MAX:
                logger.error(f"Suspiciously high job value: ${value:,.2f}")
                data['job_value_validation_flag'] = 'too_high'
                data['data_quality_flags'].append('high_job_value')
            elif value > self.JOB_VALUE_WARNING_THRESHOLD:
                logger.warning(f"High job value (above warning threshold): ${value:,.2f}")
                data['job_value_validation_flag'] = 'high_warning'
                data['data_quality_flags'].append('high_job_value_warning')
    
    def calculate_completeness_score(self, details: PermitDetails) -> float:
        """Calculate data completeness score (0-100)"""
        # Define field weights
        field_weights = {
            # Critical fields (high weight)
            'permit_number': 10,
            'permit_type': 8,
            'status': 8,
            'address': 10,
            'applied_date': 7,
            
            # Important fields (medium weight)
            'owner_name': 6,
            'job_value': 6,
            'description': 5,
            'issued_date': 5,
            'parcel_number': 5,
            
            # Nice to have fields (low weight)
            'contractor_name': 3,
            'total_fees': 3,
            'square_footage': 3,
            'zoning': 3,
            'subdivision': 2,
            'lot': 2,
            'block': 2,
            'construction_type': 2,
            'dwelling_units': 2,
            
            # Additional fields
            'work_description': 2,
            'use_code': 2,
            'occupancy_type': 2,
            'project_name': 1,
            'lot_size': 1
        }
        
        total_weight = sum(field_weights.values())
        earned_weight = 0
        
        for field_name, weight in field_weights.items():
            value = getattr(details, field_name, None)
            if value is not None and str(value).strip():
                earned_weight += weight
        
        # Check parsed address quality
        if details.parsed_address and details.parsed_address.get('street_name'):
            earned_weight += 5  # Bonus for good address parsing
        
        # Check for related data
        if details.related_permits:
            earned_weight += 2
        
        if details.itemized_fees:
            earned_weight += 2
        
        # Calculate score
        score = (earned_weight / total_weight) * 100
        return round(score, 2)
    
    def get_page_structure_hash(self) -> str:
        """Generate hash of page structure for change detection"""
        try:
            # Get all data labels
            labels = self.driver.find_elements(By.CSS_SELECTOR, "span.NotBreakWord")
            label_texts = [label.text.strip() for label in labels if label.text.strip()]
            
            # Create hash of structure
            structure_string = '|'.join(sorted(label_texts))
            return hashlib.md5(structure_string.encode()).hexdigest()
        except:
            return "unknown"
    
    def safe_extract(self, selector: str, by: By = By.XPATH, 
                     attribute: Optional[str] = None) -> Optional[str]:
        """Safely extract text or attribute from element"""
        try:
            element = self.driver.find_element(by, selector)
            if attribute:
                return element.get_attribute(attribute)
            return element.text.strip()
        except NoSuchElementException:
            return None
        except Exception as e:
            logger.debug(
                f"Extraction error for {selector}: {e}"
            )
            return None
    
    def extract_fees_table(self) -> List[Dict[str, Any]]:
        """Extract itemized fees from fee table"""
        fees = []
        try:
            # Look for fee table
            fee_rows = self.driver.find_elements(By.CSS_SELECTOR, "table#tblFees tr, table.fee-table tr")
            
            for row in fee_rows[1:]:  # Skip header row
                cells = row.find_elements(By.TAG_NAME, "td")
                if len(cells) >= 3:
                    fee_item = {
                        'description': cells[0].text.strip(),
                        'amount': self.extract_financial_value(cells[1].text),
                        'status': cells[2].text.strip() if len(cells) > 2 else 'Unknown'
                    }
                    if fee_item['amount'] is not None:
                        fees.append(fee_item)
        except Exception as e:
            logger.debug(f"Could not extract fee table: {e}")
        
        return fees
    
    def extract_related_permits(self) -> List[str]:
        """Extract related permit numbers"""
        related = []
        try:
            # Look for related permits section
            related_links = self.driver.find_elements(
                By.XPATH, "//a[contains(@href, 'PermitDetail') and contains(text(), '-')]"
            )
            for link in related_links:
                permit_text = link.text.strip()
                if re.match(r'[A-Z]{2,3}-\d{4}-\d+', permit_text):
                    related.append(permit_text)
        except Exception as e:
            logger.debug(f"Could not extract related permits: {e}")
        
        return list(set(related))  # Remove duplicates
    
    def extract_permit_details(self, permit_url: str) -> PermitDetails:
        """Extract comprehensive permit details from page"""
        details = PermitDetails(permit_number="Unknown")
        
        try:
            # Navigate to permit page
            self.driver.get(permit_url)
            time.sleep(2)
            
            # Check if we need to login
            if "Login.aspx" in self.driver.current_url:
                logger.info("Session expired, logging in again...")
                if not self.login_to_clark_county():
                    details.extraction_errors.append("Login failed")
                    return details
                # Navigate back to permit page
                self.driver.get(permit_url)
                time.sleep(2)
            
            # Get page structure hash
            details.page_structure_hash = self.get_page_structure_hash()
            
            # Extract permit number from URL or page
            permit_match = re.search(r'PermitNumber=([^&]+)', permit_url)
            if permit_match:
                details.permit_number = permit_match.group(1)
            
            # Extract all labeled data using the common pattern
            labels = self.driver.find_elements(By.CSS_SELECTOR, "span.NotBreakWord")
            
            for label in labels:
                label_text = label.text.strip().lower()
                
                # Find the corresponding value element
                value_elem = None
                try:
                    # Try next sibling
                    parent = label.find_element(By.XPATH, "..")
                    value_elem = parent.find_element(By.XPATH, "following-sibling::td[1]")
                except:
                    # Try other patterns
                    try:
                        value_elem = label.find_element(By.XPATH, "../../td[2]")
                    except:
                        continue
                
                if value_elem:
                    value = value_elem.text.strip()
                    
                    # Map label to field
                    if 'permit type' in label_text:
                        details.permit_type = value
                    elif 'sub type' in label_text:
                        details.permit_subtype = value
                    elif 'status' in label_text and 'inspection' not in label_text:
                        details.status = value
                    elif 'description' in label_text and 'work' not in label_text:
                        details.description = value
                    elif 'work description' in label_text:
                        details.work_description = value
                    elif 'applied' in label_text:
                        details.applied_date = value
                    elif 'issued' in label_text:
                        details.issued_date = value
                    elif 'final' in label_text and 'date' in label_text:
                        details.final_date = value
                    elif 'expire' in label_text:
                        details.expiration_date = value
                    elif 'address' in label_text and 'mail' not in label_text:
                        details.address = value
                        details.parsed_address = self.parse_address_advanced(value)
                    elif 'parcel' in label_text:
                        details.parcel_number = value
                    elif 'subdivision' in label_text:
                        details.subdivision = value
                    elif 'lot' in label_text and 'size' not in label_text:
                        details.lot = value
                    elif 'lot size' in label_text:
                        details.lot_size = value
                    elif 'block' in label_text:
                        details.block = value
                    elif 'owner' in label_text:
                        details.owner_name = value
                    elif 'contractor' in label_text and 'license' not in label_text:
                        details.contractor_name = value
                    elif 'license' in label_text:
                        details.contractor_license = value
                    elif 'applicant' in label_text:
                        details.applicant_name = value
                    elif 'job value' in label_text or 'valuation' in label_text:
                        details.job_value = self.extract_financial_value(value)
                    elif 'total fee' in label_text:
                        details.total_fees = self.extract_financial_value(value)
                    elif 'paid' in label_text and 'fee' in label_text:
                        details.fees_paid = self.extract_financial_value(value)
                    elif 'due' in label_text and 'fee' in label_text:
                        details.fees_due = self.extract_financial_value(value)
                    elif 'square' in label_text:
                        try:
                            details.square_footage = int(re.sub(r'[^\d]', '', value))
                        except:
                            pass
                    elif 'dwelling' in label_text or 'unit' in label_text:
                        try:
                            details.dwelling_units = int(re.sub(r'[^\d]', '', value))
                        except:
                            pass
                    elif 'stories' in label_text or 'story' in label_text:
                        try:
                            details.stories = int(re.sub(r'[^\d]', '', value))
                        except:
                            pass
                    elif 'construction type' in label_text:
                        details.construction_type = value
                    elif 'zoning' in label_text:
                        details.zoning = value
                    elif 'use code' in label_text:
                        details.use_code = value
                    elif 'occupancy' in label_text:
                        details.occupancy_type = value
                    elif 'project' in label_text and 'name' in label_text:
                        details.project_name = value
            
            # Extract itemized fees
            details.itemized_fees = self.extract_fees_table()
            
            # Extract related permits
            details.related_permits = self.extract_related_permits()
            
            # Extract inspection counts
            try:
                inspection_rows = self.driver.find_elements(By.CSS_SELECTOR, "table#gvInspection tr, table.inspection-table tr")
                if len(inspection_rows) > 1:
                    details.inspections_count = len(inspection_rows) - 1
                    
                    # Count inspection statuses
                    passed = failed = pending = 0
                    for row in inspection_rows[1:]:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        for cell in cells:
                            cell_text = cell.text.lower()
                            if 'pass' in cell_text:
                                passed += 1
                            elif 'fail' in cell_text:
                                failed += 1
                            elif 'pending' in cell_text or 'scheduled' in cell_text:
                                pending += 1
                    
                    details.passed_inspections = passed
                    details.failed_inspections = failed
                    details.pending_inspections = pending
            except Exception as e:
                logger.debug(f"Could not extract inspection data: {e}")
                details.extraction_errors.append(f"Inspection extraction: {str(e)}")
            
            # Validate financial data
            self.validate_financial_data(details.__dict__)
            
            # Calculate completeness score
            details.completeness_score = self.calculate_completeness_score(details)
            
            logger.info(f"Successfully extracted permit {details.permit_number} with {details.completeness_score}% completeness")
            
        except Exception as e:
            logger.error(f"Error extracting permit details: {e}")
            details.extraction_errors.append(f"General extraction error: {str(e)}")
        
        return details
    
    def save_to_database(self, details: PermitDetails, db_path: str = "permits.db"):
        """Save permit details to database with enhanced schema"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create enhanced table if not exists
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS permit_details_enhanced (
            permit_number TEXT PRIMARY KEY,
            permit_type TEXT,
            permit_subtype TEXT,
            status TEXT,
            description TEXT,
            work_description TEXT,
            
            applied_date TEXT,
            issued_date TEXT,
            final_date TEXT,
            expiration_date TEXT,
            
            address TEXT,
            parsed_street_number TEXT,
            parsed_street_name TEXT,
            parsed_street_type TEXT,
            parsed_city TEXT,
            parsed_state TEXT,
            parsed_zip TEXT,
            address_validation_flag TEXT,
            
            parcel_number TEXT,
            subdivision TEXT,
            lot TEXT,
            block TEXT,
            lot_size TEXT,
            
            owner_name TEXT,
            contractor_name TEXT,
            contractor_license TEXT,
            applicant_name TEXT,
            
            job_value REAL,
            job_value_validation_flag TEXT,
            total_fees REAL,
            fees_paid REAL,
            fees_due REAL,
            
            square_footage INTEGER,
            dwelling_units INTEGER,
            stories INTEGER,
            construction_type TEXT,
            
            inspections_count INTEGER,
            passed_inspections INTEGER,
            failed_inspections INTEGER,
            pending_inspections INTEGER,
            
            zoning TEXT,
            use_code TEXT,
            occupancy_type TEXT,
            project_name TEXT,
            
            latitude REAL,
            longitude REAL,
            
            completeness_score REAL,
            data_quality_flags TEXT,
            extraction_errors TEXT,
            
            scraped_timestamp TEXT,
            page_structure_hash TEXT,
            
            itemized_fees TEXT,
            related_permits TEXT
        )
        ''')
        
        # Prepare data
        data = (
            details.permit_number,
            details.permit_type,
            details.permit_subtype,
            details.status,
            details.description,
            details.work_description,
            
            details.applied_date,
            details.issued_date,
            details.final_date,
            details.expiration_date,
            
            details.address,
            details.parsed_address.get('street_number'),
            details.parsed_address.get('street_name'),
            details.parsed_address.get('street_type'),
            details.parsed_address.get('city'),
            details.parsed_address.get('state'),
            details.parsed_address.get('zip'),
            details.address_validation_flag,
            
            details.parcel_number,
            details.subdivision,
            details.lot,
            details.block,
            details.lot_size,
            
            details.owner_name,
            details.contractor_name,
            details.contractor_license,
            details.applicant_name,
            
            details.job_value,
            details.job_value_validation_flag,
            details.total_fees,
            details.fees_paid,
            details.fees_due,
            
            details.square_footage,
            details.dwelling_units,
            details.stories,
            details.construction_type,
            
            details.inspections_count,
            details.passed_inspections,
            details.failed_inspections,
            details.pending_inspections,
            
            details.zoning,
            details.use_code,
            details.occupancy_type,
            details.project_name,
            
            details.latitude,
            details.longitude,
            
            details.completeness_score,
            json.dumps(details.data_quality_flags),
            json.dumps(details.extraction_errors),
            
            details.scraped_timestamp,
            details.page_structure_hash,
            
            json.dumps(details.itemized_fees),
            json.dumps(details.related_permits)
        )
        
        # Insert or update
        cursor.execute('''
        INSERT OR REPLACE INTO permit_details_enhanced VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ''', data)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Saved permit {details.permit_number} to database")
    
    def emit_metric(self, name: str, value: float, unit: str = "Count", dimensions: dict = None):
        """Emit a custom CloudWatch metric via boto3"""
        try:
            cw = boto3.client("cloudwatch", region_name=AWS_REGION)
            metric_data = {
                "MetricName": name,
                "Value": value,
                "Unit": unit,
            }
            if dimensions:
                metric_data["Dimensions"] = [
                    {"Name": k, "Value": str(v)} for k, v in dimensions.items()
                ]
            cw.put_metric_data(
                Namespace="ClarkCounty/Scraper",
                MetricData=[metric_data],
            )
            logger.debug(f"Emitted CloudWatch metric: {name}={value}")
        except Exception as e:
            logger.warning(f"Failed to emit CloudWatch metric {name}: {e}")
    
    def scrape_permit(self, permit_number: str) -> Optional[PermitDetails]:
        """Scrape a permit and emit CloudWatch metrics for success/failure/errors"""
        start_time = time.time()
        error_count = 0
        try:
            logger.info(f"Scraping permit: {permit_number}")
            details = self.extract_permit_details(permit_number)
            if details and not details.extraction_errors:
                self.emit_metric("PermitScrapeSuccess", 1, dimensions={"Permit": permit_number})
            else:
                self.emit_metric("PermitScrapeFailure", 1, dimensions={"Permit": permit_number})
                error_count = len(details.extraction_errors) if details else 1
            return details
        except Exception as e:
            logger.error(f"Scrape failed: {e}")
            self.emit_metric("PermitScrapeFailure", 1, dimensions={"Permit": permit_number})
            error_count = 1
            return None
        finally:
            duration = time.time() - start_time
            self.emit_metric("PermitScrapeDuration", duration, unit="Seconds", dimensions={"Permit": permit_number})
            if error_count:
                self.emit_metric("PermitScrapeErrorCount", error_count, dimensions={"Permit": permit_number})
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")

def export_to_s3(details, bucket, prefix=""):
    s3 = boto3.client("s3")
    key = (
        f"{prefix}permit_{details.permit_number}_"
        f"{details.scraped_timestamp}.json"
    )
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(details.__dict__, default=str),
        ContentType="application/json"
    )
    logger.info(
        f"Exported permit {details.permit_number} to s3://{bucket}/{key}"
    )


def validate_details_with_ge(details):
    # Minimal example: validate job_value is not None and > 0
    df = ge.dataset.PandasDataset([details.__dict__])
    results = df.expect_column_values_to_not_be_null("job_value")
    results2 = df.expect_column_values_to_be_between(
        "job_value", 1, 1e10
    )
    if not (results["success"] and results2["success"]):
        logger.error(
            f"Great Expectations validation failed: {results}, {results2}"
        )
        return False
    logger.info("Great Expectations validation passed.")
    return True


def main():
    """Test the scraper with a sample permit"""
    scraper = EnhancedDetailScraper(headless=False)
    s3_bucket = os.getenv("S3_EXPORT_BUCKET")
    s3_prefix = os.getenv("S3_EXPORT_PREFIX", "")
    try:
        # Test with a sample permit
        test_permit = "BP21-0423"
        details = scraper.scrape_permit(test_permit)

        if details:
            print(f"\nPermit: {details.permit_number}")
            print(f"Type: {details.permit_type}")
            print(f"Status: {details.status}")
            print(f"Address: {details.address}")
            print(f"Owner: {details.owner_name}")
            print(
                f"Job Value: ${details.job_value:,.2f}"
                if details.job_value else "Job Value: N/A"
            )
            print(f"Completeness Score: {details.completeness_score}%")
            print(f"Data Quality Flags: {details.data_quality_flags}")
            print(f"Extraction Errors: {details.extraction_errors}")

            if details.parsed_address:
                print(f"\nParsed Address:")
                for key, value in details.parsed_address.items():
                    if value:
                        print(f"  {key}: {value}")

            # Data validation with Great Expectations
            if not validate_details_with_ge(details):
                print("Validation failed. Not exporting to S3.")
            elif s3_bucket:
                export_to_s3(details, s3_bucket, s3_prefix)
        else:
            print("Failed to extract permit details")
    finally:
        scraper.close()

if __name__ == "__main__":
    main()