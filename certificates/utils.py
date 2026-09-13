import random
import re
from datetime import datetime

def get_next_certificate_sequence():
    """
    Returns the next 2-digit sequence number formatted with leading zeros (01, 02... 99).
    Increments based on the highest existing suffix sequence number or total count.
    """
    from .models import Certificate
    max_seq = 0
    for cert in Certificate.objects.all():
        match = re.search(r'-(\d{2})$', cert.certificate_id)
        if match:
            try:
                seq_num = int(match.group(1))
                if seq_num > max_seq:
                    max_seq = seq_num
            except ValueError:
                pass

    if max_seq > 0:
        next_seq = max_seq + 1
    else:
        next_seq = Certificate.objects.count() + 1

    if next_seq > 99:
        next_seq = ((next_seq - 1) % 99) + 1

    return f"{next_seq:02d}"

def generate_certificate_id(first_name="", last_name=""):
    """
    Auto-generates a unique server-side certificate ID in format CERT-YYYY-FL-RANDOM-SEQ
    Where:
    - YYYY = current year
    - FL = first letter of First Name + first letter of Last Name (uppercase)
    - RANDOM = random 4-digit number
    - SEQ = running certificate number with leading zeros (2 digits: 01, 02... 99)
    """
    from .models import Certificate
    year = datetime.now().year

    fn_clean = first_name.strip() if first_name else ""
    ln_clean = last_name.strip() if last_name else ""

    f_char = fn_clean[0].upper() if fn_clean else "X"
    l_char = ln_clean[0].upper() if ln_clean else "X"
    fl = f"{f_char}{l_char}"

    seq_str = get_next_certificate_sequence()

    while True:
        random_num = random.randint(1000, 9999)
        cert_id = f"CERT-{year}-{fl}-{random_num}-{seq_str}"
        if not Certificate.objects.filter(certificate_id__iexact=cert_id).exists():
            return cert_id


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



