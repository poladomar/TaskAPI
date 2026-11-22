from fastapi.testclient import TestClient
from app import app

def test_crud_and_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET","test-only-not-a-production-secret-000000")
    monkeypatch.setenv("DATABASE_PATH",str(tmp_path/"test.db"))
    client = TestClient(app)
    def account(name):
        assert client.post("/register",json={"username":name,"password":"testpassword123"}).status_code == 201
        result = client.post("/token",data={"username":name,"password":"testpassword123"})
        assert result.status_code == 200
        return {"Authorization":"Bearer "+result.json()["access_token"]}
    a,b = account("alice"),account("bobby")
    assert client.get("/tasks").status_code == 401
    task = client.post("/tasks",json={"title":"Read"},headers=a)
    assert task.status_code == 201
    path = "/tasks/"+str(task.json()["id"])
    assert client.get(path,headers=b).status_code == 404
    assert client.put(path,json={"title":"Read","done":True},headers=a).json()["done"]
    assert len(client.get("/tasks?done=true",headers=a).json()) == 1
    assert client.delete(path,headers=a).status_code == 204
    assert client.get(path,headers=a).status_code == 404
