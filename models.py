from sqlalchemy import Integer, String, Column
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    password_hash = Column(String)


class Trash(Base):
    __tablename__ = "trash"
    id = Column(Integer, primary_key=True)
    content = Column(String)

