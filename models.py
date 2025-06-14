from sqlalchemy import Column, Integer, String, ForeignKey, Date, Float
from sqlalchemy.orm import relationship
from database import Base  # Импорт Base из database.py

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    birthdate = Column(Date)
    department = Column(String)
    position = Column(String)

    extra_payments = relationship("ExtraPayment", back_populates="employee")

class ExtraPayment(Base):
    __tablename__ = "extra_payments"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"))
    amount = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
    description = Column(String, nullable=True)

    employee = relationship("Employee", back_populates="extra_payments")
