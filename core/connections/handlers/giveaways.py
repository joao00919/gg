"""Giveaways module handlers"""

import logging
from datetime import datetime, timezone
import uuid
from functions.database import database as db

logger = logging.getLogger(__name__)

def register_giveaways_handlers():
    """Register all giveaways handlers"""
    
    async def get_active(bot, payload):
        giveaways = db.get_document("giveaways") or {}
        active = [g for g in giveaways.values() if g.get('active')]
        return {'giveaways': active}
    
    async def create(bot, payload):
        data = payload.get('giveawayData', {})
        if not isinstance(data, dict):
            raise ValueError("giveawayData must be an object")
        title = str(data.get("title") or "").strip()
        prize = str(data.get("prize") or "").strip()
        if not title or not prize:
            raise ValueError("title and prize are required")
        giveaways = db.get_document("giveaways") or {}
        giveaway_id = str(data.get("id") or uuid.uuid4().hex[:12])
        if giveaway_id in giveaways:
            raise ValueError("giveaway id already exists")
        now = datetime.now(timezone.utc).isoformat()
        record = {
            **data,
            "id": giveaway_id,
            "title": title,
            "prize": prize,
            "active": bool(data.get("active", True)),
            "createdAt": now,
            "updatedAt": now,
            "participants": list(data.get("participants") or []),
        }
        giveaways[giveaway_id] = record
        db.save_document("giveaways", giveaways)
        logger.info("Giveaway created: %s", giveaway_id)
        return {'success': True, 'giveaway': record}
    
    return {
        'giveaways.getActive': get_active,
        'giveaways.create': create
    }
