from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from database import SessionLocal, engine  # Импорт из database.py
from models import Base, Employee, ExtraPayment  # Импорт моделей из models.py
from fastapi.templating import Jinja2Templates
import pandas as pd

# Создаем таблицы в БД (если они еще не созданы)
Base.metadata.create_all(bind=engine)

app = FastAPI(docs_url="/docs")

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# Функция для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Загрузка сотрудников из Excel
@app.post("/upload/employees")
async def upload_employees(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        df = pd.read_excel(file.file)
        required_columns = {"Сотрудник", "День рождения", "Подразделение", "Должность"}
        if not required_columns.issubset(set(df.columns)):
            missing = required_columns - set(df.columns)
            raise HTTPException(status_code=400, detail=f"Отсутствуют колонки: {missing}")

        for _, row in df.iterrows():
            name = row["Сотрудник"].strip()
            birthdate = pd.to_datetime(row["День рождения"], errors="coerce").date()
            department = row["Подразделение"].strip()
            position = row["Должность"].strip()

            # Если сотрудник уже есть в БД, пропускаем
            existing_employee = db.query(Employee).filter(Employee.name == name).first()
            if existing_employee:
                print(f"⚠ Сотрудник '{name}' уже существует. Пропускаем.")
                continue

            employee = Employee(
                name=name,
                birthdate=birthdate,
                department=department,
                position=position
            )
            db.add(employee)

        db.commit()
        print("✅ Все сотрудники успешно загружены в БД!")
        return {"message": "Сотрудники успешно загружены"}
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка при загрузке сотрудников: {e}")
        raise HTTPException(status_code=400, detail=str(e))

# Загрузка выплат из Excel
@app.post("/upload/payments")
async def upload_payments(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        df = pd.read_excel(file.file, header=0)
        expected_columns = {"Дата", "Номер", "Тип документа", "Сотрудник", "Комментарий", "Ответственный", "Сумма"}
        if not expected_columns.issubset(set(df.columns)):
            missing = expected_columns - set(df.columns)
            raise HTTPException(status_code=400, detail=f"Файл не содержит нужные колонки: {missing}")

        for _, row in df.iterrows():
            employee_name = str(row["Сотрудник"]).strip()
            amount = float(row["Сумма"])
            # Поиск сотрудника без учета регистра
            employee = db.query(Employee).filter(Employee.name.ilike(f"%{employee_name}%")).first()
            if not employee:
                print(f"⚠ Сотрудник '{employee_name}' не найден, пропускаем запись.")
                continue

            payment = ExtraPayment(
                employee_id=employee.id,
                amount=amount,
                date=pd.to_datetime(row["Дата"]).date(),
                description=row["Тип документа"]
            )
            db.add(payment)

        db.commit()
        print("✅ Все выплаты успешно загружены в БД!")
        return {"message": "Выплаты успешно загружены"}
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка при загрузке выплат: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/employee/{employee_id}/payments", response_class=HTMLResponse)
def employee_payments(request: Request, employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    
    payments = db.query(ExtraPayment).filter(ExtraPayment.employee_id == employee_id).all()
    return templates.TemplateResponse("employee_payments.html", {"request": request, "employee": employee, "payments": payments})
    payments = db.query(ExtraPayment).filter(ExtraPayment.employee_id == employee_id).all()
    
    return templates.TemplateResponse(
        "employee_payments.html",
        {"request": request, "employee": employee, "payments": payments}
    )
@app.get("/employees", response_class=HTMLResponse)
def employees_page(request: Request, db: Session = Depends(get_db), search: str = None):
    query = db.query(Employee)
    
    if search:
        query = query.filter(Employee.name.ilike(f"%{search}%"))  # Поиск без учета регистра

    employees = query.all()
    return templates.TemplateResponse("employees.html", {"request": request, "employees": employees, "search": search})
@app.get("/search", response_class=HTMLResponse)
def search_employee(request: Request, q: str = "", db: Session = Depends(get_db)):
    employees = db.query(Employee).filter(Employee.name.ilike(f"%{q}%")).all()
    return templates.TemplateResponse("search_results.html", {"request": request, "employees": employees, "query": q})

    return templates.TemplateResponse("employees.html", {"request": request, "employees": employees})
@app.get("/employees/edit/{employee_id}", response_class=HTMLResponse)
def edit_employee_page(request: Request, employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")
    
    return templates.TemplateResponse("employee_edit.html", {"request": request, "employee": employee})

@app.post("/employees/edit/{employee_id}")
async def edit_employee(request: Request, employee_id: int, db: Session = Depends(get_db)):
    form = await request.form()
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    employee.name = form["name"]
    employee.department = form["department"]
    employee.position = form["position"]
    db.commit()
    
    return RedirectResponse(url=f"/employees/{employee_id}", status_code=303)
@app.get("/extra-payments/edit/{payment_id}", response_class=HTMLResponse)
def edit_payment_page(request: Request, payment_id: int, db: Session = Depends(get_db)):
    payment = db.query(ExtraPayment).filter(ExtraPayment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Выплата не найдена")
    
    return templates.TemplateResponse("payment_edit.html", {"request": request, "payment": payment})

@app.post("/extra-payments/edit/{payment_id}")
async def edit_payment(request: Request, payment_id: int, db: Session = Depends(get_db)):
    form = await request.form()
    payment = db.query(ExtraPayment).filter(ExtraPayment.id == payment_id).first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Выплата не найдена")

    payment.amount = float(form["amount"])
    payment.description = form["description"]
    db.commit()
    
    return RedirectResponse(url=f"/employees/{payment.employee_id}", status_code=303)

@app.get("/employees/{employee_id}", response_class=HTMLResponse)
def employee_detail(request: Request, employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Сотрудник не найден")

    payments = db.query(ExtraPayment).filter(ExtraPayment.employee_id == employee_id).all()
    
    return templates.TemplateResponse("employee_detail.html", {"request": request, "employee": employee, "payments": payments})

# Главная страница
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Страница со списком сотрудников
@app.get("/employees", response_class=HTMLResponse)
def employees_page(request: Request, db: Session = Depends(get_db)):
    employees = db.query(Employee).all()
    return templates.TemplateResponse("employees.html", {"request": request, "employees": employees})

# Страница с выплатами (JOIN extra_payments и employees)
@app.get("/extra-payments", response_class=HTMLResponse)
def extra_payments_page(request: Request, db: Session = Depends(get_db)):
    results = db.query(ExtraPayment, Employee).join(Employee, ExtraPayment.employee_id == Employee.id).all()
    payments_data = []
    for payment, employee in results:
        payments_data.append({
            "id": payment.id,
            "employee": employee.name,
            "date": payment.date,
            "amount": payment.amount,
            "тип_документа": payment.description
        })
    return templates.TemplateResponse("extra_payments.html", {"request": request, "payments": payments_data})

# Страница загрузки данных
@app.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})
