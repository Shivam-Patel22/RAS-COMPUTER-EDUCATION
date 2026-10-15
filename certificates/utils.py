import re
import secrets
import threading
from datetime import datetime
from django.db import transaction, IntegrityError

_cert_gen_lock = threading.Lock()

CERTIFICATE_ID_REGEX = re.compile(r'^(RAS|CITI)-\d{4}-(0[1-9]|1[0-2])-[A-Z]{2}-[1-9]\d{5}-\d{4}$')


class SequenceExhaustedError(Exception):
    """Raised when the 4-digit sequence counter (1001-9999 / 5001-9999) reaches 9999."""
    pass


class RandomCodeExhaustedError(Exception):
    """Raised when all 900,000 unique six-digit random codes (100000-999999) are exhausted."""
    pass


def extract_recipient_initials(first_name="", last_name="", student_name=""):
    """
    Extracts two-letter uppercase recipient initials (first letter of first name + first letter of last name).
    Trims leading and trailing whitespace.
    If either first_name or last_name is missing, raises ValueError.
    Divyaraj Vihol -> DV | Rahul Patel -> RP | Aisha Shah -> AS
    """
    fn = (str(first_name) if first_name else "").strip()
    ln = (str(last_name) if last_name else "").strip()

    if (not fn or not ln) and student_name:
        parts = str(student_name).strip().split()
        if len(parts) >= 2:
            if not fn:
                fn = parts[0]
            if not ln:
                ln = parts[-1]

    if not fn:
        raise ValueError("First name is required to generate recipient initials.")
    if not ln:
        raise ValueError("Last name is required to generate recipient initials.")

    f_char = fn[0].upper()
    l_char = ln[0].upper()

    if not (f_char.isalpha() and l_char.isalpha()):
        raise ValueError(f"Initials must be alphabetic characters, got '{f_char}{l_char}'.")

    return f"{f_char}{l_char}"


def format_certificate_id(prefix, year, month, initials, random_code, sequence):
    """
    Formats the authoritative Certificate ID according to the exact standard:
    PREFIX-YYYY-MM-FF-RRRRRR-SSSS
    Example:
    RAS-2026-10-DV-482716-1001

    - PREFIX: Selected certificate class (RAS or CITI)
    - YYYY: Current four-digit year
    - MM: Current two-digit month (01-12)
    - FF: Recipient initials (two uppercase letters)
    - RRRRRR: Unique six-digit numeric code (100000-999999)
    - SSSS: Four-digit sequence per prefix (1001-9999)
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
        r_int = int(random_code)
        if not (100000 <= r_int <= 999999):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError(f"Invalid random code '{random_code}'. Must be a 6-digit number between 100000 and 999999.")

    try:
        s_int = int(sequence)
        if not (1000 <= s_int <= 9999):
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError(f"Invalid sequence number '{sequence}'. Must be a 4-digit number between 1000 and 9999.")

    formatted_id = f"{clean_prefix}-{y_int:04d}-{m_int:02d}-{clean_initials}-{r_int:06d}-{s_int:04d}"

    if not CERTIFICATE_ID_REGEX.match(formatted_id):
        raise ValueError(f"Formatted certificate ID '{formatted_id}' failed standard pattern verification.")

    return formatted_id


def get_student_initials(first_name="", last_name="", student_name=""):
    """
    Derives student initials from first_name, last_name, or student_name.
    Requirements:
    - Uppercase.
    - Ignore leading and trailing spaces.
    - If first_name and last_name are present: first letter of first_name + first letter of last_name.
    - If multiple words in student_name (when first/last not explicitly provided):
      first letter of first name + first letter of last name.
    - If last name is missing (or single-word name):
      only the first initial.
    - Fallback: 'FL' if completely blank (e.g. for placeholder display).
    """
    fn = (str(first_name) if first_name else "").strip()
    ln = (str(last_name) if last_name else "").strip()
    sn = (str(student_name) if student_name else "").strip()

    if fn and ln:
        return f"{fn[0].upper()}{ln[0].upper()}"
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


def allocate_unique_random_code(certificate_id="", max_retries=20):
    """
    Allocates a cryptographically secure, globally unique six-digit numeric code (100000-999999).
    Persists the code in CertificateRandomCodeRegistry with database-level uniqueness.
    Never releases or reuses previously allocated codes, including after deletion or cancellation.
    Safely retries on collision. If 900,000 values are exhausted, raises RandomCodeExhaustedError.
    """
    from .models import CertificateRandomCodeRegistry

    if CertificateRandomCodeRegistry.objects.count() >= 900000:
        raise RandomCodeExhaustedError("All 900,000 unique six-digit random codes have been exhausted.")

    for _ in range(max_retries):
        code_str = str(secrets.randbelow(900000) + 100000)
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


def generate_certificate_id(prefix="RAS", year=None, month=None, first_name="", last_name="", student_name="", initials=None, reserve=True, *args, **kwargs):
    """
    Authoritative Certificate ID generator following:
    PREFIX-YYYY-MM-FF-RRRRRR-SSSS
    Example:
    RAS-2026-10-DV-482716-1001

    - If reserve=True (default during actual certificate issuance):
      Atomically increments the prefix sequence and allocates a permanent random code.
    - If reserve=False (preview mode):
      Peeks at next sequence and uses a non-persisted preview code without consuming sequence or registry allocations.
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
            initials = extract_recipient_initials(first_name=first_name, last_name=last_name, student_name=student_name)
        except ValueError:
            initials = get_student_initials(first_name=first_name, last_name=last_name, student_name=student_name)
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

    if reserve:
        with _cert_gen_lock:
            seq = reserve_next_certificate_sequence(clean_prefix)
            random_code = allocate_unique_random_code()
            cert_id = format_certificate_id(clean_prefix, year, month, initials, random_code, seq)
            from .models import CertificateRandomCodeRegistry
            CertificateRandomCodeRegistry.objects.filter(code=random_code).update(certificate_id=cert_id, status='active')
            return cert_id
    else:
        seq = peek_next_certificate_sequence(clean_prefix)
        preview_code = 100000
        return format_certificate_id(clean_prefix, year, month, initials, preview_code, seq)


def preview_certificate_id(prefix="RAS", year=None, month=None, first_name="", last_name="", student_name="", initials=None):
    """
    Generates an ID preview for the frontend without consuming any sequence or random code.
    """
    return generate_certificate_id(
        prefix=prefix,
        year=year,
        month=month,
        first_name=first_name,
        last_name=last_name,
        student_name=student_name,
        initials=initials,
        reserve=False
    )



def validate_certificate_id_format(cert_id, prefix=None, expected_initials=None, allow_legacy=True):
    """
    Validates certificate ID format.
    Standard new format: PREFIX-YYYY-MM-FF-RRRRRR-SSSS (e.g. RAS-2026-10-DV-482716-1001)
    - PREFIX: must be RAS or CITI (or match selected prefix)
    - YYYY: valid 4-digit year
    - MM: valid 2-digit month (01-12)
    - FF: 2 uppercase letters matching expected recipient initials
    - RRRRRR: 6-digit unique random code (100000-999999)
    - SSSS: 4-digit sequence per prefix (1001-9999)

    If allow_legacy=True, also accepts valid legacy formats:
    - PREFIX-YYYY-FLSEQUENCE (e.g. RAS-2026-HC1001)
    - CERT-YYYY-...
    """
    if not cert_id:
        return False, "Certificate ID cannot be empty."

    cert_id = str(cert_id).strip().upper()

    # 1. Check New Standard Format: PREFIX-YYYY-MM-FF-RRRRRR-SSSS
    match_new = CERTIFICATE_ID_REGEX.match(cert_id)
    if match_new:
        cert_prefix = match_new.group(1)
        if prefix and cert_prefix != prefix.strip().upper():
            return False, f"Certificate ID must start with the selected prefix '{prefix.strip().upper()}'."

        parts = cert_id.split('-')
        # parts: [PREFIX, YYYY, MM, FF, RRRRRR, SSSS]
        extracted_initials = parts[3]
        if expected_initials and expected_initials != 'FL':
            clean_expected = re.sub(r'[^A-Z]', '', expected_initials.strip().upper())
            if clean_expected and extracted_initials != clean_expected:
                return False, f"Certificate ID initials '{extracted_initials}' do not match student initials '{clean_expected}'."
        return True, None

    # 2. Check Legacy Formats if allowed
    if allow_legacy:
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

    return False, "Certificate ID must follow the format 'PREFIX-YYYY-MM-FF-RRRRRR-SSSS' (e.g. RAS-2026-10-DV-482716-1001)."



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


def generate_ccc_certificate_pdf(cert):
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

    # 1. Top-Left Box QR Code
    qr_data = cert.certificate_id
    if hasattr(cert, 'verification_token') and cert.verification_token:
        qr_data = f"{cert.certificate_id}|{cert.verification_token}"

    try:
        qr_widget = qr.QrCodeWidget(qr_data)
        qr_bounds = qr_widget.getBounds()
        qr_w = qr_bounds[2] - qr_bounds[0]
        qr_h = qr_bounds[3] - qr_bounds[1]

        box_qr_size = 76
        d = Drawing(box_qr_size, box_qr_size, transform=[box_qr_size / qr_w, 0, 0, box_qr_size / qr_h, 0, 0])
        d.add(qr_widget)
        renderPDF.draw(d, c, 58, 680)
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

    c.save()
    buf.seek(0)
    return buf.getvalue()


def generate_certificate_pdf(cert):
    """
    Generates a high-quality PDF in memory for a given Certificate instance.
    For CCC courses, it uses the official CCC certificate template.
    For all other courses, it retains the standard C-DAC certificate layout.
    """
    if is_ccc_certificate(cert):
        return generate_ccc_certificate_pdf(cert)

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



