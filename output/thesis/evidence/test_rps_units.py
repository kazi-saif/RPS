"""Isolated unit tests for RPS calculation and input validation.
No HTTP server, database connection, or academic records are used.
"""
import os, sys, unittest
from pathlib import Path
os.environ['RPS_DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['RPS_SECRET_KEY'] = 'isolated-unit-test-key-not-for-production-0000'
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'Backend'))
from app.main import calculate_grade, marks_info, MarksInput, CohortInput
from pydantic import ValidationError

class GradingUnitTests(unittest.TestCase):
    def test_all_grade_thresholds(self):
        cases = [(120,'A+',4),(112.5,'A',3.75),(105,'A-',3.5),(97.5,'B+',3.25),(90,'B',3),(82.5,'B-',2.75),(75,'C+',2.5),(67.5,'C',2.25),(60,'D',2)]
        for total, grade, point in cases:
            with self.subTest(total=total):
                self.assertEqual(calculate_grade(total), (grade,point))
    def test_just_below_pass_fails(self):
        self.assertEqual(calculate_grade(59.99), ('F',0))
    def test_zero_and_maximum(self):
        self.assertEqual(calculate_grade(0), ('F',0))
        self.assertEqual(calculate_grade(150), ('A+',4))
    def test_just_below_a_plus(self):
        self.assertEqual(calculate_grade(119.99), ('A',3.75))
    def test_missing_marks_remain_pending(self):
        self.assertEqual(marks_info(None), {'total_marks':None,'grade':None,'grade_point':None,'published':False})

class MarksValidationUnitTests(unittest.TestCase):
    def valid(self, **overrides):
        return dict(assignment_marks=10,class_test_marks=20,midterm_marks=40,final_marks=80,**overrides)
    def test_valid_full_marks(self):
        self.assertEqual(MarksInput(**self.valid()).final_marks,80)
    def test_accepts_two_decimal_places(self):
        values=self.valid(); values['final_marks']=65.25
        self.assertEqual(MarksInput(**values).final_marks,65.25)
    def test_rejects_three_decimal_places(self):
        values=self.valid(); values['final_marks']=65.251
        with self.assertRaises(ValidationError): MarksInput(**values)
    def test_component_limits(self):
        for field,maximum in [('assignment_marks',10),('class_test_marks',20),('midterm_marks',40),('final_marks',80)]:
            for bad in [-0.01,maximum+0.01]:
                with self.subTest(field=field,value=bad):
                    values=self.valid(); values[field]=bad
                    with self.assertRaises(ValidationError): MarksInput(**values)
    def test_missing_component_rejected(self):
        values=self.valid(); del values['final_marks']
        with self.assertRaises(ValidationError): MarksInput(**values)
    def test_nonfinite_values_rejected(self):
        for bad in [float('nan'),float('inf')]:
            values=self.valid(); values['final_marks']=bad
            with self.assertRaises(ValidationError): MarksInput(**values)
    def test_revision_must_be_positive(self):
        values=self.valid(); values['revision']=0
        with self.assertRaises(ValidationError): MarksInput(**values)

if __name__ == '__main__': unittest.main(verbosity=2)
