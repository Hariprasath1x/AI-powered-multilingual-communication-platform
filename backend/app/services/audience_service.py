"""Audience management service: CRUD, pagination, filtering, statistics, and bulk CSV/Excel import."""

import csv
import io
import logging
from typing import List, Optional, Dict, Tuple, Set, Any
from sqlalchemy import select, func, or_, desc, asc
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.models.audience import AudienceMember
from app.schemas.audience import (
    AudienceMemberCreate,
    AudienceMemberUpdate,
    AudienceMemberResponse,
    PaginatedAudienceResponse,
    AudienceStatsResponse,
    AudienceImportSummary,
    ImportRowError,
    normalize_phone_number,
)

import re

logger = logging.getLogger("masscommai.audience_service")

# 10 MB Maximum upload size limit
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Maximum rows per import to prevent resource exhaustion or decompression attacks
MAX_IMPORT_ROWS = 10_000

# Canonical header mappings for bulk import (keys normalized without whitespace, hyphens, or underscores)
HEADER_MAP: Dict[str, str] = {
    # Name
    "name": "name",
    "fullname": "name",
    "recipientname": "name",
    "citizenname": "name",
    # Email
    "email": "email",
    "emailaddress": "email",
    "mail": "email",
    # Phone
    "phone": "phone",
    "phonenumber": "phone",
    "mobile": "phone",
    "mobilenumber": "phone",
    "contact": "phone",
    "contactnumber": "phone",
    # Age
    "age": "age",
    # Gender
    "gender": "gender",
    "sex": "gender",
    # City
    "city": "city",
    "town": "city",
    "district": "city",
    # State
    "state": "state",
    "province": "state",
    # Preferred Language
    "preferredlanguage": "preferred_language",
    "language": "preferred_language",
    "lang": "preferred_language",
    # Occupation
    "occupation": "occupation",
    "job": "occupation",
    "profession": "occupation",
    # Organization / Department
    "organizationdepartment": "organization_department",
    "department": "organization_department",
    "dept": "organization_department",
    "organization": "organization_department",
    "org": "organization_department",
    # Preferred Channel
    "preferredchannel": "preferred_channel",
    "channel": "preferred_channel",
    # Consent
    "consentstatus": "consent_status",
    "consent": "consent_status",
    "optin": "consent_status",
}


def normalize_header(h: Any) -> str:
    """Normalize input table header into a standardized canonical schema key."""
    if h is None:
        return ""
    raw = str(h).strip().lower()
    cleaned = re.sub(r"[\s_-]+", "", raw)
    return HEADER_MAP.get(cleaned, raw)


def check_duplicate_contact(
    db: Session,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    exclude_id: Optional[int] = None,
) -> Optional[str]:
    """
    Check if an email or phone number is already registered to another audience member.
    Returns descriptive reason if duplicate found, or None.
    """
    if email:
        stmt = select(AudienceMember).where(
            func.lower(AudienceMember.email) == email.strip().lower()
        )
        if exclude_id is not None:
            stmt = stmt.where(AudienceMember.id != exclude_id)
        if db.execute(stmt).scalar_one_or_none():
            return f"Email address '{email.strip().lower()}' is already registered."

    if phone:
        norm_phone = normalize_phone_number(phone)
        if norm_phone:
            stmt = select(AudienceMember).where(AudienceMember.phone == norm_phone)
            if exclude_id is not None:
                stmt = stmt.where(AudienceMember.id != exclude_id)
            if db.execute(stmt).scalar_one_or_none():
                return f"Phone number '{norm_phone}' is already registered."

    return None


def get_audience_member_by_id(db: Session, member_id: int) -> AudienceMember:
    """Retrieve an audience member by ID or raise HTTP 404."""
    stmt = select(AudienceMember).where(AudienceMember.id == member_id)
    member = db.execute(stmt).scalar_one_or_none()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audience member with ID {member_id} not found.",
        )
    return member


def create_audience_member(db: Session, data: AudienceMemberCreate) -> AudienceMember:
    """Create a new audience member with duplicate detection and validation."""
    duplicate_reason = check_duplicate_contact(
        db, email=data.email, phone=data.phone
    )
    if duplicate_reason:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=duplicate_reason,
        )

    member = AudienceMember(
        name=data.name,
        email=data.email.strip().lower() if data.email else None,
        phone=normalize_phone_number(data.phone),
        age=data.age,
        gender=data.gender.strip() if data.gender else None,
        city=data.city.strip() if data.city else None,
        state=data.state.strip() if data.state else None,
        preferred_language=data.preferred_language,
        occupation=data.occupation.strip() if data.occupation else None,
        organization_department=data.organization_department.strip() if data.organization_department else None,
        preferred_channel=data.preferred_channel,
        consent_status=data.consent_status,
    )
    db.add(member)
    try:
        db.commit()
        db.refresh(member)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An audience member with this contact handle (email or phone) already exists.",
        )
    logger.info("Created audience member ID %s", member.id)
    return member


def list_audience_members(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    preferred_language: Optional[str] = None,
    preferred_channel: Optional[str] = None,
    gender: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    occupation: Optional[str] = None,
    consent_status: Optional[bool] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> PaginatedAudienceResponse:
    """List audience members with full-text search, filtering, and pagination."""
    query = select(AudienceMember)

    # 1. Search across text fields
    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                AudienceMember.name.ilike(term),
                AudienceMember.email.ilike(term),
                AudienceMember.phone.ilike(term),
                AudienceMember.city.ilike(term),
                AudienceMember.state.ilike(term),
                AudienceMember.occupation.ilike(term),
                AudienceMember.organization_department.ilike(term),
            )
        )

    # 2. Targeted attribute filters
    if preferred_language and preferred_language.strip():
        query = query.where(
            func.lower(AudienceMember.preferred_language) == preferred_language.strip().lower()
        )
    if preferred_channel and preferred_channel.strip():
        query = query.where(
            func.lower(AudienceMember.preferred_channel) == preferred_channel.strip().lower()
        )
    if gender and gender.strip():
        query = query.where(
            func.lower(AudienceMember.gender) == gender.strip().lower()
        )
    if city and city.strip():
        query = query.where(AudienceMember.city.ilike(f"%{city.strip()}%"))
    if state and state.strip():
        query = query.where(AudienceMember.state.ilike(f"%{state.strip()}%"))
    if occupation and occupation.strip():
        query = query.where(AudienceMember.occupation.ilike(f"%{occupation.strip()}%"))
    if consent_status is not None:
        if isinstance(consent_status, bool):
            query = query.where(AudienceMember.consent_status.is_(consent_status))
        elif isinstance(consent_status, str):
            cs = consent_status.strip().lower()
            if cs in ("true", "1", "opted_in", "consented"):
                query = query.where(AudienceMember.consent_status.is_(True))
            elif cs in ("false", "0", "opted_out", "unsubscribed"):
                query = query.where(AudienceMember.consent_status.is_(False))
            elif cs in ("none", "null", "unconfirmed", "unknown"):
                query = query.where(AudienceMember.consent_status.is_(None))

    # 3. Total count calculation
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar_one()

    # 4. Sorting
    sort_col = getattr(AudienceMember, sort_by, AudienceMember.created_at)
    order_func = desc if sort_order.lower() == "desc" else asc
    query = query.order_by(order_func(sort_col))

    # 5. Pagination offset & limit
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    items = list(db.execute(query).scalars().all())

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedAudienceResponse(
        items=[AudienceMemberResponse.model_validate(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def update_audience_member(
    db: Session,
    member_id: int,
    data: AudienceMemberUpdate,
) -> AudienceMember:
    """Update audience member fields with integrity validation and conflict checking."""
    member = get_audience_member_by_id(db, member_id)

    # Candidate values after update
    candidate_email = data.email.strip().lower() if data.email else (member.email if data.email is None else None)
    candidate_phone = normalize_phone_number(data.phone) if data.phone is not None else member.phone
    candidate_channel = data.preferred_channel if data.preferred_channel is not None else member.preferred_channel

    # Enforce contact handle requirement
    if not candidate_email and not candidate_phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Audience member must retain at least an email address or a phone number.",
        )

    # Channel requirement check
    ch_norm = candidate_channel.lower() if candidate_channel else "email"
    if ch_norm == "email" and not candidate_email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email address is required when preferred channel is 'Email'.",
        )
    if ch_norm in ("sms", "whatsapp") and not candidate_phone:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Phone number is required when preferred channel is '{candidate_channel}'.",
        )

    # Check for duplicate collisions against other members
    duplicate_reason = check_duplicate_contact(
        db, email=data.email, phone=data.phone, exclude_id=member_id
    )
    if duplicate_reason:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=duplicate_reason,
        )

    update_dict = data.model_dump(exclude_unset=True)
    for field_name, value in update_dict.items():
        if field_name == "phone" and value is not None:
            value = normalize_phone_number(value)
        setattr(member, field_name, value)

    try:
        db.commit()
        db.refresh(member)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An audience member with this contact handle (email or phone) already exists.",
        )
    logger.info("Updated audience member ID %s", member.id)
    return member


def delete_audience_member(db: Session, member_id: int) -> None:
    """Delete an audience member by ID."""
    member = get_audience_member_by_id(db, member_id)
    db.delete(member)
    db.commit()
    logger.info("Deleted audience member ID %s", member_id)


def get_audience_stats(db: Session) -> AudienceStatsResponse:
    """Compute summary metrics and distributions for the audience database."""
    total = db.execute(select(func.count(AudienceMember.id))).scalar_one() or 0
    consented_count = db.execute(
        select(func.count(AudienceMember.id)).where(AudienceMember.consent_status.is_(True))
    ).scalar_one() or 0
    opt_out_count = db.execute(
        select(func.count(AudienceMember.id)).where(AudienceMember.consent_status.is_(False))
    ).scalar_one() or 0
    unspecified_count = db.execute(
        select(func.count(AudienceMember.id)).where(AudienceMember.consent_status.is_(None))
    ).scalar_one() or 0

    # Language distribution
    lang_rows = db.execute(
        select(AudienceMember.preferred_language, func.count(AudienceMember.id))
        .group_by(AudienceMember.preferred_language)
    ).all()
    lang_dist = {str(row[0]): int(row[1]) for row in lang_rows if row[0]}

    # Channel distribution
    channel_rows = db.execute(
        select(AudienceMember.preferred_channel, func.count(AudienceMember.id))
        .group_by(AudienceMember.preferred_channel)
    ).all()
    channel_dist = {str(row[0]): int(row[1]) for row in channel_rows if row[0]}

    # Gender distribution
    gender_rows = db.execute(
        select(AudienceMember.gender, func.count(AudienceMember.id))
        .group_by(AudienceMember.gender)
    ).all()
    gender_dist = {str(row[0] or "Unspecified"): int(row[1]) for row in gender_rows}

    return AudienceStatsResponse(
        total_members=total,
        consented_count=consented_count,
        opt_out_count=opt_out_count,
        unspecified_consent_count=unspecified_count,
        active_consent_count=consented_count,
        language_distribution=lang_dist,
        channel_distribution=channel_dist,
        gender_distribution=gender_dist,
    )


# ---------------------------------------------------------------------------
# Bulk Import Implementation (CSV & Excel)
# ---------------------------------------------------------------------------

def _parse_csv_file(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse CSV content with multiple encoding attempts and DictReader."""
    content_str: Optional[str] = None
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            content_str = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if content_str is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decode CSV file. Ensure it is encoded in valid UTF-8 or Latin-1.",
        )

    f = io.StringIO(content_str)
    reader = csv.reader(f)
    try:
        raw_headers = next(reader)
    except StopIteration:
        return []

    # Map raw headers to canonical field names
    canonical_headers = [normalize_header(h) for h in raw_headers]

    rows: List[Dict[str, Any]] = []
    for raw_row in reader:
        # Ignore completely empty rows
        if not any(cell.strip() for cell in raw_row):
            continue
        row_dict: Dict[str, Any] = {}
        for idx, val in enumerate(raw_row):
            if idx < len(canonical_headers):
                header = canonical_headers[idx]
                row_dict[header] = val.strip()
        rows.append(row_dict)
        if len(rows) > MAX_IMPORT_ROWS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"CSV file exceeds maximum allowed limit of {MAX_IMPORT_ROWS} rows per upload. Please split your file into smaller batches.",
            )

    return rows


def _parse_excel_file(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse Excel (.xlsx) content via openpyxl in read-only mode with safety limits."""
    import openpyxl

    try:
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to parse Excel file. The file appears to be corrupted, encrypted, or invalid.",
        )

    sheet = wb.active
    if not sheet:
        wb.close()
        return []

    rows_iter = sheet.iter_rows(values_only=True)
    try:
        raw_headers = next(rows_iter)
    except StopIteration:
        wb.close()
        return []

    canonical_headers = [normalize_header(h) for h in raw_headers]

    rows: List[Dict[str, Any]] = []
    for raw_row in rows_iter:
        if not any(cell is not None and str(cell).strip() for cell in raw_row):
            continue
        row_dict: Dict[str, Any] = {}
        for idx, val in enumerate(raw_row):
            if idx < len(canonical_headers) and canonical_headers[idx]:
                header = canonical_headers[idx]
                row_dict[header] = str(val).strip() if val is not None else ""
        rows.append(row_dict)
        if len(rows) > MAX_IMPORT_ROWS:
            wb.close()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Spreadsheet exceeds maximum allowed limit of {MAX_IMPORT_ROWS} rows per upload. Please split your file into smaller batches.",
            )

    wb.close()
    return rows


def import_audience_file(
    db: Session,
    file_bytes: bytes,
    filename: str,
) -> AudienceImportSummary:
    """
    Process bulk audience import from CSV or Excel file.
    Validates rows independently, catches duplicates in the batch and database,
    and returns a full reconciliation summary.
    """
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum allowed upload size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    fn_lower = filename.lower()
    if fn_lower.endswith(".csv"):
        parsed_rows = _parse_csv_file(file_bytes)
    elif fn_lower.endswith(".xlsx"):
        parsed_rows = _parse_excel_file(file_bytes)
    elif fn_lower.endswith(".xls"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Legacy Excel format (.xls) is not supported. Please convert your file to modern Excel (.xlsx) or CSV (.csv).",
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a .csv or .xlsx file.",
        )

    total_rows = len(parsed_rows)
    successful_imports = 0
    duplicate_count = 0
    rejected_count = 0
    unspecified_consent_count = 0
    errors: List[ImportRowError] = []

    # Pre-fetch existing emails and phones from DB to optimize duplicate lookups
    existing_emails_raw = db.execute(
        select(func.lower(AudienceMember.email)).where(AudienceMember.email.is_not(None))
    ).scalars().all()
    existing_emails: Set[str] = {e for e in existing_emails_raw if e}

    existing_phones_raw = db.execute(
        select(AudienceMember.phone).where(AudienceMember.phone.is_not(None))
    ).scalars().all()
    existing_phones: Set[str] = {p for p in existing_phones_raw if p}

    # Tracking sets to detect intra-file duplicate entries
    batch_emails: Set[str] = set()
    batch_phones: Set[str] = set()

    for idx, row in enumerate(parsed_rows, start=2):  # row 1 is header
        name = row.get("name", "").strip()
        email_raw = row.get("email", "").strip() or None
        phone_raw = row.get("phone", "").strip() or None
        age_raw = row.get("age", "").strip() or None
        gender_raw = row.get("gender", "").strip() or None
        city_raw = row.get("city", "").strip() or None
        state_raw = row.get("state", "").strip() or None
        lang_raw = row.get("preferred_language", "").strip() or "en"
        occupation_raw = row.get("occupation", "").strip() or None
        dept_raw = row.get("organization_department", "").strip() or None
        channel_raw = row.get("preferred_channel", "").strip() or "Email"
        consent_raw = row.get("consent_status", "").strip().lower()

        # 1. Parse consent boolean (Never convert missing/omitted consent to explicit True!)
        consent_status: Optional[bool] = None
        if consent_raw in ("true", "1", "yes", "y", "opt_in", "consented"):
            consent_status = True
        elif consent_raw in ("false", "0", "no", "n", "opt_out", "unsubscribed"):
            consent_status = False
        elif consent_raw == "":
            # Missing or blank consent: stored as None (unconfirmed)
            consent_status = None
            unspecified_consent_count += 1
        else:
            # Invalid or ambiguous consent value (e.g. "maybe", "not sure", "pending")
            rejected_count += 1
            errors.append(
                ImportRowError(
                    row_number=idx,
                    name=name,
                    email=email_raw,
                    phone=phone_raw,
                    reason=f"Invalid consent value '{consent_raw}'. Must be affirmative (yes/true), opt-out (no/false), or blank for unconfirmed.",
                    error_type="validation_error",
                )
            )
            continue

        # 2. Parse age integer
        age: Optional[int] = None
        if age_raw:
            try:
                # Handle possible float string from Excel e.g. "25.0"
                age_val = int(float(age_raw))
                if 1 <= age_val <= 120:
                    age = age_val
                else:
                    rejected_count += 1
                    errors.append(
                        ImportRowError(
                            row_number=idx,
                            name=name,
                            email=email_raw,
                            phone=phone_raw,
                            reason=f"Age '{age_raw}' is out of acceptable bounds (1-120).",
                            error_type="validation_error",
                        )
                    )
                    continue
            except (ValueError, TypeError):
                rejected_count += 1
                errors.append(
                    ImportRowError(
                        row_number=idx,
                        name=name,
                        email=email_raw,
                        phone=phone_raw,
                        reason=f"Invalid age numeric value '{age_raw}'.",
                        error_type="validation_error",
                    )
                )
                continue

        # 3. Validate row via Pydantic AudienceMemberCreate
        try:
            candidate = AudienceMemberCreate(
                name=name,
                email=email_raw,
                phone=phone_raw,
                age=age,
                gender=gender_raw,
                city=city_raw,
                state=state_raw,
                preferred_language=lang_raw,
                occupation=occupation_raw,
                organization_department=dept_raw,
                preferred_channel=channel_raw,
                consent_status=consent_status,
            )
        except (ValidationError, ValueError) as val_err:
            rejected_count += 1
            # Extract readable error message
            msg = str(val_err)
            if hasattr(val_err, "errors"):
                err_details = val_err.errors()
                if err_details:
                    msg = err_details[0].get("msg", str(val_err))
            errors.append(
                ImportRowError(
                    row_number=idx,
                    name=name,
                    email=email_raw,
                    phone=phone_raw,
                    reason=msg,
                    error_type="validation_error",
                )
            )
            continue

        cand_email = candidate.email.lower() if candidate.email else None
        cand_phone = candidate.phone

        # 4. Check Duplicate in existing database
        is_dup = False
        if cand_email and cand_email in existing_emails:
            duplicate_count += 1
            errors.append(
                ImportRowError(
                    row_number=idx,
                    name=name,
                    email=cand_email,
                    phone=cand_phone,
                    reason=f"Email '{cand_email}' is already registered in the database.",
                    error_type="duplicate",
                )
            )
            is_dup = True
        elif cand_phone and cand_phone in existing_phones:
            duplicate_count += 1
            errors.append(
                ImportRowError(
                    row_number=idx,
                    name=name,
                    email=cand_email,
                    phone=cand_phone,
                    reason=f"Phone '{cand_phone}' is already registered in the database.",
                    error_type="duplicate",
                )
            )
            is_dup = True

        # 5. Check Duplicate within current file batch
        elif cand_email and cand_email in batch_emails:
            duplicate_count += 1
            errors.append(
                ImportRowError(
                    row_number=idx,
                    name=name,
                    email=cand_email,
                    phone=cand_phone,
                    reason=f"Duplicate email '{cand_email}' encountered multiple times in the upload file.",
                    error_type="duplicate",
                )
            )
            is_dup = True
        elif cand_phone and cand_phone in batch_phones:
            duplicate_count += 1
            errors.append(
                ImportRowError(
                    row_number=idx,
                    name=name,
                    email=cand_email,
                    phone=cand_phone,
                    reason=f"Duplicate phone '{cand_phone}' encountered multiple times in the upload file.",
                    error_type="duplicate",
                )
            )
            is_dup = True

        if is_dup:
            continue

        # 6. Row is valid and non-duplicate: instantiate member
        member = AudienceMember(
            name=candidate.name,
            email=cand_email,
            phone=cand_phone,
            age=candidate.age,
            gender=candidate.gender,
            city=candidate.city,
            state=candidate.state,
            preferred_language=candidate.preferred_language,
            occupation=candidate.occupation,
            organization_department=candidate.organization_department,
            preferred_channel=candidate.preferred_channel,
            consent_status=candidate.consent_status,
        )
        db.add(member)

        # Update batch tracker and local mirror sets
        if cand_email:
            batch_emails.add(cand_email)
            existing_emails.add(cand_email)
        if cand_phone:
            batch_phones.add(cand_phone)
            existing_phones.add(cand_phone)

        successful_imports += 1

    # Commit all valid rows in one transactional block
    try:
        db.commit()
    except IntegrityError as ie:
        db.rollback()
        logger.warning("Bulk import integrity collision during commit: %s", ie)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A concurrent duplicate contact collision occurred during bulk import. No records were imported.",
        )
    except Exception as exc:
        db.rollback()
        logger.exception("Bulk import transaction failed during commit.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database transaction failed during bulk audience import. All rows rolled back.",
        )

    logger.info(
        "Import finished: %s total, %s successful, %s duplicates, %s rejected.",
        total_rows,
        successful_imports,
        duplicate_count,
        rejected_count,
    )

    return AudienceImportSummary(
        total_rows=total_rows,
        successful_imports=successful_imports,
        duplicate_count=duplicate_count,
        rejected_count=rejected_count,
        unspecified_consent_count=unspecified_consent_count,
        errors=errors,
    )
