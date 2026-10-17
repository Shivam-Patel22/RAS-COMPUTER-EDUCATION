import html
import re

def get_clean_preview(text, max_words=35):
    """
    Extract a clean 2-3 line plain-text preview from a course description,
    skipping markdown headings, syllabus blocks, bullet items, and formatting tokens.
    """
    if not text:
        return ""

    normalized = text.replace('\r\n', '\n').strip()
    lines = normalized.split('\n')

    desc_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        # Stop if we hit syllabus, curriculum, or module outlines
        if lower.startswith(('## course syllabus', '## syllabus', '## curriculum', '### syllabus', '# syllabus')):
            break
        # Skip markdown headings
        if stripped.startswith('#'):
            continue
        # Skip bullet points in preview
        if stripped.startswith(('-', '*', '•', '+')):
            continue
        desc_lines.append(stripped)
        if len(' '.join(desc_lines).split()) >= max_words:
            break

    clean_text = ' '.join(desc_lines) if desc_lines else normalized
    # Remove markdown formatting characters (*, _, `, #)
    clean_text = re.sub(r'[*_`#]', '', clean_text)
    # Collapse multiple whitespaces
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    return clean_text


def format_markdown_to_html(text):
    """
    Safely formats markdown course descriptions into semantic, styled HTML.
    Supports headings, bold, italic, inline code, bullet lists, and paragraphs.
    Fully XSS-safe via html.escape.
    """
    if not text:
        return ""

    escaped = html.escape(text.replace('\r\n', '\n'))
    lines = escaped.split('\n')

    html_parts = []
    in_list = False
    para_lines = []

    def flush_para():
        nonlocal para_lines
        if para_lines:
            content = ' '.join(para_lines)
            html_parts.append(f'<p class="course-text-para">{content}</p>')
            para_lines = []

    def flush_list():
        nonlocal in_list
        if in_list:
            html_parts.append('</ul>')
            in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_para()
            flush_list()
            continue

        # Format inline bold, italic, code
        formatted = stripped
        formatted = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', formatted)
        formatted = re.sub(r'\*(.*?)\*', r'<em>\1</em>', formatted)
        formatted = re.sub(r'`(.*?)`', r'<code class="course-inline-code">\1</code>', formatted)

        # Headings
        if stripped.startswith('# '):
            flush_para()
            flush_list()
            h_text = formatted[2:].strip()
            html_parts.append(f'<h2 class="course-h2">{h_text}</h2>')
        elif stripped.startswith('## '):
            flush_para()
            flush_list()
            h_text = formatted[3:].strip()
            html_parts.append(f'<h3 class="course-h3">{h_text}</h3>')
        elif stripped.startswith('### '):
            flush_para()
            flush_list()
            h_text = formatted[4:].strip()
            html_parts.append(f'<h4 class="course-h4">{h_text}</h4>')
        # Lists
        elif stripped.startswith(('- ', '* ')):
            flush_para()
            if not in_list:
                html_parts.append('<ul class="course-bullet-list">')
                in_list = True
            item_text = formatted[2:].strip()
            html_parts.append(f'<li>{item_text}</li>')
        else:
            flush_list()
            para_lines.append(formatted)

    flush_para()
    flush_list()
    return '\n'.join(html_parts)


def generate_course_slug(name):
    """
    Generates a clean, readable SEO slug from a course name,
    properly mapping special technical notations like C++, C#, .NET.
    """
    if not name:
        return 'course'
    from django.utils.text import slugify
    normalized = str(name).replace('++', 'pp').replace('#', ' sharp').replace('.net', 'dotnet').replace('.NET', 'dotnet')
    slug = slugify(normalized)
    return slug or 'course'
