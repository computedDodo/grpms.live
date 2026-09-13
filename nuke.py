from app import create_app, db
from app.models import Student, User

app = create_app()

def nuke_duplicate_students():
    with app.app_context():
        # Fetch all students ordered by ID so we keep the older, original ones
        students = Student.query.order_by(Student.id.asc()).all()
        
        seen_signatures = set()
        deleted_count = 0
        
        for student in students:
            # Create a unique fingerprint for each student based on their name and class
            signature = (
                student.first_name.strip().lower(), 
                student.last_name.strip().lower(), 
                student.current_class_id,
                student.school_id
            )
            
            if signature in seen_signatures:
                # We found a clone! Grab their login account too.
                user_account = User.query.get(student.user_id)
                
                # Permanently delete the student record
                db.session.delete(student)
                
                # Permanently delete the associated login account
                if user_account:
                    db.session.delete(user_account)
                    
                deleted_count += 1
            else:
                # First time seeing this student, keep them safe
                seen_signatures.add(signature)
                
        # Commit the purge to the database
        db.session.commit()
        print(f"🧹 Clean Slate Protocol Executed: Permanently deleted {deleted_count} duplicate students and their user accounts!")

if __name__ == '__main__':
    nuke_duplicate_students()
