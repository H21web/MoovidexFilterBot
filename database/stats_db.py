from datetime import datetime
import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME

class StatsDB:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.search_logs = self.db.search_logs
        self.pm_search_logs = self.db.pm_search_logs

    async def add_search_log(self, query, user_id, results_count):
        log = {
            'query': query,
            'user_id': user_id,
            'results_count': results_count,
            'timestamp': datetime.utcnow()
        }
        await self.search_logs.insert_one(log)

    async def add_pm_search_log(self, query, user_id):
        log = {
            'query': query,
            'user_id': user_id,
            'timestamp': datetime.utcnow()
        }
        await self.pm_search_logs.insert_one(log)
    
    async def clear_pm_search_logs(self):
        await self.pm_search_logs.delete_many({})

    async def get_total_searches(self):
        return await self.search_logs.count_documents({})

    async def get_top_searches(self, limit=10):
        pipeline = [
            {"$group": {"_id": "$query", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        cursor = self.search_logs.aggregate(pipeline)
        return await cursor.to_list(length=limit)

    async def get_no_result_stats(self, limit=10):
        pipeline = [
            {"$match": {"results_count": 0}},
            {"$group": {"_id": "$query", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        cursor = self.search_logs.aggregate(pipeline)
        return await cursor.to_list(length=limit)

    async def get_recent_pm_searches(self, limit=50):
        cursor = self.pm_search_logs.find().sort('timestamp', -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_top_active_users(self, limit=10):
        pipeline = [
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        cursor = self.search_logs.aggregate(pipeline)
        return await cursor.to_list(length=limit)

stats_db = StatsDB(DATABASE_URI, DATABASE_NAME)
