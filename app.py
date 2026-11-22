import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from pwdlib import PasswordHash
import jwt

app = FastAPI(title="TaskAPI", version="1.0.0")
passwords = PasswordHash.recommended()
oauth = OAuth2PasswordBearer(tokenUrl="/token")

@contextmanager
def db():
    con = sqlite3.connect(os.getenv("DATABASE_PATH", "tasks.db"))
    con.row_factory = sqlite3.Row
    try:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, owner INTEGER NOT NULL, title TEXT NOT NULL, description TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0);
        """)
        with con:
            yield con
    finally:
        con.close()

def secret():
    key = os.getenv("JWT_SECRET", "")
    if len(key) < 32:
        raise HTTPException(503, "Set JWT_SECRET to at least 32 characters")
    return key

def current_user(token: str = Depends(oauth)):
    try:
        payload = jwt.decode(token, secret(), algorithms=["HS256"], options={"require":["sub","exp"]})
        uid = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(401, "Invalid token", headers={"WWW-Authenticate":"Bearer"})
    with db() as con:
        if not con.execute("SELECT id FROM users WHERE id=?", (uid,)).fetchone():
            raise HTTPException(401, "Unknown user")
    return uid

class Register(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)

class Task(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(default="", max_length=2000)
    done: bool = False

@app.get("/health")
def health():
    return {"status":"ok"}

@app.post("/register", status_code=201)
def register(data: Register):
    try:
        with db() as con:
            uid = con.execute("INSERT INTO users(username,password) VALUES(?,?)", (data.username.lower(), passwords.hash(data.password))).lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Username already exists")
    return {"id":uid, "username":data.username.lower()}

@app.post("/token")
def login(form: OAuth2PasswordRequestForm = Depends()):
    with db() as con:
        user = con.execute("SELECT * FROM users WHERE username=?", (form.username.lower(),)).fetchone()
    if not user or not passwords.verify(form.password, user["password"]):
        raise HTTPException(401, "Invalid credentials")
    token = jwt.encode({"sub":str(user["id"]), "exp":datetime.now(timezone.utc)+timedelta(minutes=60)}, secret(), algorithm="HS256")
    return {"access_token":token, "token_type":"bearer"}

def task_row(row):
    return {"id":row["id"], "title":row["title"], "description":row["description"], "done":bool(row["done"])}

@app.get("/tasks")
def list_tasks(done: bool | None = None, user: int = Depends(current_user)):
    with db() as con:
        rows = con.execute("SELECT * FROM tasks WHERE owner=? AND (? IS NULL OR done=?) ORDER BY id DESC", (user, done, done)).fetchall()
    return [task_row(r) for r in rows]

@app.post("/tasks", status_code=201)
def create_task(data: Task, user: int = Depends(current_user)):
    with db() as con:
        tid = con.execute("INSERT INTO tasks(owner,title,description,done) VALUES(?,?,?,?)",(user,data.title,data.description,data.done)).lastrowid
    return {"id":tid, **data.model_dump()}

@app.get("/tasks/{tid}")
def get_task(tid: int, user: int = Depends(current_user)):
    with db() as con:
        row = con.execute("SELECT * FROM tasks WHERE id=? AND owner=?",(tid,user)).fetchone()
    if not row:
        raise HTTPException(404,"Task not found")
    return task_row(row)

@app.put("/tasks/{tid}")
def update_task(tid: int, data: Task, user: int = Depends(current_user)):
    with db() as con:
        result = con.execute("UPDATE tasks SET title=?,description=?,done=? WHERE id=? AND owner=?", (data.title,data.description,data.done,tid,user))
        if not result.rowcount:
            raise HTTPException(404,"Task not found")
    return {"id":tid, **data.model_dump()}

@app.delete("/tasks/{tid}", status_code=204)
def delete_task(tid: int, user: int = Depends(current_user)):
    with db() as con:
        if not con.execute("DELETE FROM tasks WHERE id=? AND owner=?", (tid,user)).rowcount:
            raise HTTPException(404,"Task not found")
