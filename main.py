from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from database import engine, get_db
from models import Base, User, Trash


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # Создаем новые таблицы
    yield
    engine.dispose()


app = FastAPI(lifespan=lifespan)


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