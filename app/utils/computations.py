"""
Grade computation and other academic utility functions.
"""


def get_class_section(class_name):
    """
    Derives the academic section from a class name string.
    Returns one of the 5 Subject.SECTIONS values.
    """
    name = class_name.lower()
    if any(k in name for k in ('nursery', 'kg', 'kindergarten', 'creche', 'pre-')):
        return 'Nursery'
    if any(k in name for k in ('primary', 'pry', 'basic')):
        return 'Primary'
    if any(k in name for k in ('jss', 'junior', 'jhs', 'j.s')):
        return 'Junior Secondary'
    if any(k in name for k in ('sss', 'senior', 'shs', 's.s', 'ss ')):
        return 'Senior Secondary'
    return 'All Sections'


def get_subjects_for_class(class_name, school_id):
    """
    Returns subjects visible to a given class:
    subjects scoped to that section + subjects marked 'All Sections'.
    Used in score entry and report card filtering.
    """
    from app.models import Subject
    from app import db
    section = get_class_section(class_name)
    return Subject.query.filter(
        Subject.school_id == school_id,
        db.or_(
            Subject.section == section,
            Subject.section == 'All Sections',
        )
    ).order_by(Subject.subject_name).all()


def compute_grade_and_remark(total_score):
    """
    Returns (grade, remark) tuple based on total score out of 100.
    """
    if total_score >= 70:
        return 'A', 'Excellent'
    elif total_score >= 60:
        return 'B', 'Very Good'
    elif total_score >= 50:
        return 'C', 'Good'
    elif total_score >= 45:
        return 'D', 'Pass'
    elif total_score >= 40:
        return 'E', 'Fair'
    else:
        return 'F', 'Fail'


def get_class_weight(class_name):
    """
    Returns a sort weight so classes display in school-level order:
    Nursery < Primary < JSS < SSS.
    """
    name = class_name.lower()
    if get_class_section(name) == 'Nursery':          return 1
    if get_class_section(name) == 'Primary':          return 2
    if get_class_section(name) == 'Junior Secondary': return 3
    if get_class_section(name) == 'Senior Secondary': return 4
    return 5


def get_ordinal(n):
    """Returns ordinal string: 1 → '1st', 2 → '2nd', etc."""
    if 11 <= (n % 100) <= 13:
        return f'{n}th'
    return f'{n}' + {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')


def rank_performances(performances):
    """
    Sorts a list of dicts by 'total_marks' descending, assigns
    'position' (int) and 'position_str' (ordinal) to each.
    Handles ties — tied students share the same position.
    """
    performances.sort(key=lambda x: x['total_marks'], reverse=True)
    for i, perf in enumerate(performances):
        if perf['num_subjects'] == 0:
            perf['position']     = None
            perf['position_str'] = 'N/A'
        elif i > 0 and perf['total_marks'] == performances[i - 1]['total_marks']:
            perf['position']     = performances[i - 1]['position']
            perf['position_str'] = performances[i - 1]['position_str']
        else:
            perf['position']     = i + 1
            perf['position_str'] = get_ordinal(i + 1)
    return performances
