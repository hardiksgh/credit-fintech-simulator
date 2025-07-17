from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy import Column, Integer, String, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Database URL (update with your MySQL credentials)
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:Hardik%402827@localhost:3306/task_manager_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Task model
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100))
    description = Column(String(255))
    completed = Column(Boolean, default=False)

# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI app
app = FastAPI()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def root():
    return {"message": "Welcome to Task Manager API"}

@app.get("/tasks")
def get_tasks(db: Session = Depends(get_db)):
    tasks = db.query(Task).all()
    return {"tasks": tasks, "count": len(tasks)}

@app.post("/tasks")
def create_task(task: dict, db: Session = Depends(get_db)):
    new_task = Task(
        title=task.get("title", ""),
        description=task.get("description", ""),
        completed=task.get("completed", False),
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

