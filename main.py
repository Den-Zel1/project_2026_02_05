import hashlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, APIRouter
from sqlalchemy.orm import Session

from database import engine, get_db
from models import Base, User, Trash
from pydantic import BaseModel

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # Создаем новые таблицы
    yield
    engine.dispose()


app = FastAPI(lifespan=lifespan)

class UserCreate(BaseModel):
    username: str
    password: str


@app.get("/")
def get_hello():
    return {"message": "Hello World!"}

@app.get("/trash")
def get_trash(db: Session = Depends(get_db)):
    users = db.query(Trash).all()
    return {"users": [
        {"id": user.id, "content": user.content}
        for user in users
    ]}

@app.post("/trash")
def add_trash(data:str, db: Session = Depends(get_db)):
    xer = Trash(content = data)
    db.add(xer)
    db.commit()
    db.refresh(xer)
    return {"id":xer.id}


@app.post("/register")
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Простой эндпоинт для регистрации пользователя
    """

    # Проверяем, существует ли пользователь с таким username
    existing_user = db.query(User).filter(user.username == User.name).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Пользователь с таким именем уже существует"
        )

    # Хэшируем пароль
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    password_hash = str(password_hash)
    # Создаем нового пользователя
    new_user = User(
        name=user.username,
        password_hash=password_hash
    )

    # Сохраняем в базу данных
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Возвращаем ответ (без пароля!)
    return {
        "message": "Пользователь успешно зарегистрирован",
        "user_id": new_user.id,
        "username": new_user.name
    }