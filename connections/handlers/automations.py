"""Automations module handlers"""

import logging
from datetime import datetime, timezone
import uuid
from functions.database import database as db

logger = logging.getLogger(__name__)

def register_automations_handlers():
    """Register all automations handlers"""
    
    async def get_automations(bot, payload):
        automations = db.get_document("automations") or {}
        return {'automations': list(automations.values())}
    
    async def create_automation(bot, payload):
        data = payload.get('automationData', {})
        if not isinstance(data, dict):
            raise ValueError("automationData must be an object")
        name = str(data.get("name") or "").strip()
        automation_type = str(data.get("type") or "").strip()
        if not name or not automation_type:
            raise ValueError("name and type are required")
        automations = db.get_document("automations") or {}
        automation_id = str(data.get("id") or uuid.uuid4().hex[:12])
        if automation_id in automations:
            raise ValueError("automation id already exists")
        now = datetime.now(timezone.utc).isoformat()
        record = {
            **data,
            "id": automation_id,
            "name": name,
            "type": automation_type,
            "enabled": bool(data.get("enabled", True)),
            "createdAt": now,
            "updatedAt": now,
        }
        automations[automation_id] = record
        db.save_document("automations", automations)
        logger.info("Automation created: %s", automation_id)
        return {'success': True, 'automation': record}
    
    return {
        'automations.getAutomations': get_automations,
        'automations.createAutomation': create_automation
    }
