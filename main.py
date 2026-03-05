import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import time, timedelta, datetime
import os

from fastapi.responses import JSONResponse


from fastapi import FastAPI, Depends, HTTPException, APIRouter
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt
from sqlalchemy.orm import Session
from database import engine, get_db
from models import Base, User, Trash
from pydantic import BaseModel
import middleware
from config import settings
from logger import setup_logging
from fastapi.responses import HTMLResponse


from fastapi.templating import Jinja2Templates
from fastapi import Request





setup_logging()
logger = logging.getLogger(__name__)




@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Приложение запускается")
    Base.metadata.create_all(bind=engine)  # Создаем новые таблицы
    yield
    logger.warning("Приложение останавливается")
    engine.dispose()




app = FastAPI(lifespan=lifespan)
app.add_middleware(middleware.PrintMiddleware)




security = HTTPBearer()
def create_token(username: str):
    expire = datetime.now() + timedelta(minutes=settings.TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "exp": expire
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

class UserCreate(BaseModel):
    username: str
    password: str


@app.get("/", response_class=HTMLResponse)
def get_hello():
    logger.debug("Обращение к ручке get!")
    with open("index.html", encoding="utf-8") as f:
        return f.read()

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
    logger.debug(f"Новый пользователь {new_user} успешно добавлен")
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
        logger.debug(f"Пользователь пытается зайти под недействильным логином {user.username}")
        raise HTTPException(
            status_code=400,
            detail="Таких не знаем!"
        )
    # Хэшируем пароль
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    password_hash = str(password_hash)
    if password_hash != existing_user.password_hash:
        logger.debug(f"Пользователь {user.username} ввел невалидный пароль")
        raise HTTPException(
            status_code=400,
            detail="Пароль какой-то не такой!"
        )
    else:
        token = create_token(user.username)

        response = JSONResponse(content={
            "message": "У тебя валидный токен!",
        })
        response.set_cookie(key="access_token", value=token, httponly=True, max_age=3600)
        logger.debug(f"Пользователь {user.username} успешно авторизовался ")
        return response

@app.get("/check-auth")
def read_current_user(request: Request):
    token = request.cookies.get("access_token")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        return {
            "authenticated": True,
            "username": username,
            "message": "Пользователь авторизован"
        }
    except Exception as e:
        print(type(e), e)
        raise HTTPException(
            status_code=401,
            detail={
                "authenticated": False,
                "message": "Токен недействителен!"
            }
        )
@app.post("/login")
def login_user(request: Request):
    token = request.cookies.get("access_token")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        return {
            "authenticated": True,
            "username": username,
            "message": "Пользователь авторизован"
        }
    except Exception as e:
        print(type(e), e)
        raise HTTPException(
            status_code=401,
            detail={
                "authenticated": False,
                "message": "Токен недействителен!"
            })

