import json
from pathlib import Path

from student_validator import StudentValidator

STUDENT_JSON = Path(__file__).resolve().parent / "student.json"

def test_student_validation():
    with open(STUDENT_JSON) as json_file:
        student_data = json.load(json_file)

    student= validate_student = StudentValidator(**student_data)

    #Verificarea conditiilor si daca acestea sunt cele asteptate

    assert student.nume == "Ana Popescu"
    assert student.varsta == 20
    assert student.email == "ana.popescu@example.com"

    print(student) #afisare output la rulare