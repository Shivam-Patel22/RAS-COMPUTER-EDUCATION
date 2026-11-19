import re
import secrets
import threading
from datetime import datetime
from django.db import transaction, IntegrityError

_cert_gen_lock = threading.Lock()

CERTIFICATE_ID_REGEX = re.compile(r'^(RAS|CITI)-\d{4}-(0[1-9]|1[0-2])-[A-Z]{2}-[1-9]\d{5}$')
LEGACY_CERTIFICATE_ID_REGEX = re.compile(r'^(RAS|CITI)-\d{4}-(0[1-9]|1[0-2])-[A-Z]{2}-[1-9]\d{5}-(\d{6}|\d{4})$')

OFFICIAL_INSTITUTE_ADDRESS = "F-5, 2nd Floor, Surbhi Complex, Sector - 22, Nr. Gh-5 Circle, Gandhinagar, Gujarat - 382021"
OFFICIAL_INSTITUTE_PIN = "382021"


def generate_six_digit_suffix():
    """
    Generates a cryptographically secure 6-digit numeric suffix in the inclusive range 100000-999999.
    Uses Python's secrets module (backed by os.urandom) to guarantee unguessability and high entropy.
    """
    return secrets.randbelow(900000) + 100000


class SequenceExhaustedError(Exception):
    """Raised when the 4-digit sequence counter (1001-9999 / 5001-9999) reaches 9999."""
    pass


class RandomCodeExhaustedError(Exception):
    """Raised when all 900,000 unique six-digit random codes (100000-999999) are exhausted."""
    pass


def extract_recipient_initials(first_name="", last_name="", student_name="", middle_name=""):
    """
    Extracts two-letter uppercase recipient initials.
    - If first_name and last_name are present: first letter of first_name + first letter of last_name.
    - If last_name is omitted but middle_name is present: first letter of first_name + first letter of middle_name.
    - If student_name is provided: derived from available words.
    - Raises ValueError if first_name is missing or if neither last_name, middle_name, nor multi-word student_name is present.
    Divyaraj Vihol -> DV | Rahul Sharma -> RS | Rahul Kumar (no last) -> RK
    """
    fn = (str(first_name) if first_name else "").strip()
    mn = (str(middle_name) if middle_name else "").strip()
    ln = (str(last_name) if last_name else "").strip()

    if (not fn or (not ln and not mn)) and student_name:
        parts = str(student_name).strip().split()
        if len(parts) >= 2:
            if not fn:
                fn = parts[0]
            if not ln and not mn:
                ln = parts[-1]
        elif len(parts) == 1 and not fn:
            fn = parts[0]

    if not fn:
        raise ValueError("First name is required to generate recipient initials.")
    if not ln and not mn:
        raise ValueError("Last name is required to generate recipient initials.")

    import unicodedata
    norm_fn = unicodedata.normalize('NFKD', fn).encode('ascii', 'ignore').decode('ascii').strip()
    norm_mn = unicodedata.normalize('NFKD', mn).encode('ascii', 'ignore').decode('ascii').strip() if mn else ""
    norm_ln = unicodedata.normalize('NFKD', ln).encode('ascii', 'ignore').decode('ascii').strip() if ln else ""

    if norm_fn and norm_fn[0].isalpha():
        f_char = norm_fn[0].upper()
    else:
        f_char = 'S'

    if norm_ln and norm_ln[0].isalpha():
        l_char = norm_ln[0].upper()
    elif norm_mn and norm_mn[0].isalpha():
        l_char = norm_mn[0].upper()
    else:
        l_char = 'X'

    return f"{f_char}{l_char}"


def format_certificate_id(prefix, year, month, initials, random_code=100000, sequence=None, suffix=None, *args, **kwargs):
    """
    Formats the authoritative Certificate ID according to the standard:
    PREFIX-YYYY-MM-FL-XXXXXX-SERIAL
    Example:
    RAS-2026-10-SP-483271-1001
    CITI-2026-10-SP-728194-5001

    - PREFIX: Selected certificate class (RAS or CITI)
    - YYYY: Current four-digit year
    - MM: Current two-digit month (01-12)
    - FL: Recipient initials (two uppercase letters)
    - XXXXXX: Six-digit random numeric code (100000-999999, unique across all certificates)
    - SERIAL: Institute sequential counter (RAS: 1001, 1002...; CITI: 5001, 5002...)
    """
    clean_prefix = str(prefix).strip().upper() if prefix else "RAS"
    if clean_prefix not in ('RAS', 'CITI'):
        raise ValueError(f"Invalid certificate prefix '{clean_prefix}'. Allowed prefixes: 'RAS', 'CITI'.")

    try:
        y_int = int(year)
        if not (1000 <= y_int <= 9999):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError(f"Invalid issuance year '{year}'. Must be a 4-digit number.")

    try:
        m_int = int(month)
        if not (1 <= m_int <= 12):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError(f"Invalid issuance month '{month}'. Must be between 01 and 12.")

    clean_initials = str(initials).strip().upper() if initials else ""
    if not (len(clean_initials) == 2 and clean_initials.isalpha()):
        raise ValueError(f"Invalid recipient initials '{clean_initials}'. Must be exactly 2 letters.")

    try:
        r_int = int(random_code) if random_code is not None else 100000
        if not (100000 <= r_int <= 999999):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError(f"Invalid random code '{random_code}'. Must be a 6-digit number between 100000 and 999999.")

    formatted_id = f"{clean_prefix}-{y_int:04d}-{m_int:02d}-{clean_initials}-{r_int:06d}"

    if not CERTIFICATE_ID_REGEX.match(formatted_id):
        raise ValueError(f"Formatted certificate ID '{formatted_id}' failed standard pattern verification.")

    return formatted_id


def get_student_initials(first_name="", last_name="", student_name="", middle_name=""):
    """
    Derives student initials from first_name, last_name, middle_name, or student_name.
    Requirements:
    - Uppercase.
    - Ignore leading and trailing spaces.
    - If first_name and last_name are present: first letter of first_name + first letter of last_name.
    - If last_name is omitted but middle_name is present: first letter of first_name + first letter of middle_name.
    - If only first_name is present: first letter of first_name.
    - If multiple words in student_name (when first/last not explicitly provided):
      first letter of first name + first letter of last name.
    - Fallback: 'FL' if completely blank (e.g. for placeholder display).
    """
    fn = (str(first_name) if first_name else "").strip()
    mn = (str(middle_name) if middle_name else "").strip()
    ln = (str(last_name) if last_name else "").strip()
    sn = (str(student_name) if student_name else "").strip()

    if fn and ln:
        return f"{fn[0].upper()}{ln[0].upper()}"
    elif fn and mn:
        return f"{fn[0].upper()}{mn[0].upper()}"
    elif fn:
        return fn[0].upper()
    elif ln:
        return ln[0].upper()
    elif sn:
        words = sn.split()
        if len(words) >= 2:
            return f"{words[0][0].upper()}{words[-1][0].upper()}"
        elif len(words) == 1:
            return words[0][0].upper()

    return "FL"


def _init_sequence_if_needed(prefix):
    """
    Initializes sequence counter in database if not already present.
    - RAS begins at 1001.
    - CITI begins at 5001.
    Inspects existing certificates to prevent any overlap with pre-existing records.
    """
    from .models import Certificate, CertificateSequence

    clean_prefix = str(prefix).strip().upper() if prefix else "RAS"
    if clean_prefix not in ('RAS', 'CITI'):
        clean_prefix = "RAS"

    seq_obj = CertificateSequence.objects.filter(prefix=clean_prefix).first()
    if seq_obj:
        return seq_obj

    start_seq = 1001 if clean_prefix == "RAS" else 5001

    max_seq = 0
    pattern_new = re.compile(rf"^{re.escape(clean_prefix)}-.*-(\d{{4}})$", re.IGNORECASE)
    pattern_leg = re.compile(rf"^{re.escape(clean_prefix)}-.*[A-Za-z](\d{{4}})$", re.IGNORECASE)

    prefix_filter = f"{clean_prefix}-"
    for cert_id in Certificate.objects.filter(certificate_id__istartswith=prefix_filter).values_list('certificate_id', flat=True):
        m = pattern_new.match(cert_id) or pattern_leg.match(cert_id)
        if m:
            try:
                val = int(m.group(1))
                if val > max_seq:
                    max_seq = val
            except ValueError:
                pass

    init_val = max(start_seq, max_seq + 1 if max_seq >= start_seq else start_seq)

    seq_obj, _ = CertificateSequence.objects.get_or_create(
        prefix=clean_prefix,
        defaults={'next_sequence': init_val}
    )
    return seq_obj


def peek_next_certificate_sequence(prefix="RAS"):
    """
    Returns the next sequence number (integer) for the given prefix without incrementing it.
    Does NOT consume the sequence number. Used for form previews and placeholder displays.
    """
    clean_prefix = str(prefix).strip().upper() if prefix else "RAS"
    if clean_prefix not in ('RAS', 'CITI'):
        clean_prefix = "RAS"

    seq_obj = _init_sequence_if_needed(clean_prefix)
    val = seq_obj.next_sequence
    if val > 9999:
        raise SequenceExhaustedError(f"Sequence counter for prefix '{clean_prefix}' has reached its maximum limit of 9999.")
    return val


def reserve_next_certificate_sequence(prefix="RAS"):
    """
    Atomically allocates and increments the persistent sequence number for the given prefix.
    Guarantees concurrency safety using database-level select_for_update row locking.
    Never decrements, resets, or reuses sequence numbers upon deletion/cancellation.
    """
    clean_prefix = str(prefix).strip().upper() if prefix else "RAS"
    if clean_prefix not in ('RAS', 'CITI'):
        clean_prefix = "RAS"

    from .models import CertificateSequence

    with transaction.atomic():
        _init_sequence_if_needed(clean_prefix)
        seq_obj = CertificateSequence.objects.select_for_update().get(prefix=clean_prefix)
        allocated_seq = seq_obj.next_sequence

        if allocated_seq > 9999:
            raise SequenceExhaustedError(f"Sequence counter for prefix '{clean_prefix}' has reached its maximum limit of 9999.")

        seq_obj.next_sequence = allocated_seq + 1
        seq_obj.save(update_fields=['next_sequence', 'updated_at'])
        return allocated_seq


def get_next_certificate_sequence(prefix="RAS", year=None):
    """
    Backward-compatible sequence query: returns current next sequence without incrementing.
    """
    return peek_next_certificate_sequence(prefix=prefix)


def allocate_unique_random_code(certificate_id="", max_retries=100):
    """
    Allocates a cryptographically secure, globally unique six-digit numeric code (100000-999999).
    Persists the code in CertificateRandomCodeRegistry with database-level uniqueness.
    Never releases or reuses previously allocated codes, across both RAS and CITI.
    Safely retries on collision. If 900,000 values are exhausted, raises RandomCodeExhaustedError.
    """
    from .models import Certificate, CertificateRandomCodeRegistry

    if CertificateRandomCodeRegistry.objects.count() >= 900000:
        raise RandomCodeExhaustedError("All 900,000 unique six-digit random codes have been exhausted.")

    for _ in range(max_retries):
        code_str = str(secrets.randbelow(900000) + 100000)

        # Check against existing Certificate records (ending segment: -XXXXXX or legacy: -XXXXXX-)
        from django.db.models import Q
        if Certificate.objects.filter(
            Q(certificate_id__endswith=f"-{code_str}") | Q(certificate_id__contains=f"-{code_str}-")
        ).exists():
            continue

        try:
            with transaction.atomic():
                CertificateRandomCodeRegistry.objects.create(
                    code=code_str,
                    certificate_id=certificate_id,
                    status='allocated'
                )
            return code_str
        except IntegrityError:
            # Collision caught by database unique constraint; retry with new code
            continue

    raise RandomCodeExhaustedError("Unable to allocate a unique random code after multiple collision retries. Please try again.")


def generate_certificate_id(
    prefix="RAS",
    year=None,
    month=None,
    first_name="",
    last_name="",
    student_name="",
    middle_name="",
    initials=None,
    reserve=True,
    sequence=None,
    suffix=None,
    random_code=None,
    *args,
    **kwargs
):
    """
    Authoritative Certificate ID generator following:
    PREFIX-YYYY-MM-FL-XXXXXX-SERIAL
    Example:
    RAS-2026-10-SP-483271-1001
    CITI-2026-10-SP-728194-5001

    - Every newly issued certificate (reserve=True):
      - Allocates a unique, cryptographically secure 6-digit random code (100000-999999) unique across RAS and CITI.
      - Allocates the next sequential serial counter (RAS starts at 1001, CITI starts at 5001).
      - Checks database uniqueness and handles collisions with automated retry.
    - If reserve=False (preview mode):
      - Returns preview ID with 100000 as random code and next peeked serial without consuming sequences.
    """
    clean_prefix = str(prefix).strip().upper() if prefix else "RAS"
    if clean_prefix not in ('RAS', 'CITI'):
        clean_prefix = "RAS"

    # Year and Month at issuance time
    now = datetime.now()
    if year is None:
        year = now.year
    else:
        try:
            year = int(str(year).strip())
        except (ValueError, TypeError):
            year = now.year

    if month is None:
        month = now.month
    else:
        try:
            month = int(str(month).strip())
        except (ValueError, TypeError):
            month = now.month

    # Determine initials
    if not initials:
        try:
            initials = extract_recipient_initials(first_name=first_name, last_name=last_name, student_name=student_name, middle_name=middle_name)
        except ValueError:
            initials = get_student_initials(first_name=first_name, last_name=last_name, student_name=student_name, middle_name=middle_name)
            if len(initials) == 1:
                initials = f"{initials}X"
            elif not initials or len(initials) != 2:
                initials = "XX"
    else:
        clean_init = re.sub(r'[^A-Z]', '', str(initials).strip().upper())
        if len(clean_init) == 2:
            initials = clean_init
        elif len(clean_init) == 1:
            initials = f"{clean_init}X"
        else:
            initials = "XX"

    explicit_random_code = random_code if random_code is not None else kwargs.get('random_code')
    target_seq = sequence if sequence is not None else suffix

    if reserve:
        with _cert_gen_lock:
            from .models import Certificate, CertificateRandomCodeRegistry
            max_retries = 100
            for attempt in range(max_retries):
                if target_seq is not None:
                    curr_seq = target_seq
                else:
                    curr_seq = reserve_next_certificate_sequence(clean_prefix)

                if explicit_random_code is not None and attempt == 0:
                    code_str = str(explicit_random_code)
                    # Check if this explicit random code is available (not already in Certificate or Registry)
                    from django.db.models import Q
                    if not Certificate.objects.filter(
                        Q(certificate_id__endswith=f"-{code_str}") | Q(certificate_id__contains=f"-{code_str}-")
                    ).exists():
                        try:
                            with transaction.atomic():
                                CertificateRandomCodeRegistry.objects.create(
                                    code=code_str,
                                    certificate_id="",
                                    status='allocated'
                                )
                            curr_random_code = code_str
                        except IntegrityError:
                            curr_random_code = allocate_unique_random_code()
                    else:
                        curr_random_code = allocate_unique_random_code()
                else:
                    curr_random_code = allocate_unique_random_code()

                cert_id = format_certificate_id(
                    clean_prefix, year, month, initials,
                    random_code=curr_random_code,
                    sequence=curr_seq
                )
                if not Certificate.objects.filter(certificate_id__iexact=cert_id).exists():
                    CertificateRandomCodeRegistry.objects.filter(code=str(curr_random_code)).update(
                        certificate_id=cert_id,
                        status='active'
                    )
                    return cert_id

            raise SequenceExhaustedError("Unable to allocate a unique Certificate ID after multiple collision attempts.")
    else:
        preview_seq = target_seq if target_seq is not None else peek_next_certificate_sequence(clean_prefix)
        if explicit_random_code is not None:
            preview_random_code = explicit_random_code
        else:
            preview_random_code = secrets.randbelow(900000) + 100000
        return format_certificate_id(
            clean_prefix, year, month, initials,
            random_code=preview_random_code,
            sequence=preview_seq
        )


def preview_certificate_id(prefix="RAS", year=None, month=None, first_name="", last_name="", student_name="", middle_name="", initials=None, random_code=None):
    """
    Generates an ID preview for the frontend without consuming any sequence or random code.
    """
    return generate_certificate_id(
        prefix=prefix,
        year=year,
        month=month,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        student_name=student_name,
        initials=initials,
        random_code=random_code,
        reserve=False
    )



def validate_certificate_id_format(cert_id, prefix=None, expected_initials=None, allow_legacy=True):
    """
    Validates certificate ID format.
    Standard new format: PREFIX-YYYY-MM-FL-XXXXXX-SERIAL (e.g. RAS-2026-10-SP-483271-1001)
    - PREFIX: must be RAS or CITI (or match selected prefix)
    - YYYY: valid 4-digit year
    - MM: valid 2-digit month (01-12)
    - FL: 2 uppercase letters matching expected recipient initials
    - XXXXXX: 6-digit unique random code (100000-999999)
    - SERIAL: sequential serial number per institute (RAS: 1001-9999, CITI: 5001-9999)

    If allow_legacy=True, also accepts valid legacy formats:
    - PREFIX-YYYY-FLSEQUENCE (e.g. RAS-2026-HC1001)
    - CERT-YYYY-...
    """
    if not cert_id:
        return False, "Certificate ID cannot be empty."

    cert_id = str(cert_id).strip().upper()

    # 1. Check New Standard Format: PREFIX-YYYY-MM-FL-XXXXXX-SERIAL
    match_new = CERTIFICATE_ID_REGEX.match(cert_id)
    if match_new:
        cert_prefix = match_new.group(1)
        if prefix and cert_prefix != prefix.strip().upper():
            return False, f"Certificate ID must start with the selected prefix '{prefix.strip().upper()}'."

        parts = cert_id.split('-')
        # parts: [PREFIX, YYYY, MM, FL, XXXXXX, SERIAL]
        extracted_initials = parts[3]
        if expected_initials and expected_initials != 'FL':
            clean_expected = re.sub(r'[^A-Z]', '', expected_initials.strip().upper())
            if clean_expected and extracted_initials != clean_expected:
                return False, f"Certificate ID initials '{extracted_initials}' do not match student initials '{clean_expected}'."
        return True, None

    # 2. Check Legacy Formats if allowed
    if allow_legacy:
        match_prev = LEGACY_CERTIFICATE_ID_REGEX.match(cert_id)
        if match_prev:
            cert_prefix = match_prev.group(1)
            if prefix and cert_prefix != prefix.strip().upper():
                return False, f"Certificate ID must start with the selected prefix '{prefix.strip().upper()}'."
            parts = cert_id.split('-')
            extracted_initials = parts[3]
            if expected_initials and expected_initials != 'FL':
                clean_expected = re.sub(r'[^A-Z]', '', expected_initials.strip().upper())
                if clean_expected and extracted_initials != clean_expected:
                    return False, f"Certificate ID initials '{extracted_initials}' do not match student initials '{clean_expected}'."
            return True, None

        # Check Legacy PREFIX-YYYY-FLSEQUENCE
        parts = cert_id.split('-')
        if len(parts) == 3:
            cert_prefix, year_str, fl_seq = parts
            if cert_prefix in ('RAS', 'CITI'):
                if prefix and cert_prefix != prefix.strip().upper():
                    return False, f"Certificate ID must start with the selected prefix '{prefix.strip().upper()}'."
                if not re.match(r'^\d{4}$', year_str):
                    return False, "Certificate ID year must be a valid 4-digit year (e.g. 2026)."
                if fl_seq.startswith('XX'):
                    return False, "Literal 'XX' is not allowed in Certificate ID. It must be replaced with the student's initials."
                match_legacy = re.match(r'^([A-Z]{1,2})(\d+)$', fl_seq)
                if match_legacy:
                    extracted_initials = match_legacy.group(1)
                    if expected_initials and expected_initials != 'FL':
                        clean_expected = re.sub(r'[^A-Z]', '', expected_initials.strip().upper())
                        if clean_expected and extracted_initials != clean_expected:
                            return False, f"Certificate ID initials '{extracted_initials}' do not match student initials '{clean_expected}'."
                    return True, None
        elif len(parts) >= 3 and parts[0] == 'CERT':
            return True, None

    return False, "Certificate ID must follow the format 'PREFIX-YYYY-MM-FL-XXXXXX' (e.g. RAS-2026-10-SP-483271)."



def is_ccc_certificate(cert):
    """
    Checks whether a certificate is for the CCC (Course on Computer Concepts) program.
    """
    if hasattr(cert, 'is_ccc'):
        return bool(cert.is_ccc)
    if not cert or not getattr(cert, 'course', None):
        return False
    course_name = (cert.course.name or '').strip().lower()
    return (
        course_name == 'ccc' or
        'course on computer concepts' in course_name or
        course_name.startswith('ccc ') or
        course_name.endswith(' ccc') or
        '(ccc)' in course_name
    )


def is_ras_certificate(cert):
    """
    Returns True if the certificate belongs to the RAS institute prefix.
    """
    if not cert:
        return False
    if hasattr(cert, 'prefix') and cert.prefix:
        return cert.prefix.upper() == 'RAS'
    cert_id = getattr(cert, 'certificate_id', '') or ''
    if cert_id and '-' in cert_id:
        return cert_id.split('-')[0].upper() == 'RAS'
    return False


def is_spoken_english_certificate(cert):
    """
    Checks whether a certificate is for the Spoken English program.
    """
    if hasattr(cert, 'is_spoken_english'):
        return bool(cert.is_spoken_english)
    if not cert or not getattr(cert, 'course', None):
        return False
    course_name = (getattr(cert.course, 'name', None) or str(cert.course) or '').strip().lower()
    return (
        'spoken english' in course_name or
        course_name == 'english speaking' or
        ('english' in course_name and ('spoken' in course_name or 'speaking' in course_name))
    )


def _format_ordinal_date(d):
    """
    Formats a date object as day with ordinal suffix + abbreviated month with dot,
    e.g., 15th Jun. or 31st Aug.
    """
    if not d:
        return ""
    day = d.day
    if 11 <= (day % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
    return f"{day}{suffix} {d.strftime('%b')}."


def generate_qr_code_image(data, box_size=4, border=1):
    """
    Generates a crisp PIL Image of a QR code encoding data.
    Uses standard QR code generation with medium error correction.
    """
    import qrcode
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


def generate_qr_data_uri(data, box_size=4, border=1):
    """
    Generates a base64 PNG data URI for embedding directly into HTML templates.
    """
    import io
    import base64
    img = generate_qr_code_image(data, box_size=box_size, border=border)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    return f"data:image/png;base64,{b64}"


def get_certificate_verify_url(cert=None, request=None):
    """
    Returns the absolute URL for the Certificate Verification page or specific certificate.
    Supports optional cert instance/ID and optional HttpRequest.
    Guarantees no double slashes and respects deployment environment domain.
    """
    import os
    from django.conf import settings
    from django.urls import reverse

    cert_id = None
    if cert:
        if hasattr(cert, 'certificate_id') and cert.certificate_id:
            cert_id = str(cert.certificate_id).strip()
        elif isinstance(cert, str):
            cert_id = cert.strip()

    if cert_id:
        try:
            path = reverse('certificates:verify_direct', kwargs={'certificate_id': cert_id})
        except Exception:
            path = f"/verify-certificate/{cert_id}/"
    else:
        try:
            path = reverse('certificates:verify')
        except Exception:
            path = '/verify-certificate/'

    # 1. Configured base URL from settings / env
    base = getattr(settings, 'SITE_BASE_URL', os.environ.get('SITE_BASE_URL', '')).strip().rstrip('/')

    # 2. If request is available and (DEBUG is active or base is default localhost), use request.build_absolute_uri
    if request:
        if not base or ('localhost' in base and not getattr(settings, 'DEBUG', False)):
            return request.build_absolute_uri(path)
        if getattr(settings, 'DEBUG', False) and 'localhost' in base:
            return request.build_absolute_uri(path)

    # 3. If base is configured, use it
    if base:
        return f"{base}/{path.lstrip('/')}"

    # 4. If request is provided fallback to request absolute uri
    if request:
        return request.build_absolute_uri(path)

    # 5. Default fallback
    return f"http://localhost:8000/{path.lstrip('/')}"


def generate_ras_certificate_pdf(cert, request=None):
    """
    Generates a high-quality A4 landscape PDF in memory for an RAS institute certificate
    using the official RAS Computer Education template background.
    Dynamic fields are positioned as exact percentages of page width/height:
    - Student name: x 62%, y 39% (UPPERCASE, Bold)
    - Course name: x 64%, y 44% (UPPERCASE, Bold, in curly quotes “...”)
    - Period from: x 34%, y 50% (Ordinal day + abbreviated month, e.g. 15th Jun.)
    - Period to: x 44.5%, y 50% (Ordinal day + abbreviated month, e.g. 31st Aug.)
    - Year: x 58.5%, y 50% (4 digits, e.g. 2026)
    - Grade: x 35%, y 59.5% (in curly quotes, e.g. “A”)
    - Issue date: x 23.5%, y 70.5% (DD.MM.YYYY, e.g. 10.09.2026)
    - Authority Signatory: left empty.
    """
    import io
    import os
    from django.conf import settings
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors

    buf = io.BytesIO()
    page_w, page_h = landscape(A4)  # 841.89 x 595.27 points
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    template_candidates = [
        os.path.join(settings.BASE_DIR, 'static', 'certificates', 'ras_template.jpg'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'ras_template.jpg'),
    ]
    template_path = None
    for cand in template_candidates:
        if os.path.exists(cand):
            template_path = cand
            break

    if template_path:
        c.drawImage(template_path, 0, 0, width=page_w, height=page_h)

    # 1. Student Name (x 62%, y 39% from top)
    student_name = (cert.student_name or '').strip().upper()
    c.setFillColor(colors.HexColor('#000000'))
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(page_w * 0.62, page_h * (1 - 0.398), student_name)

    # 2. Course Name (x 64%, y 44% from top)
    course_name = (cert.course.name if cert.course else '').strip().upper()
    c.setFont('Helvetica-Bold', 15)
    c.drawCentredString(page_w * 0.64, page_h * (1 - 0.446), f'“{course_name}”')

    # 3. Period From (x 34%, y 50% from top)
    c.setFont('Helvetica', 12)
    from_str = _format_ordinal_date(cert.course_start_date)
    if from_str:
        c.drawCentredString(page_w * 0.34, page_h * (1 - 0.503), from_str)

    # 4. Period To (x 44.5%, y 50% from top)
    to_str = _format_ordinal_date(cert.course_end_date)
    if to_str:
        c.drawCentredString(page_w * 0.445, page_h * (1 - 0.503), to_str)

    # 5. Year (x 58.5%, y 50% from top)
    if cert.course_end_date:
        year_str = str(cert.course_end_date.year)
    elif cert.issue_date:
        year_str = str(cert.issue_date.year)
    else:
        year_str = ''
    if year_str:
        c.drawCentredString(page_w * 0.585, page_h * (1 - 0.503), year_str)

    # 6. Grade (x 35%, y 59.5% from top)
    if cert.grade:
        grade_str = f'“{cert.grade.strip()}”'
        c.setFont('Helvetica-Bold', 13)
        c.drawCentredString(page_w * 0.35, page_h * (1 - 0.598), grade_str)

    # 7. Issue Date (x 23.5%, y 70.5% from top)
    if cert.issue_date:
        date_str = cert.issue_date.strftime('%d.%m.%Y')
        c.setFont('Helvetica', 11)
        c.drawCentredString(page_w * 0.235, page_h * (1 - 0.713), date_str)

    # 8. Certificate Verification Line (dynamic text between Date/Signatory row and grade scale)
    verify_url = get_certificate_verify_url()
    verify_line = f"This Certificate can be verified on {verify_url}"
    c.setFillColor(colors.HexColor('#1E293B'))
    font_size = 9
    max_w = page_w * 0.85
    while c.stringWidth(verify_line, 'Helvetica', font_size) > max_w and font_size > 5:
        font_size -= 0.5
    c.setFont('Helvetica', font_size)
    c.drawCentredString(page_w * 0.50, page_h * (1 - 0.782), verify_line)

    # 9. Dynamic Scannable QR Code Overlay in Top-Left (x 38.5%, y 12%)
    qr_verify_url = get_certificate_verify_url(cert, request=request)
    try:
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        qr_img = generate_qr_code_image(qr_verify_url, box_size=4, border=1)
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format='PNG')
        qr_buf.seek(0)

        qr_size = 62
        qr_x = page_w * 0.115 - (qr_size / 2)
        qr_y = page_h * (1 - 0.12) - (qr_size / 2)

        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor('#CBD5E1'))
        c.setLineWidth(0.8)
        c.roundRect(qr_x - 3, qr_y - 10, qr_size + 6, qr_size + 13, 3, fill=True, stroke=True)
        c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size)

        c.setFont('Helvetica-Bold', 5.5)
        c.setFillColor(colors.HexColor('#475569'))
        c.drawCentredString(qr_x + (qr_size / 2), qr_y - 7, 'SCAN TO VERIFY')
    except Exception:
        pass

    # Authority Signatory: left empty per requirements

    c.save()
    buf.seek(0)
    return buf.getvalue()


def generate_ras_spoken_english_certificate_pdf(cert, request=None):
    """
    Generates a high-quality A4 landscape PDF in memory for an RAS Spoken English certificate
    using the official uploaded template background: 'RAS Spoken English copy.jpg.jpeg'.
    Dynamic fields are positioned matching the template's printed blanks:
    - Student name: x 65.25%, y 40.2% from top (UPPERCASE, Bold)
    - Course name: x 65.25%, y 44.8% from top (UPPERCASE, Bold, in quotes)
    - Period from: x 34.14%, y 50.5% from top
    - Period to: x 44.54%, y 50.5% from top
    - Year: x 58.59%, y 50.5% from top
    - Grade: x 35.05%, y 60.0% from top (in quotes)
    - Student Registration No: x 31.5% (left-aligned), y 64.0% from top (Bold)
    - Issue date: x 23.45%, y 71.3% from top
    - QR Code: x 88.5%, y 12% in top-right corner
    """
    import io
    import os
    from django.conf import settings
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors

    buf = io.BytesIO()
    page_w, page_h = landscape(A4)  # 841.89 x 595.27 points
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    template_candidates = [
        os.path.join(settings.BASE_DIR, 'static', 'certificates', 'ras_spoken_english_template.jpg'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'ras_spoken_english_template.jpg'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'RAS Spoken English copy.jpg.jpeg'),
        os.path.join(settings.BASE_DIR, 'static', 'certificates', 'RAS Spoken English copy.jpg.jpeg'),
    ]
    template_path = None
    for cand in template_candidates:
        if os.path.exists(cand):
            template_path = cand
            break

    if template_path:
        c.drawImage(template_path, 0, 0, width=page_w, height=page_h)

    # 1. Student Name (x 65.25%, y 40.2% from top)
    student_name = (cert.student_name or '').strip().upper()
    c.setFillColor(colors.HexColor('#000000'))
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(page_w * 0.6525, page_h * (1 - 0.402), student_name)

    # 2. Course Name (x 65.25%, y 44.8% from top)
    course_name = (cert.course.name if cert.course else '').strip().upper()
    c.setFont('Helvetica-Bold', 15)
    c.drawCentredString(page_w * 0.6525, page_h * (1 - 0.448), f'“{course_name}”')

    # 3. Period From (x 34.14%, y 50.5% from top)
    c.setFont('Helvetica', 12)
    from_str = _format_ordinal_date(cert.course_start_date)
    if from_str:
        c.drawCentredString(page_w * 0.3414, page_h * (1 - 0.505), from_str)

    # 4. Period To (x 44.54%, y 50.5% from top)
    to_str = _format_ordinal_date(cert.course_end_date)
    if to_str:
        c.drawCentredString(page_w * 0.4454, page_h * (1 - 0.505), to_str)

    # 5. Year (x 58.59%, y 50.5% from top)
    if cert.course_end_date:
        year_str = str(cert.course_end_date.year)
    elif cert.issue_date:
        year_str = str(cert.issue_date.year)
    else:
        year_str = ''
    if year_str:
        c.drawCentredString(page_w * 0.5859, page_h * (1 - 0.505), year_str)

    # 6. Grade (x 35.05%, y 60.0% from top)
    if cert.grade:
        grade_str = f'“{cert.grade.strip()}”'
        c.setFont('Helvetica-Bold', 13)
        c.drawCentredString(page_w * 0.3505, page_h * (1 - 0.600), grade_str)

    # 7. Student Registration No (left-aligned at x 31.5%, y 64.0% from top)
    reg_no = (cert.certificate_id or cert.registration_number or '').strip()
    if reg_no:
        c.setFont('Helvetica-Bold', 12)
        c.drawString(page_w * 0.315, page_h * (1 - 0.640), reg_no)

    # 8. Issue Date (x 23.45%, y 71.3% from top)
    if cert.issue_date:
        date_str = cert.issue_date.strftime('%d.%m.%Y')
        c.setFont('Helvetica', 11)
        c.drawCentredString(page_w * 0.2345, page_h * (1 - 0.713), date_str)

    # 9. Dynamic Scannable QR Code Overlay in Top-Left Corner (x 11.5%, y 12%)
    qr_verify_url = get_certificate_verify_url(cert, request=request)
    try:
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        qr_img = generate_qr_code_image(qr_verify_url, box_size=4, border=1)
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format='PNG')
        qr_buf.seek(0)

        qr_size = 62
        qr_x = page_w * 0.115 - (qr_size / 2)
        qr_y = page_h * (1 - 0.12) - (qr_size / 2)

        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor('#CBD5E1'))
        c.setLineWidth(0.8)
        c.roundRect(qr_x - 3, qr_y - 10, qr_size + 6, qr_size + 13, 3, fill=True, stroke=True)
        c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size)

        c.setFont('Helvetica-Bold', 5.5)
        c.setFillColor(colors.HexColor('#475569'))
        c.drawCentredString(qr_x + (qr_size / 2), qr_y - 7, 'SCAN TO VERIFY')
    except Exception:
        pass

    # Authority Signatory: left empty per requirements

    c.save()
    buf.seek(0)
    return buf.getvalue()


def generate_ccc_certificate_pdf(cert, request=None):
    """
    Generates high-resolution PDF for CCC (Course on Computer Concepts)
    using the official uploaded template image as background.
    """
    import io
    import os
    from django.conf import settings
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderPDF

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4  # 595.27 x 841.89

    # Locate template image in static/images
    template_candidates = [
        os.path.join(settings.BASE_DIR, 'static', 'images', 'CCCCerty copy.jpg.jpeg'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'ccc_certificate_template.jpg'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'CCCCerty copy.jpg'),
    ]
    template_path = None
    for cand in template_candidates:
        if os.path.exists(cand):
            template_path = cand
            break

    if template_path:
        c.drawImage(template_path, 0, 0, width=width, height=height)

    # 1. Top-Left Box QR Code (encodes public verification URL)
    qr_verify_url = get_certificate_verify_url(cert, request=request)
    try:
        from reportlab.lib.utils import ImageReader
        qr_img = generate_qr_code_image(qr_verify_url, box_size=4, border=1)
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format='PNG')
        qr_buf.seek(0)

        box_qr_size = 72
        c.drawImage(ImageReader(qr_buf), 60, 682, width=box_qr_size, height=box_qr_size)
    except Exception:
        pass

    # 2. Certificate ID and Issue Date in Top Right Area
    c.setFillColor(colors.HexColor('#1E293B'))
    c.setFont('Helvetica-Bold', 9)
    c.drawRightString(width - 55, 715, f"Cert. No: {cert.certificate_id}")
    issue_date_str = cert.issue_date.strftime('%B %d, %Y') if cert.issue_date else 'N/A'
    c.setFont('Helvetica', 8.5)
    c.setFillColor(colors.HexColor('#475569'))
    c.drawRightString(width - 55, 700, f"Date: {issue_date_str}")

    # 3. Middle Content Area (Certificate Text)
    # Lead-in
    c.setFillColor(colors.HexColor('#475569'))
    c.setFont('Helvetica-Oblique', 12.5)
    c.drawCentredString(width / 2, 475, 'This is to certify that')

    # Student Name
    student_name = (cert.student_name or 'Student').upper()
    c.setFillColor(colors.HexColor('#1E3A8A'))
    c.setFont('Helvetica-Bold', 22)
    c.drawCentredString(width / 2, 442, student_name)

    # Subtle Underline below Student Name
    name_w = c.stringWidth(student_name, 'Helvetica-Bold', 22)
    line_start_x = max(90, width / 2 - (name_w / 2) - 25)
    line_end_x = min(width - 90, width / 2 + (name_w / 2) + 25)
    c.setStrokeColor(colors.HexColor('#CBD5E1'))
    c.setLineWidth(1)
    c.line(line_start_x, 435, line_end_x, 435)

    # Course Text
    c.setFillColor(colors.HexColor('#334155'))
    c.setFont('Helvetica', 11)
    c.drawCentredString(width / 2, 402, 'has successfully completed the course requirements and practical assessment for')

    c.setFillColor(colors.HexColor('#0F172A'))
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(width / 2, 372, 'Course on Computer Concepts (CCC)')

    # Course Duration & Dates
    duration_str = cert.course.duration if (cert.course and cert.course.duration) else '3 Months (80 Hours)'
    c.setFillColor(colors.HexColor('#2563EB'))
    c.setFont('Helvetica-Bold', 10.5)
    c.drawCentredString(width / 2, 345, f'Course Duration: {duration_str}')

    if cert.course_start_date and cert.course_end_date:
        period_str = f"Course Period: {cert.course_start_date.strftime('%B %d, %Y')} – {cert.course_end_date.strftime('%B %d, %Y')}"
        c.setFillColor(colors.HexColor('#475569'))
        c.setFont('Helvetica', 9.5)
        c.drawCentredString(width / 2, 326, period_str)

    # Grade Awarded Badge/Text
    if cert.grade:
        grade_text = f"GRADE SECURED: {cert.grade.upper()}"
        c.setFillColor(colors.HexColor('#15803D'))
        c.setFont('Helvetica-Bold', 12)
        c.drawCentredString(width / 2, 288, grade_text)

    # 4. Signatory (Bottom Right Area, above 'AUTHORITY SIGNATORY' label)
    c.setFillColor(colors.HexColor('#0F172A'))
    c.setFont('Helvetica-Bold', 10.5)
    c.drawCentredString(width * 0.76, 128, 'Dr. P. K. Sharma')
    c.setFillColor(colors.HexColor('#64748B'))
    c.setFont('Helvetica', 8)
    c.drawCentredString(width * 0.76, 116, 'Director of Academic Affairs')

    # 5. Certificate Verification Line
    verify_url = get_certificate_verify_url()
    verify_line = f"This Certificate can be verified on {verify_url}"
    c.setFillColor(colors.HexColor('#475569'))
    font_size = 8
    max_w = width - 120
    while c.stringWidth(verify_line, 'Helvetica', font_size) > max_w and font_size > 5:
        font_size -= 0.5
    c.setFont('Helvetica', font_size)
    c.drawCentredString(width / 2, 48, verify_line)

    c.save()
    buf.seek(0)
    return buf.getvalue()


def get_next_citi_serial():
    """
    Returns the next sequential serial number for CITI CCC certificates.
    Finds the highest numeric serial_number among CITI certificates, defaulting to 4327 if none exist.
    """
    from .models import Certificate
    citi_certs = Certificate.objects.filter(certificate_id__startswith='CITI').exclude(serial_number='')
    max_serial = 4326  # default so next is 4327
    for cert in citi_certs:
        s = (cert.serial_number or '').strip()
        if s.isdigit():
            val = int(s)
            if val > max_serial:
                max_serial = val
    return str(max_serial + 1)


def generate_citi_ccc_certificate_pdf(cert, request=None):
    """
    Generates high-resolution A4 portrait PDF for CITI CCC Certificate
    using the official blank CITI CCC template image as background.
    Dynamic values printed on top (exact % coordinates from requirements):
    - Student photo: left 10.5%, top 8.3%, width 12.7%, height 11.8%, thin black border, object-fit cover
    - Serial number: right side, x 83% (centered), y 14.5%
    - Student name: x 51% (centered), y 51%, UPPERCASE, underlined, max width ~62%
    - Grade letter: x 58.8%, y 65.5%, bold and underlined
    - Student registration No.: x 50% (centered), y 70.3%, bold
    - Date (DD.MM.YYYY): x 40%, y 89.2%
    - Verification URL: centered in blank space between address and grade legend (y 75.5%)
    """
    import io
    import os
    from django.conf import settings
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from PIL import Image

    buf = io.BytesIO()
    width, height = A4  # 595.27 x 841.89 points
    c = canvas.Canvas(buf, pagesize=A4)

    # 1. Background Template Image
    template_candidates = [
        os.path.join(settings.BASE_DIR, 'static', 'certificates', 'citi_ccc_template.jpg'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'citi_ccc_template.jpg'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'CCCCerty copy.jpg.jpeg'),
    ]
    template_path = None
    for cand in template_candidates:
        if os.path.exists(cand):
            template_path = cand
            break

    if template_path:
        c.drawImage(template_path, 0, 0, width=width, height=height)

    # 2. Student Photo (Top-Right Corner if uploaded, symmetrical to QR Code: top 8.3%, right 10.5%)
    photo_w = width * 0.127
    photo_h = height * 0.118
    photo_x = width * (1 - 0.105) - photo_w
    photo_y = height * (1 - 0.083 - 0.118)

    if cert.student_photo:
        try:
            photo_file = cert.student_photo
            photo_file.open('rb')
            img = Image.open(photo_file)
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # Crop to aspect ratio photo_w / photo_h
            target_ratio = photo_w / photo_h
            img_ratio = img.width / img.height
            if img_ratio > target_ratio:
                crop_w = int(img.height * target_ratio)
                offset = (img.width - crop_w) // 2
                img_cropped = img.crop((offset, 0, offset + crop_w, img.height))
            else:
                crop_h = int(img.width / target_ratio)
                offset = (img.height - crop_h) // 2
                img_cropped = img.crop((0, offset, img.width, offset + crop_h))
            
            img_buf = io.BytesIO()
            img_cropped.save(img_buf, format='JPEG', quality=90)
            img_buf.seek(0)
            c.drawImage(ImageReader(img_buf), photo_x, photo_y, width=photo_w, height=photo_h)

            # Thin black border around student photo
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.8)
            c.rect(photo_x, photo_y, photo_w, photo_h, fill=False, stroke=True)
        except Exception:
            pass

    # 3. Dynamic Scannable QR Code (Top-Left Corner: top 8.3%, left 10.5%)
    qr_verify_url = get_certificate_verify_url(cert, request=request)
    qr_size = 52
    qr_x = width * 0.105
    qr_y = height * (1 - 0.083) - qr_size
    try:
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        qr_img = generate_qr_code_image(qr_verify_url, box_size=4, border=1)
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format='PNG')
        qr_buf.seek(0)

        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor('#CBD5E1'))
        c.setLineWidth(0.8)
        c.roundRect(qr_x - 3, qr_y - 9, qr_size + 6, qr_size + 12, 3, fill=True, stroke=True)
        c.drawImage(ImageReader(qr_buf), qr_x, qr_y, width=qr_size, height=qr_size)

        c.setFont('Helvetica-Bold', 5)
        c.setFillColor(colors.HexColor('#475569'))
        c.drawCentredString(qr_x + (qr_size / 2.0), qr_y - 6.5, 'SCAN TO VERIFY')
    except Exception:
        pass

    # 4. Serial Number removed from certificate display as requested

    # Center axis: x = 51% of page width
    center_x = width * 0.51

    # a. "This is to certify that Mr./ Ms./ Mrs." (y 49.1%, regular, ~13.5 pt)
    c.setFont('Helvetica', 13.5)
    c.setFillColor(colors.black)
    c.drawCentredString(center_x, height * (1 - 0.491) - (13.5 * 0.35), "This is to certify that Mr./ Ms./ Mrs.")

    # b. Student Name (y 51.8%, bold + underline, ~19 pt, UPPERCASE, max width 70%)
    student_name = (cert.student_name or '').strip().upper()
    name_font = 19.0
    max_name_w = width * 0.70
    while c.stringWidth(student_name, 'Helvetica-Bold', name_font) > max_name_w and name_font > 8.0:
        name_font -= 0.5
    name_y = height * (1 - 0.518) - (name_font * 0.35)
    c.setFont('Helvetica-Bold', name_font)
    c.setFillColor(colors.black)
    c.drawCentredString(center_x, name_y, student_name)
    nw = c.stringWidth(student_name, 'Helvetica-Bold', name_font)
    c.setLineWidth(1.2)
    c.setStrokeColor(colors.black)
    c.line(center_x - nw / 2.0, name_y - 2.5, center_x + nw / 2.0, name_y - 2.5)

    # c. "has successfully completed" (y 54.9%, regular, ~13.5 pt)
    c.setFont('Helvetica', 13.5)
    c.setFillColor(colors.black)
    c.drawCentredString(center_x, height * (1 - 0.549) - (13.5 * 0.35), "has successfully completed")

    # d. "CERTIFICATE COURSE ON COMPUTER CONCEPTS (CCC)" (y 57.6%, bold, ~13.5 pt)
    c.setFont('Helvetica-Bold', 13.5)
    c.setFillColor(colors.black)
    c.drawCentredString(center_x, height * (1 - 0.576) - (13.5 * 0.35), "CERTIFICATE COURSE ON COMPUTER CONCEPTS (CCC)")

    # e. "as per govt. GR. No. CRR-10-2007-120320-G5, Dated:13/08/08" (y 60.6%, regular, ~13.5 pt)
    c.setFont('Helvetica', 13.5)
    c.setFillColor(colors.black)
    c.drawCentredString(center_x, height * (1 - 0.606) - (13.5 * 0.35), "as per govt. GR. No. CRR-10-2007-120320-G5, Dated:13/08/08")

    # f. "(Exploring in MS Office Indic 2003 - Gujarati)" (y 63.7%, regular, ~13.5 pt)
    c.setFont('Helvetica', 13.5)
    c.setFillColor(colors.black)
    c.drawCentredString(center_x, height * (1 - 0.637) - (13.5 * 0.35), "(Exploring in MS Office Indic 2003 - Gujarati)")

    # g. "He / She has obtained  <GRADE>  Grade." (y 66.6%, regular, ~13.5 pt, grade bold + underlined inside line)
    grade_val = (cert.grade or 'A').strip().upper()
    g_y = height * (1 - 0.666) - (13.5 * 0.35)
    pre_txt = "He / She has obtained  "
    grade_txt = f"{grade_val}"
    post_txt = "  Grade."
    w_pre = c.stringWidth(pre_txt, 'Helvetica', 13.5)
    w_grade = c.stringWidth(grade_txt, 'Helvetica-Bold', 13.5)
    w_post = c.stringWidth(post_txt, 'Helvetica', 13.5)
    underline_pad = 4.0
    total_g_w = w_pre + w_grade + (underline_pad * 2) + w_post
    start_g_x = center_x - (total_g_w / 2.0)

    c.setFont('Helvetica', 13.5)
    c.setFillColor(colors.black)
    c.drawString(start_g_x, g_y, pre_txt)

    gx = start_g_x + w_pre + underline_pad
    c.setFont('Helvetica-Bold', 13.5)
    c.drawString(gx, g_y, grade_txt)
    c.setLineWidth(1.2)
    c.setStrokeColor(colors.black)
    c.line(gx - underline_pad, g_y - 2.5, gx + w_grade + underline_pad, g_y - 2.5)

    c.setFont('Helvetica', 13.5)
    c.drawString(gx + w_grade + underline_pad, g_y, post_txt)

    # h. "Student registration No.: <REG NO>" (y 71.4%, bold, ~13.5 pt)
    reg_val = cert.certificate_id or cert.registration_number
    reg_line = f"Student registration No.: {reg_val}"
    reg_font = 13.5
    while c.stringWidth(reg_line, 'Helvetica-Bold', reg_font) > width * 0.8 and reg_font > 8:
        reg_font -= 0.5
    c.setFont('Helvetica-Bold', reg_font)
    c.setFillColor(colors.black)
    c.drawCentredString(center_x, height * (1 - 0.714) - (reg_font * 0.35), reg_line)

    # i. "Exam was conducted at" (y 74.5%, bold, ~13.5 pt)
    c.setFont('Helvetica-Bold', 13.5)
    c.setFillColor(colors.black)
    c.drawCentredString(center_x, height * (1 - 0.745) - (13.5 * 0.35), "Exam was conducted at")

    # j. Official Address (y 77.4%, regular, 11.5 pt to fit full address cleanly)
    c.setFont('Helvetica', 11.5)
    c.setFillColor(colors.black)
    c.drawCentredString(center_x, height * (1 - 0.774) - (11.5 * 0.35), OFFICIAL_INSTITUTE_ADDRESS)

    # verify line (y 43.0%, ~8.5-9 pt, dark gray)
    verify_url = get_certificate_verify_url()
    verify_line = f"This Certificate can be verified on {verify_url}"
    c.setFont('Helvetica', 8.5)
    c.setFillColor(colors.HexColor('#334155'))
    c.drawCentredString(center_x, height * (1 - 0.430) - (8.5 * 0.35), verify_line)

    # Bottom-left Date / Place block (left edge x 27.4%, Date at y 90.8%, Place at y 92.9%, bold, ~14 pt)
    left_dp_x = width * 0.274
    date_str = cert.issue_date.strftime('%d.%m.%Y') if cert.issue_date else ''
    c.setFont('Helvetica-Bold', 14)
    c.setFillColor(colors.black)
    if date_str:
        c.drawString(left_dp_x, height * (1 - 0.908) - (14 * 0.35), f"Date  : {date_str}")
    c.drawString(left_dp_x, height * (1 - 0.929) - (14 * 0.35), "Place: Gandhinagar")

    c.save()
    buf.seek(0)
    return buf.getvalue()


def generate_citi_marksheet_pdf(cert):
    """
    Generates high-resolution A4 portrait Statement of Marks PDF for CITI CCC
    matching the exact template layout, typography, and styling of CCC_MarkSheet_Sample.pdf.
    """
    import io
    import os
    from django.conf import settings
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    buf = io.BytesIO()
    width, height = A4  # 595.27559 x 841.88976 points
    c = canvas.Canvas(buf, pagesize=A4)

    # 1. Fonts Registration (Calibri with fallback to Helvetica)
    f_reg = 'Helvetica'
    f_bld = 'Helvetica-Bold'
    f_itl = 'Helvetica-Oblique'
    for font_dir in [r'C:\Windows\Fonts', '/usr/share/fonts/truetype', '/usr/local/share/fonts']:
        cal_p = os.path.join(font_dir, 'calibri.ttf')
        cal_b = os.path.join(font_dir, 'calibrib.ttf')
        cal_i = os.path.join(font_dir, 'calibrii.ttf')
        if os.path.exists(cal_p) and os.path.exists(cal_b) and os.path.exists(cal_i):
            try:
                if 'Calibri' not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont('Calibri', cal_p))
                    pdfmetrics.registerFont(TTFont('Calibri-Bold', cal_b))
                    pdfmetrics.registerFont(TTFont('Calibri-Italic', cal_i))
                f_reg = 'Calibri'
                f_bld = 'Calibri-Bold'
                f_itl = 'Calibri-Italic'
                break
            except Exception:
                pass

    # 2. Background Letterhead Template
    bg_candidates = [
        os.path.join(settings.BASE_DIR, 'static', 'certificates', 'citi_marksheet_bg.jpg'),
        os.path.join(settings.BASE_DIR, 'staticfiles', 'certificates', 'citi_marksheet_bg.jpg'),
        os.path.join(settings.BASE_DIR, 'static', 'images', 'citi_marksheet_bg.jpg'),
    ]
    bg_path = None
    for cand in bg_candidates:
        if os.path.exists(cand):
            bg_path = cand
            break
    if bg_path:
        c.drawImage(bg_path, 0, 0, width=width, height=height)

    # 3. Document Title: STATEMENT OF MARKS (Underlined, Centered)
    c.setFont(f_bld, 14)
    c.setFillColor(colors.black)
    c.drawCentredString(width / 2.0, 629.9, "STATEMENT OF MARKS")
    c.setLineWidth(0.8)
    c.line(229.7, 628.6, 365.8, 628.6)

    # 4. Student & Course Information
    student_name = (cert.student_name or '').upper()
    duration_val = (cert.course_duration or '').strip() or (cert.course.duration if cert.course else '') or "3 Months"

    c.setFont(f_bld, 11)
    c.drawString(151.2, 603.5, "Student’s Name")
    c.drawString(259.2, 603.5, f":  {student_name}")

    c.drawString(151.2, 590.0, "Course Name")
    c.setFont(f_reg, 11)
    c.drawString(259.2, 590.0, ":  CERTIFICATE COURSE ON COMPUTER CONCEPTS (CCC)")

    c.setFont(f_bld, 11)
    c.drawString(151.2, 576.5, "Course Duration")
    c.setFont(f_reg, 11)
    c.drawString(259.2, 576.5, f":  {duration_val}")

    # 5. Main Examination Marks Table (Matching CCC_MarkSheet_Sample.pdf)
    col_widths = [283.6, 67.4, 67.6, 67.5, 61.1]  # Total: 547.2 pt
    row_heights = [13.9, 14.1, 147.6, 14.0]        # Total: 189.6 pt

    subject_style = ParagraphStyle(
        'ExactSubject',
        fontName=f_reg,
        fontSize=11,
        leading=20.1,
        alignment=0,
        textColor=colors.black
    )
    subj_html = (
        "Ms-Office  2003 with Indic Version ( Word, Excel, Power<br/>"
        "Point, Outlook Express  and Indic 2003(Gujarati)<br/>"
        "Computer Fundaments, Operating System, Concepts,<br/>"
        "System Utility, Networks and Internet,<br/>"
        "Installation, Trouble shooting,<br/>"
        "PDF File Concepts."
    )
    subj_para = Paragraph(subj_html, subject_style)

    num_style = ParagraphStyle(
        'NumStyle',
        fontName=f_reg,
        fontSize=11,
        leading=13,
        alignment=1,  # Centered
        textColor=colors.black
    )

    th_m = str(cert.theory_marks) if cert.theory_marks is not None else "0"
    pr_m = str(cert.practical_marks) if cert.practical_marks is not None else "0"
    tot_m = str(cert.total_marks) if cert.total_marks is not None else "0"

    table_data = [
        ["Subject", "Max. Marks", "", "Marks Obtained", ""],
        ["", "Theory", "Practical", "Theory", "Practical"],
        [subj_para, Paragraph("50", num_style), Paragraph("50", num_style), Paragraph(th_m, num_style), Paragraph(pr_m, num_style)],
        ["Total Marks", "100", "", tot_m, ""]
    ]

    t = Table(table_data, colWidths=col_widths, rowHeights=row_heights)
    t.setStyle(TableStyle([
        ('SPAN', (0, 0), (0, 1)),      # Subject across header rows 0 & 1
        ('SPAN', (1, 0), (2, 0)),      # Max. Marks across Theory/Practical
        ('SPAN', (3, 0), (4, 0)),      # Marks Obtained across Theory/Practical
        ('SPAN', (1, 3), (2, 3)),      # Total 100 across Theory/Practical
        ('SPAN', (3, 3), (4, 3)),      # Total Obtained across Theory/Practical
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),

        # Headers styling
        ('FONTNAME', (0, 0), (-1, 1), f_bld),
        ('FONTSIZE', (0, 0), (-1, 1), 11),
        ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 1), 'MIDDLE'),

        # Content Row (Row 2)
        ('VALIGN', (0, 2), (-1, 2), 'TOP'),
        ('LEFTPADDING', (0, 2), (0, 2), 5.6),
        ('TOPPADDING', (0, 2), (-1, 2), 4.5),

        # Total Row (Row 3)
        ('FONTNAME', (0, 3), (0, 3), f_bld),
        ('FONTNAME', (1, 3), (2, 3), f_bld),
        ('FONTNAME', (3, 3), (-1, 3), f_reg),
        ('FONTSIZE', (0, 3), (-1, 3), 11),
        ('ALIGN', (0, 3), (0, 3), 'LEFT'),
        ('ALIGN', (1, 3), (-1, 3), 'CENTER'),
        ('VALIGN', (0, 3), (-1, 3), 'MIDDLE'),
        ('LEFTPADDING', (0, 3), (0, 3), 5.6),
    ]))

    t_y = 841.89 - 295.0 - 189.6  # 357.29 pt
    t.wrapOn(c, 547.2, 189.6)
    t.drawOn(c, 25.0, t_y)

    # 6. Government GR Details & Registration No. (Horizontally Centered)
    reg_no = cert.certificate_id or cert.registration_number or ""
    c.setFont(f_reg, 12)
    c.drawCentredString(width / 2.0, 841.89 - 524.9, "Above Course contents are as per Govt. of Gujarat’s")
    c.drawCentredString(width / 2.0, 841.89 - 539.6, "G.R. No.: CRR-10-2007-120320-G5, Dated: 13/08/08")
    c.drawCentredString(width / 2.0, 841.89 - 554.2, f"Student’s Registration No.: {reg_no}")

    # 7. Side-by-side Section: GRADE LEGEND (Left) & Obtained Summary (Right)
    # Left: GRADE LEGEND Table
    legend_data = [
        ["GRADE LEGEND", ""],
        ["Grade", "Percentage"],
        ["S", "85% & Above"],
        ["A", "75% to 84%"],
        ["B", "65% to 74%"],
        ["C", "55% to 64%"],
        ["D", "50% to 54%"],
    ]
    t_leg = Table(legend_data, colWidths=[71.3, 71.3], rowHeights=[13.0, 13.1, 13.2, 13.1, 13.1, 13.1, 12.7])
    t_leg.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), f_reg),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 1), (0, -1), f_reg),
        ('FONTNAME', (1, 1), (1, -1), f_itl),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    t_leg.wrapOn(c, 142.6, 91.3)
    t_leg.drawOn(c, 21.0, 841.89 - 665.6)

    # Right: Obtained Percentage and Grade Table
    raw_pct = cert.percentage if cert.percentage is not None else 0
    pct_str = f"{raw_pct}%" if not str(raw_pct).endswith('%') else str(raw_pct)
    grade_val = cert.grade or "A"
    summary_data = [
        ["Obtained Percentage", f"  {pct_str}"],
        ["Obtained Grade", str(grade_val)],
    ]
    t_sum = Table(summary_data, colWidths=[140.5, 58.6], rowHeights=[13.9, 13.9])
    t_sum.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, -1), f_reg),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, -1), 5.7),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    t_sum.wrapOn(c, 199.1, 27.8)
    t_sum.drawOn(c, 306.0, 841.89 - 600.8)

    c.save()
    buf.seek(0)
    return buf.getvalue()


def generate_certificate_pdf(cert, request=None):
    """
    Generates a high-quality PDF in memory for a given Certificate instance.
    For RAS Spoken English certificates, it uses the official RAS Spoken English template.
    For RAS institute certificates, it uses the official RAS template image.
    For CITI certificates, it uses the official CITI CCC template image with photo.
    For CCC courses, it uses the official CCC certificate template.
    For all other courses, it retains the standard C-DAC certificate layout.
    """
    if is_spoken_english_certificate(cert):
        return generate_ras_spoken_english_certificate_pdf(cert, request=request)

    if is_ras_certificate(cert):
        return generate_ras_certificate_pdf(cert, request=request)

    if getattr(cert, 'prefix', '') == 'CITI':
        return generate_citi_ccc_certificate_pdf(cert, request=request)

    if is_ccc_certificate(cert):
        return generate_ccc_certificate_pdf(cert, request=request)

    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4  # 595.27 x 841.89

    # Background tint
    c.setFillColor(colors.HexColor('#FAFAFC'))
    c.rect(0, 0, width, height, fill=True, stroke=False)

    # Double Outer Border (Navy & Blue)
    c.setStrokeColor(colors.HexColor('#0F172A'))
    c.setLineWidth(5)
    c.rect(30, 30, width - 60, height - 60)

    c.setStrokeColor(colors.HexColor('#2563EB'))
    c.setLineWidth(1.5)
    c.rect(38, 38, width - 76, height - 76)

    # Corner Decorative Accents
    accent_len = 25
    c.setLineWidth(3)
    # Top-Left Accent
    c.line(30, height - 30, 30 + accent_len, height - 30)
    c.line(30, height - 30, 30, height - 30 - accent_len)
    # Top-Right Accent
    c.line(width - 30, height - 30, width - 30 - accent_len, height - 30)
    c.line(width - 30, height - 30, width - 30, height - 30 - accent_len)
    # Bottom-Left Accent
    c.line(30, 30, 30 + accent_len, 30)
    c.line(30, 30, 30, 30 + accent_len)
    # Bottom-Right Accent
    c.line(width - 30, 30, width - 30 - accent_len, 30)
    c.line(width - 30, 30, width - 30, 30 + accent_len)

    # Header Section
    c.setFillColor(colors.HexColor('#2563EB'))
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(width / 2, height - 90, 'CENTRE FOR DEVELOPMENT OF ADVANCED COMPUTING')

    c.setFillColor(colors.HexColor('#0F172A'))
    c.setFont('Helvetica-Bold', 22)
    c.drawCentredString(width / 2, height - 130, 'CERTIFICATE OF COMPLETION')

    # Divider line
    c.setStrokeColor(colors.HexColor('#2563EB'))
    c.setLineWidth(1.5)
    c.line(width / 2 - 120, height - 145, width / 2 + 120, height - 145)

    # Recipient Lead-in
    c.setFillColor(colors.HexColor('#64748B'))
    c.setFont('Helvetica-Oblique', 13)
    c.drawCentredString(width / 2, height - 190, 'This is proudly presented to')

    # Student Name
    student_name = cert.student_name or 'Student'
    c.setFillColor(colors.HexColor('#2563EB'))
    c.setFont('Helvetica-Bold', 26)
    c.drawCentredString(width / 2, height - 235, student_name)

    # Dashed Line below Student Name
    name_w = c.stringWidth(student_name, 'Helvetica-Bold', 26)
    line_start_x = max(100, width / 2 - (name_w / 2) - 30)
    line_end_x = min(width - 100, width / 2 + (name_w / 2) + 30)
    c.setStrokeColor(colors.HexColor('#CBD5E1'))
    c.setLineWidth(1)
    c.setDash(4, 3)
    c.line(line_start_x, height - 245, line_end_x, height - 245)
    c.setDash()  # Reset dash

    # Completion Body Text
    c.setFillColor(colors.HexColor('#475569'))
    c.setFont('Helvetica', 11)
    c.drawCentredString(width / 2, height - 290, 'for successfully completing the specialized training program and fulfilling all prescribed')
    c.drawCentredString(width / 2, height - 308, 'academic and practical coursework requirements for')

    # Course Name
    course_name = cert.course.name if cert.course else 'N/A'
    c.setFillColor(colors.HexColor('#0F172A'))
    c.setFont('Helvetica-Bold', 20)
    c.drawCentredString(width / 2, height - 355, course_name)

    # Duration & Dates
    duration_str = cert.course.duration if (cert.course and cert.course.duration) else ''
    if duration_str:
        c.setFillColor(colors.HexColor('#2563EB'))
        c.setFont('Helvetica-Bold', 11)
        c.drawCentredString(width / 2, height - 382, f'Course Duration: {duration_str}')

    if cert.course_start_date and cert.course_end_date:
        period_str = f"Course Period: {cert.course_start_date.strftime('%B %d, %Y')} - {cert.course_end_date.strftime('%B %d, %Y')}"
        c.setFillColor(colors.HexColor('#475569'))
        c.setFont('Helvetica', 10)
        c.drawCentredString(width / 2, height - 402, period_str)

    # Official Seal (Center Footer)
    seal_y = 165
    seal_x = width / 2
    c.setFillColor(colors.HexColor('#1E3A8A'))
    c.setStrokeColor(colors.HexColor('#D97706'))
    c.setLineWidth(3)
    c.circle(seal_x, seal_y, 35, fill=True, stroke=True)

    c.setFillColor(colors.HexColor('#F59E0B'))
    c.setFont('Helvetica-Bold', 7)
    c.drawCentredString(seal_x, seal_y + 12, 'C-DAC VERIFIED')
    c.setFont('Helvetica-Bold', 6)
    c.drawCentredString(seal_x, seal_y + 2, '★ ★ ★')
    c.setFillColor(colors.HexColor('#FEF08A'))
    c.setFont('Helvetica', 6)
    c.drawCentredString(seal_x, seal_y - 10, 'OFFICIAL SEAL')

    # Left Footer: Certificate Details & Verification
    c.setFillColor(colors.HexColor('#0F172A'))
    c.setFont('Helvetica-Bold', 9)
    c.drawString(60, 190, f'Certificate ID: {cert.certificate_id}')

    issue_date_str = cert.issue_date.strftime('%B %d, %Y') if cert.issue_date else 'N/A'
    c.setFillColor(colors.HexColor('#475569'))
    c.setFont('Helvetica', 9)
    c.drawString(60, 175, f'Issue Date: {issue_date_str}')

    if cert.grade:
        c.drawString(60, 160, f'Grade: {cert.grade}')

    c.setFillColor(colors.HexColor('#16A34A'))
    c.setFont('Helvetica-Bold', 8.5)
    c.drawString(60, 145, 'Status: Authentic & Valid')

    # Dynamic Scannable QR Code for standard layout
    qr_verify_url = get_certificate_verify_url(cert, request=request)
    try:
        from reportlab.lib.utils import ImageReader
        qr_img = generate_qr_code_image(qr_verify_url, box_size=4, border=1)
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format='PNG')
        qr_buf.seek(0)
        c.drawImage(ImageReader(qr_buf), 235, 135, width=50, height=50)
        c.setFont('Helvetica-Bold', 5)
        c.setFillColor(colors.HexColor('#475569'))
        c.drawCentredString(260, 127, 'SCAN TO VERIFY')
    except Exception:
        pass

    # Right Footer: Authorized Signatory
    c.setStrokeColor(colors.HexColor('#0F172A'))
    c.setLineWidth(1.5)
    c.line(width - 200, 175, width - 60, 175)

    c.setFillColor(colors.HexColor('#0F172A'))
    c.setFont('Helvetica-Bold', 11)
    c.drawRightString(width - 60, 160, 'Dr. P. K. Sharma')
    c.setFont('Helvetica-Bold', 9)
    c.drawRightString(width - 60, 147, 'Authorized Signatory')
    c.setFillColor(colors.HexColor('#64748B'))
    c.setFont('Helvetica', 8)
    c.drawRightString(width - 60, 135, 'Director of Academic Affairs')

    # Verification Line (centered above metadata bar)
    verify_url = get_certificate_verify_url()
    verify_line = f"This Certificate can be verified on {verify_url}"
    c.setFillColor(colors.HexColor('#475569'))
    font_size = 8.5
    max_w = width - 120
    while c.stringWidth(verify_line, 'Helvetica', font_size) > max_w and font_size > 5:
        font_size -= 0.5
    c.setFont('Helvetica', font_size)
    c.drawCentredString(width / 2, 82, verify_line)

    # Metadata Bar at Bottom
    c.setFillColor(colors.HexColor('#F8FAFC'))
    c.rect(45, 45, width - 90, 25, fill=True, stroke=False)
    c.setStrokeColor(colors.HexColor('#E2E8F0'))
    c.setLineWidth(1)
    c.rect(45, 45, width - 90, 25, fill=False, stroke=True)

    c.setFillColor(colors.HexColor('#475569'))
    c.setFont('Helvetica', 8)
    c.drawString(55, 54, f'Verification Code: {cert.verification_token or "VERIFIED"}')
    c.drawRightString(width - 55, 54, 'Official Digital Certificate - C-DAC Academic System')

    c.save()
    buf.seek(0)
    return buf.getvalue()


def build_safe_certificate_filename(student_name, course_name):
    """
    Creates a clean, safe filename from student name and course name.
    Examples:
      - Shivam Patel + Python -> Shivampatel-Python
      - Shivam Patel + Python Programming -> Shivampatel-Python-Programming
    """
    words = re.findall(r'[a-zA-Z0-9]+', student_name or '')
    clean_student = ''.join(words).capitalize() if words else 'Student'

    c_words = re.findall(r'[a-zA-Z0-9]+', course_name or '')
    clean_course = '-'.join(w.capitalize() for w in c_words) if c_words else 'Course'

    return f"{clean_student}-{clean_course}"


class FilenameDeduplicator:
    """
    Tracks duplicate filenames and appends incremental counters
    (-2, -3, etc.) to prevent overwriting files in the ZIP archive.
    """
    def __init__(self):
        self.seen_counts = {}

    def get_unique_filename(self, student_name, course_name):
        base_name = build_safe_certificate_filename(student_name, course_name)
        count = self.seen_counts.get(base_name, 0)
        self.seen_counts[base_name] = count + 1

        if count == 0:
            return f"{base_name}.pdf"
        else:
            return f"{base_name}-{count + 1}.pdf"


def parse_date_input(date_str):
    """
    Flexibly parses date input strings in common formats (YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, DD-MM-YYYY).
    Returns a datetime.date object or None.
    """
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if not date_str:
        return None

    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            pass
    return None



