from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.role_model import Role
from models.user_model import User
from models.database import UserDB
import base64
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Iterable, Optional

def auth_middleware(token: str):
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized: Token key not provided")

    token = base64.b64decode(token).decode('utf-8')
    
    if token != os.getenv('ADMIN_PASSWORD'):
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid Credentials")

async def get_all_users(db: Session):
    try:
        users = db.query(UserDB).all()
        user_list = []
        for user in users:
            user_list.append({
                "unique_id": user.unique_id,
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                "credits": user.credits or 0,
            })
        return user_list
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def update_user_points(user_id: str, points: int, db: Session):
    try:
        user = db.query(UserDB).filter(UserDB.unique_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.credits += points
        db.commit()
        return {"message": "User points updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def add_user(user_data: dict, db: Session):
    try:
        user_id = user_data.get('user_id')
        user_name = user_data.get('user_name')
        user_points = user_data.get('user_points', 0)
        
        # Parse name into first and last
        name_parts = user_name.split(' ', 1) if user_name else ['', '']
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''
        
        new_user = User(
            unique_id=user_id,
            first_name=first_name,
            last_name=last_name,
            credits=user_points
        )
        new_user.save(db)
        return {"message": "User added successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def remove_user(user_id: str, db: Session):
    try:
        user = db.query(UserDB).filter(UserDB.unique_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        db.delete(user)
        db.commit()
        return {"message": "User removed successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

async def change_user_role(admin_id: str, target_user_id: str, new_role: str, db: Session):
    try:
        admin_user = User.get_by_id(admin_id, db)
        if not admin_user or admin_user.role != Role.ADMIN:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        target_user = User.get_by_id(target_user_id, db)
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        try:
            new_role_enum = Role(new_role.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid role")
        
        db_user = db.query(UserDB).filter(UserDB.unique_id == target_user_id).first()
        db_user.role = new_role_enum.value
        db.commit()
        
        return {
            "message": f"User role updated to {new_role} successfully",
            "user": {
                "id": target_user_id,
                "role": new_role_enum.value
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

async def get_total_users_count(db: Session) -> int:
    try:
        return db.query(func.count(UserDB.id)).scalar() or 0
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


async def get_top_users(limit: int, db: Session) -> List[Dict[str, Any]]:
    try:
        users = (
            db.query(UserDB)
            .order_by(UserDB.credits.desc(), UserDB.unique_id.asc())
            .limit(limit)
            .all()
        )
        result: List[Dict[str, Any]] = []
        for user in users:
            role_value = user.role.value if isinstance(user.role, Role) else str(user.role)
            result.append(
                {
                    "unique_id": user.unique_id,
                    "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                    "credits": user.credits or 0,
                    "role": role_value,
                }
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _iter_transactions(db: Session) -> Iterable[Tuple[str, Dict[str, Any]]]:
    rows = db.query(UserDB.unique_id, UserDB.transaction_history).all()
    for unique_id, history in rows:
        if not history:
            continue
        for entry in history:
            if isinstance(entry, dict):
                yield unique_id, entry


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except Exception:
            return None
    if isinstance(value, str):
        for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    return None


async def get_points_summary(db: Session, days: int = 7) -> Dict[str, Any]:
    try:
        minted_total = 0.0
        redeemed_total = 0.0
        minted_by_day: Dict[str, float] = defaultdict(float)
        redeemed_by_day: Dict[str, float] = defaultdict(float)

        window_start_date = datetime.utcnow().date() - timedelta(days=days - 1)
        window_start = datetime.combine(window_start_date, datetime.min.time())

        for user_id, entry in _iter_transactions(db):
            tx_type = str(entry.get("type", "")).upper()
            raw_amount = entry.get("points") or 0
            try:
                amount = float(raw_amount)
            except (TypeError, ValueError):
                amount = 0.0

            ts = _parse_timestamp(entry.get("timestamp"))
            bucket = None
            if ts:
                bucket = ts.strftime("%Y-%m-%d")

            if tx_type == "ALLOCATE":
                minted_total += amount
                if bucket and ts >= window_start:
                    minted_by_day[bucket] += amount
            elif tx_type == "REDEEM":
                redeemed_total += abs(amount)
                if bucket and ts >= window_start:
                    redeemed_by_day[bucket] += abs(amount)

        def _series_map(source: Dict[str, float]) -> List[Tuple[str, float]]:
            days_range = [window_start.date() + timedelta(days=i) for i in range(days)]
            return [
                (
                    day.strftime("%Y-%m-%d"),
                    round(source.get(day.strftime("%Y-%m-%d"), 0.0), 2),
                )
                for day in days_range
            ]

        def _series_dict(source: Dict[str, float]) -> Dict[str, List[float]]:
            days_range = [window_start.date() + timedelta(days=i) for i in range(days)]
            labels: List[str] = []
            values: List[float] = []
            for day in days_range:
                label = day.strftime("%Y-%m-%d")
                labels.append(label)
                values.append(round(source.get(label, 0.0), 2))
            return {"labels": labels, "values": values}

        minted_series = _series_dict(minted_by_day)
        redeemed_series = _series_dict(redeemed_by_day)

        return {
            "minted_total": round(minted_total, 2),
            "redeemed_total": round(redeemed_total, 2),
            "minted_series": minted_series,
            "redeemed_series": redeemed_series,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


async def get_daily_signups(db: Session, days: int = 7) -> Dict[str, Any]:
    try:
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=days - 1)
        start_datetime = datetime.combine(start_date, datetime.min.time())

        results = (
            db.query(
                func.date_trunc("day", UserDB.created_at).label("day"),
                func.count(UserDB.id).label("count"),
            )
            .filter(UserDB.created_at >= start_datetime)
            .group_by("day")
            .order_by("day")
            .all()
        )

        counts: Dict[datetime.date, int] = {}
        for row in results:
            day_value = row.day
            if hasattr(day_value, "date"):
                day_value = day_value.date()
            counts[day_value] = row.count

        labels: List[str] = []
        values: List[int] = []
        for i in range(days):
            day = start_date + timedelta(days=i)
            labels.append(day.strftime("%Y-%m-%d"))
            values.append(int(counts.get(day, 0)))

        return {"labels": labels, "values": values}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


async def get_transactions_flat(db: Session) -> List[Dict[str, Any]]:
    try:
        transactions: List[Dict[str, Any]] = []
        for user_id, entry in _iter_transactions(db):
            tx_type = str(entry.get("type", "")).upper()
            amount = entry.get("points", 0)
            timestamp = entry.get("timestamp")
            performed_by = entry.get("action_user")
            balance = entry.get("balance")

            transactions.append(
                {
                    "user_id": user_id,
                    "type": tx_type,
                    "amount": amount,
                    "timestamp": timestamp,
                    "performed_by": performed_by,
                    "balance": balance,
                }
            )
        transactions.sort(key=lambda item: _parse_timestamp(item.get("timestamp")) or datetime.min, reverse=True)
        return transactions
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
