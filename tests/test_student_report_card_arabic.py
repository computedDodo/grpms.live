from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape
import pytest


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / 'app' / 'templates'


@pytest.fixture
def render_report_card():
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(('html', 'xml')),
    )
    template = environment.get_template('student/result.html')
    environment.globals['url_for'] = lambda endpoint, **values: f'/{endpoint}'

    def render(show_arabic, arabic_names):
        subjects = [
            SimpleNamespace(subject_name='Mathematics', arabic_name=arabic_names[0]),
            SimpleNamespace(subject_name='Science', arabic_name=arabic_names[1]),
        ]
        scores = [
            SimpleNamespace(
                subject=subject,
                ca_1=8,
                ca_2=9,
                assign_1=10,
                assign_2=9,
                exam=55,
                total_score=91,
                grade='A',
                remark='Excellent',
            )
            for subject in subjects
        ]
        return template.render(
            student=SimpleNamespace(
                first_name='Demo',
                last_name='Student',
                admission_number='DEMO001',
                student_class=None,
            ),
            school=SimpleNamespace(
                name='Demo School',
                motto='',
                logo_path=None,
                stamp_path=None,
                signature_path=None,
                principal_name='Principal',
                show_arabic_column=show_arabic,
            ),
            scores=scores,
            term=SimpleNamespace(term_name='First Term'),
            session_obj=SimpleNamespace(session_name='2026/2027'),
            total_marks=182,
            total_subjects=len(scores),
            average=91,
            class_size=20,
        )

    return render


def test_arabic_column_is_rendered_and_names_match_each_subject(render_report_card):
    html = render_report_card(True, ['الرياضيات', 'العلوم'])

    assert 'المادة' in html
    assert 'dir="rtl"' in html
    assert html.index('Mathematics') < html.index('الرياضيات')
    assert html.index('الرياضيات') < html.index('Science') < html.index('العلوم')


def test_arabic_column_is_hidden_when_school_setting_is_disabled(render_report_card):
    html = render_report_card(False, ['الرياضيات', 'العلوم'])

    assert 'المادة' not in html
    assert 'الرياضيات' not in html
    assert 'Mathematics' in html
    assert 'colspan="9"' in render_report_card(False, [])


def test_missing_arabic_name_renders_empty_cell_without_breaking_row(render_report_card):
    html = render_report_card(True, [None, 'العلوم'])

    assert 'المادة' in html
    assert 'Mathematics' in html
    assert 'Science' in html
    assert 'العلوم' in html
    assert 'colspan="10"' in render_report_card(True, [])
    assert '<td class="arabic-subj" dir="rtl"></td>' in html
