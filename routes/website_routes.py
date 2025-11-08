from fastapi import APIRouter, Depends, Query, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from controllers.website_controller import (
    home, 
    add_user_logic, 
    user_details,
    update_user_points_logic, 
    update_user_role_logic, 
    delete_user_logic, 
    get_user_transactions_logic,
    update_user_balance_logic,
    search_users
)
from db import get_db
import os

website_router = APIRouter()
templates = Jinja2Templates(directory="templates")

# do NOT change the routes without manually changing stuff in templates

@website_router.get("/", response_class=HTMLResponse)
async def route_home(request: Request, query: str = Query(None), db: Session = Depends(get_db)):
    if query:
        return await search_users(request, query, db)
    return await home(request, db)

@website_router.get("/dashboard", response_class=HTMLResponse)
async def route_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@website_router.get("/user/add", response_class=HTMLResponse)
async def route_add_user_get(request: Request):
    return templates.TemplateResponse("AddUser.html", {"request": request})

@website_router.post("/user/add")
async def route_add_user_post(user_data: dict, db: Session = Depends(get_db)):
    return await add_user_logic(user_data, db)

@website_router.get("/user/{user_id}", response_class=HTMLResponse)
async def route_user_details(request: Request, user_id: str, db: Session = Depends(get_db)):
    return await user_details(request, user_id, db)

@website_router.post("/user/points/update")
async def route_update_user_points(
    user_id: str = Form(...),
    points: int = Form(...),
    db: Session = Depends(get_db)
):
    return await update_user_points_logic(user_id, points, db)

@website_router.post("/user/balance/update")
async def route_update_user_balance(
    user_id: str = Form(...),
    balance: int = Form(...),
    db: Session = Depends(get_db)
):
    return await update_user_balance_logic(user_id, balance, db)

@website_router.post("/user/role/update")
async def route_update_user_role(
    user_id: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db)
):
    return await update_user_role_logic(user_id, role, db)

@website_router.post("/user/delete")
async def route_delete_user(
    user_id: str = Form(...),
    db: Session = Depends(get_db)
):
    return await delete_user_logic(user_id, db)

@website_router.get("/user/{user_id}/transactions")
async def route_user_transactions(user_id: str, db: Session = Depends(get_db)):
    return await get_user_transactions_logic(user_id, db)
