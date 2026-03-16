import hashlib
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import timedelta, datetime

import aio_pika
from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from jose import jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

import middleware
from config import settings
from database import engine, get_db
from logger import setup_logging
from models import Base, User, Trash
from simple_producer import publish

queue_listener = setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Приложение запускается")
    app.state.rabbit = await aio_pika.connect_robust(settings.AMQP_URL)
    app.state.channel = await app.state.rabbit.channel()
    await app.state.channel.declare_queue(settings.RABBIT_QUEUE, durable=True)
    Base.metadata.create_all(bind=engine)
    yield
    logger.warning("Приложение останавливается")
    await app.state.rabbit.close()
    queue_listener.stop()
    engine.dispose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(middleware.AuthMiddleware)

security = HTTPBearer()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    request.state.request_id = request_id

    logger.info(
        "Request started: %s %s",
        request.method, request.url.path,
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        },
    )

    response = await call_next(request)

    logger.info(
        "Request completed: %s %s -> %s",
        request.method, request.url.path, response.status_code,
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
        },
    )

    return response


@app.get("/error")
async def error():
    logger.error("This is a test error", extra={"error_type": "test"})
    return {"error": "Something went wrong"}


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
    email: str


@app.get("/", response_class=HTMLResponse)
def get_hello():
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
def add_trash(data: str, db: Session = Depends(get_db)):
    xer = Trash(content=data)
    db.add(xer)
    db.commit()
    logger.info("Пользователь сделал новую запись %s", xer.id)
    db.refresh(xer)
    return {"id": xer.id}


@app.post("/register")
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
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
        password_hash=password_hash,
        email=user.email
    )

    # Сохраняем в базу данных
    db.add(new_user)
    db.commit()
    logger.info("Новый пользователь %s успешно добавлен", new_user.name)
    db.refresh(new_user)

    body = {"email": new_user.email, "name": new_user.name}
    await publish(app.state.channel, body, settings.RABBIT_QUEUE)

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
        logger.warning(
            "Попытка входа под несуществующим логином: %s",
            user.username,
            extra={"username": user.username},
        )
        raise HTTPException(
            status_code=400,
            detail="Таких не знаем!"
        )
    # Хэшируем пароль
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    password_hash = str(password_hash)
    if password_hash != existing_user.password_hash:
        logger.warning(
            "Неверный пароль для пользователя: %s",
            user.username,
            extra={"username": user.username},
        )
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
        logger.info(
            "Пользователь %s успешно авторизовался",
            user.username,
            extra={"username": user.username},
        )
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
        logger.warning(
            "Невалидный токен: %s — %s",
            type(e).__name__, e,
            extra={"error": str(e)},
        )
        raise HTTPException(
            status_code=401,
            detail={
                "authenticated": False,
                "message": "Токен недействителен!"
            }
        )


@app.get("/logout")
def logout_user(request: Request, response: Response):
    username = request.state.username
    response.delete_cookie(
        key="access_token",
        path="/",
        domain=None,  # укажите если нужно
        secure=True,  # True для HTTPS
        httponly=True,
        samesite="lax"
    )
    logger.info(
        "Пользователь %s вышел из системы",
        username,
        extra={"username": username},
    )
    return {"message": "Успешный выход"}


@app.post("/publish")
async def publish_endpoint(request: Request, body: dict):
    await publish(request.app.state.channel, body, settings.RABBIT_QUEUE)
    return {"status": "ok"}
