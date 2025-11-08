from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from controllers.admin_controller import (
    auth_middleware,
    get_all_users,
    update_user_points,
    add_user,
    remove_user,
    change_user_role,
    get_total_users_count,
    get_daily_signups,
    get_points_summary,
    get_top_users,
    get_transactions_flat,
)
from db import get_db
import io
import csv

admin_router = APIRouter()

async def verify_admin_token(token: str = Header(None, alias="TOKEN")):
    return auth_middleware(token)

@admin_router.get('/users', dependencies=[Depends(verify_admin_token)])
async def get_all_users_route(sort: str = Query(default="ascending"), db: Session = Depends(get_db)):
    users = await get_all_users(db)
    if sort == "descending":
        users.sort(key=lambda x: x["credits"], reverse=True)
    else:
        users.sort(key=lambda x: x["credits"])
    return users

@admin_router.put('/points/update', dependencies=[Depends(verify_admin_token)])
async def update_user_points_route(points_data: dict, db: Session = Depends(get_db)):
    user_id = points_data.get('user_id')
    points = points_data.get('points')
    return await update_user_points(user_id, points, db)

@admin_router.post('/users/add', dependencies=[Depends(verify_admin_token)])
async def add_user_route(user_data: dict, db: Session = Depends(get_db)):
    return await add_user(user_data, db)

@admin_router.delete('/users/{user_id}', dependencies=[Depends(verify_admin_token)])
async def remove_user_route(user_id: str, db: Session = Depends(get_db)):
    return await remove_user(user_id, db)

@admin_router.put('/users/role', dependencies=[Depends(verify_admin_token)])
async def change_role_route(role_data: dict, db: Session = Depends(get_db)):
    admin_id = role_data.get('admin_id')
    target_user_id = role_data.get('user_id')
    new_role = role_data.get('role')
    return await change_user_role(admin_id, target_user_id, new_role, db)


@admin_router.get('/metrics/total_users', dependencies=[Depends(verify_admin_token)])
async def total_users_metric(db: Session = Depends(get_db)):
    total = await get_total_users_count(db)
    return {"total_users": total}


@admin_router.get('/metrics/daily_signups', dependencies=[Depends(verify_admin_token)])
async def daily_signups_metric(days: int = Query(default=7, ge=1, le=30), db: Session = Depends(get_db)):
    return await get_daily_signups(db, days=days)


@admin_router.get('/metrics/points_minted', dependencies=[Depends(verify_admin_token)])
async def points_minted_metric(days: int = Query(default=7, ge=1, le=30), db: Session = Depends(get_db)):
    summary = await get_points_summary(db, days=days)
    return {
        "total": summary["minted_total"],
        "series": summary["minted_series"],
    }


@admin_router.get('/metrics/points_redeemed', dependencies=[Depends(verify_admin_token)])
async def points_redeemed_metric(days: int = Query(default=7, ge=1, le=30), db: Session = Depends(get_db)):
    summary = await get_points_summary(db, days=days)
    return {
        "total": summary["redeemed_total"],
        "series": summary["redeemed_series"],
    }


@admin_router.get('/metrics/top_users', dependencies=[Depends(verify_admin_token)])
async def top_users_metric(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)):
    users = await get_top_users(limit, db)
    return {"users": users}


@admin_router.get('/transactions/export.csv', dependencies=[Depends(verify_admin_token)])
async def export_transactions_csv(db: Session = Depends(get_db)):
    rows = await get_transactions_flat(db)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["user_id", "type", "amount", "timestamp", "performed_by", "balance"])
    for row in rows:
        writer.writerow([
            row.get("user_id"),
            row.get("type"),
            row.get("amount"),
            row.get("timestamp"),
            row.get("performed_by"),
            row.get("balance"),
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )