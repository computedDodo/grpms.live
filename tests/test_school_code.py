import pytest
from app import create_app, db
from app.models import School


@pytest.fixture
def app_instance():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_create_unique_code_succeeds(app_instance):
    s = School(name='Alpha', code=School.normalize_code('TST'))
    db.session.add(s)
    db.session.commit()
    assert School.query.filter_by(code='TST').first() is not None


def test_create_duplicate_code_fails(app_instance):
    s1 = School(name='One', code=School.normalize_code('DUP'))
    db.session.add(s1)
    db.session.commit()

    s2 = School(name='Two', code=School.normalize_code('dup'))
    db.session.add(s2)
    with pytest.raises(Exception):
        db.session.commit()
    db.session.rollback()


def test_case_insensitive_check(app_instance):
    s1 = School(name='One', code=School.normalize_code('AbC'))
    db.session.add(s1)
    db.session.commit()
    assert School.code_exists('abc') is True
    assert School.code_exists('ABC') is True


def test_update_to_own_code_succeeds(app_instance):
    s = School(name='X', code=School.normalize_code('OWN'))
    db.session.add(s)
    db.session.commit()
    assert not School.code_exists('OWN', exclude_school_id=s.id)


def test_update_to_other_code_fails(app_instance):
    s1 = School(name='One', code=School.normalize_code('AAA'))
    s2 = School(name='Two', code=School.normalize_code('BBB'))
    db.session.add_all([s1, s2])
    db.session.commit()
    assert School.code_exists('AAA', exclude_school_id=s2.id) is True


def test_invalid_code_rejected_by_normalize():
    assert School.normalize_code('123!!!') is None
    assert School.normalize_code('A1B2C3D4') == 'ABCD'
