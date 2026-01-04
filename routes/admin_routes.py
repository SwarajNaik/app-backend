from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from controllers.admin_controller import (
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
    _iter_transactions,
)
from db import get_db
from utils import verify_admin_token
import csv

admin_router = APIRouter()

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
    """Stream CSV export as generator for large datasets."""
    import io
    
    def generate_csv():
        # Use StringIO buffer for csv.writer
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        
        # Write header
        writer.writerow(["user_id", "type", "amount", "timestamp", "performed_by", "balance"])
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        
        # Stream rows one by one
        for user_id, entry in _iter_transactions(db):
            tx_type = str(entry.get("type", "")).upper()
            amount = entry.get("points", 0)
            timestamp = entry.get("timestamp")
            performed_by = entry.get("action_user")
            balance = entry.get("balance")
            
            # Use csv.writer for proper escaping
            writer.writerow([
                user_id or "",
                tx_type or "",
                amount or "",
                str(timestamp) if timestamp else "",
                performed_by or "",
                balance or "",
            ])
            yield buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
    
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions.csv"},
    )