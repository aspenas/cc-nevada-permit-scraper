"""Complete permit data structure with all fields and priority weighting"""

from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CompletePermitData:
    """Complete permit data structure with all fields and priority weighting"""
    permit_number: str = ""
    address: str = ""
    permit_type: str = ""
    status: str = ""
    applied_date: str = ""
    owner_name: str = ""
    job_value: str = ""
    funded_amount: str = ""
    description: str = ""
    issued_date: str = ""
    parcel_number: str = ""
    contractor_name: str = ""
    total_fees: str = ""
    square_footage: str = ""
    zoning: str = ""
    subdivision: str = ""
    lot: str = ""
    block: str = ""
    construction_type: str = ""
    dwelling_units: str = ""
    work_description: str = ""
    use_code: str = ""
    occupancy_type: str = ""
    project_name: str = ""
    contractor_license: str = ""
    contractor_phone: str = ""
    contractor_address: str = ""
    finaled_date: str = ""
    expiration_date: str = ""
    last_inspection_date: str = ""
    fees_paid: str = ""
    balance_due: str = ""
    completeness_score: float = 0.0
    scraped_date: str = field(default_factory=lambda: datetime.now().isoformat())
    extraction_notes: list[str] = field(default_factory=list)
    FIELD_WEIGHTS = {
        "permit_number": 10,
        "address": 10,
        "permit_type": 8,
        "status": 8,
        "applied_date": 7,
        "owner_name": 6,
        "job_value": 6,
        "funded_amount": 6,
        "description": 5,
        "issued_date": 5,
        "parcel_number": 5,
        "contractor_name": 3,
        "total_fees": 3,
        "square_footage": 3,
        "zoning": 3,
        "subdivision": 2,
        "lot": 2,
        "block": 2,
        "construction_type": 2,
        "dwelling_units": 2,
        "work_description": 2,
        "use_code": 2,
        "occupancy_type": 2,
        "project_name": 1,
        "contractor_license": 1,
        "contractor_phone": 1,
        "contractor_address": 1,
        "finaled_date": 1,
        "expiration_date": 1,
        "last_inspection_date": 1,
        "fees_paid": 1,
        "balance_due": 1,
    }
    def calculate_completeness_score(self) -> float:
        total_possible = sum(self.FIELD_WEIGHTS.values())
        total_achieved = 0
        for field_name, weight in self.FIELD_WEIGHTS.items():
            field_value = getattr(self, field_name, "")
            if field_value and str(field_value).strip():
                total_achieved += weight
        self.completeness_score = (
            (total_achieved / total_possible) * 100 if total_possible > 0 else 0
        )
        return self.completeness_score
    def get_extracted_field_count(self) -> int:
        count = 0
        for field_name in self.FIELD_WEIGHTS:
            field_value = getattr(self, field_name, "")
            if field_value and str(field_value).strip():
                count += 1
        return count
    def get_total_field_count(self) -> int:
        return len(self.FIELD_WEIGHTS)
    def to_dict(self) -> dict:
        result = {}
        for field_name in self.FIELD_WEIGHTS:
            result[field_name] = getattr(self, field_name, "")
        result["completeness_score"] = self.completeness_score
        result["scraped_date"] = self.scraped_date
        result["extraction_notes"] = self.extraction_notes
        return result
    def __str__(self) -> str:
        return (
            f"CompletePermitData(permit_number='{self.permit_number}', "
            f"address='{self.address}', completeness={self.completeness_score:.1f}%)"
        ) 