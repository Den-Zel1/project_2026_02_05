import hashlib
from contextlib import asynccontextmanager
from datetime import time, timedelta, datetime
from urllib.request import Request

from fastapi import FastAPI, Depends, HTTPException, APIRouter
from jose import jwt
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Base, User, Trash
from pydantic import BaseModel
import middleware
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # Создаем новые таблицы
    yield
    engine.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(middleware.PrintMiddleware)

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
@app.post("/auth")
def auth_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(user.username == User.name).first()
    if not existing_user:
        raise HTTPException(
            status_code=400,
            detail="Таких не знаем!"
        )
    # Хэшируем пароль
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    password_hash = str(password_hash)
    if password_hash != existing_user.password_hash:
        raise HTTPException(
            status_code=400,
            detail="Пароль какой-то не такой!"
        )
    else:
        token = create_token(user.username)
        return {"message": f"Добрый день, {user.username}!"}

@app.get("/")
async def read_current_user(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        return {"username": username, "message": "You are authenticated!"}
    except:
        raise HTTPException(status_code=401, detail="Invalid token")


def create_token(username: str):
    expire = datetime.now() + timedelta(minutes=settings.TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "exp": expire
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
