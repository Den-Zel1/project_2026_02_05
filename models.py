import re

from sqlalchemy import Integer, String, Column
from sqlalchemy.orm import declarative_base, validates

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    password_hash = Column(String)
    email = Column(String)

    @validates("email")
    def validate_email(self, key, value):
        pattern = r"^[\w.-]+@[\w.-]+\.\w+$"
        if not re.match(pattern, value):
            raise ValueError("Невалидный email")
        return value.lower()


class Trash(Base):
    __tablename__ = "trash"
    id = Column(Integer, primary_key=True)
    content = Column(String)
