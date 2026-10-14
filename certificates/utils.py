import re
import threading
from datetime import datetime

_cert_gen_lock = threading.Lock()

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


def get_next_certificate_sequence(prefix="RAS", year=None):
    """
    Returns the next sequence number (integer) for the given prefix and calendar year.
    Independent sequence counters:
    - RAS starts at 1001 for each new calendar year.
    - CITI starts at 5001 for each new calendar year.
    - The sequence continues independently for each prefix and year across all students.
    """
    from .models import Certificate

    clean_prefix = (str(prefix).strip().upper()) if prefix else "RAS"
    if clean_prefix not in ("RAS", "CITI"):
        clean_prefix = "RAS"

    if year is None:
        year = datetime.now().year

    start_seq = 1001 if clean_prefix == "RAS" else 5001
    max_seq = 0
    found = False

    prefix_filter = f"{clean_prefix}-{year}-"
    # Matches any ID starting with PREFIX-YYYY- followed by letters then digits, e.g. RAS-2026-HC1001, RAS-2026-P1002, RAS-2026-XX1001
    pattern = re.compile(rf"^{re.escape(clean_prefix)}-{year}-([A-Za-z]*)(\d+)$", re.IGNORECASE)

    # Inspect existing certificate records for this prefix and year
    for cert_id in Certificate.objects.filter(certificate_id__istartswith=prefix_filter).values_list('certificate_id', flat=True):
        match = pattern.match(cert_id)
        if match:
            found = True
            try:
                seq_val = int(match.group(2))
                if seq_val > max_seq:
                    max_seq = seq_val
            except ValueError:
                pass

    if found and max_seq >= start_seq:
        next_seq = max_seq + 1
    else:
        next_seq = start_seq

    # Ensure we never reuse an existing sequence number for this prefix and year
    pattern_seq = re.compile(rf"^{re.escape(clean_prefix)}-{year}-[A-Za-z]*{next_seq}$", re.IGNORECASE)
    while any(pattern_seq.match(cid) for cid in Certificate.objects.filter(certificate_id__istartswith=prefix_filter).values_list('certificate_id', flat=True)):
        next_seq += 1
        pattern_seq = re.compile(rf"^{re.escape(clean_prefix)}-{year}-[A-Za-z]*{next_seq}$", re.IGNORECASE)

    return next_seq


def generate_certificate_id(prefix="RAS", year=None, first_name="", last_name="", student_name="", initials=None, *args, **kwargs):
    """
    Auto-generates a unique server-side certificate ID in format:
    PREFIX-YYYY-FLSEQUENCE
    Where:
    - PREFIX = RAS or CITI, selected by the admin (default RAS).
    - YYYY = current running year dynamically obtained from server's current date.
    - FL = student initials (first letter of first name + first letter of last name, or single letter if no last name).
    - SEQUENCE = sequential number for the selected prefix (RAS starts at 1001, CITI at 5001).
    """
    from .models import Certificate

    raw_prefix = str(prefix).strip().upper() if prefix else "RAS"
    if raw_prefix in ("RAS", "CITI"):
        clean_prefix = raw_prefix
    else:
        clean_prefix = "RAS"
        if not first_name:
            first_name = prefix

    if isinstance(year, str) and not year.strip().isdigit():
        if not last_name and first_name:
            last_name = first_name
        first_name = year
        year = None
    elif isinstance(year, (int, str)) and str(year).strip().isdigit():
        year = int(str(year).strip())
    else:
        year = None

    if year is None:
        year = datetime.now().year

    if not initials:
        initials = get_student_initials(first_name=first_name, last_name=last_name, student_name=student_name)
    else:
        initials = re.sub(r'[^A-Z]', '', str(initials).strip().upper())
        if not initials:
            initials = "FL"

    with _cert_gen_lock:
        seq = get_next_certificate_sequence(clean_prefix, year)
        cert_id = f"{clean_prefix}-{year}-{initials}{seq}"

        while Certificate.objects.filter(certificate_id__iexact=cert_id).exists():
            seq += 1
            cert_id = f"{clean_prefix}-{year}-{initials}{seq}"

        return cert_id


def validate_certificate_id_format(cert_id, prefix=None, expected_initials=None):
    """
    Validates that cert_id conforms to PREFIX-YYYY-FLSEQUENCE:
    - PREFIX must be RAS or CITI
    - YYYY must be a 4-digit year
    - FL must be student initials (1-2 uppercase letters, not literal 'XX')
    - SEQUENCE is digits
    If prefix is provided, cert_id must match the provided prefix.
    If expected_initials is provided, initials must match expected_initials.
    Returns (is_valid, error_message).
    """
    if not cert_id:
        return False, "Certificate ID cannot be empty."

    cert_id = str(cert_id).strip().upper()
    parts = cert_id.split('-')
    if len(parts) != 3:
        return False, "Certificate ID must follow the format 'PREFIX-YYYY-FLSEQUENCE' (e.g. RAS-2026-HC1001)."

    cert_prefix, year_str, fl_seq = parts
    if cert_prefix not in ('RAS', 'CITI'):
        return False, "Invalid certificate prefix. Certificate ID must start with either 'RAS' or 'CITI'."

    if prefix and cert_prefix != prefix.strip().upper():
        return False, f"Certificate ID must start with the selected prefix '{prefix.strip().upper()}'."

    if not re.match(r'^\d{4}$', year_str):
        return False, "Certificate ID year must be a valid 4-digit year (e.g. 2026)."

    if fl_seq.startswith('XX'):
        return False, "Literal 'XX' is not allowed in Certificate ID. It must be replaced with the student's initials (e.g. HC1001)."

    match = re.match(r'^([A-Z]{1,2})(\d+)$', fl_seq)
    if not match:
        return False, "Certificate ID must include student initials (1-2 letters) followed by the sequence number (e.g. HC1001)."

    extracted_initials = match.group(1)
    if expected_initials and expected_initials != 'FL':
        clean_expected = re.sub(r'[^A-Z]', '', expected_initials.strip().upper())
        if clean_expected and extracted_initials != clean_expected:
            return False, f"Certificate ID initials '{extracted_initials}' do not match student initials '{clean_expected}'."

    return True, None


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



