from datetime import datetime
import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME

class StatsDB:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.search_logs = self.db.search_logs
        self.pm_search_logs = self.db.pm_search_logs

    async def add_search_log(self, query, user_id, results_count, source=None):
        log = {
            'query': query,
            'user_id': user_id,
            'results_count': results_count,
            'source': source or 'auto_filter',
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
        pipeline = [
            {"$sort": {"timestamp": -1}},
            {"$limit": limit},
            {"$lookup": {
                "from": "users",  # Verify this matches COLLECTION_NAME in users_chats_db logic
                "localField": "user_id",
                "foreignField": "id",
                "as": "user_info"
            }},
            {"$unwind": {"path": "$user_info", "preserveNullAndEmptyArrays": True}}
        ]
        cursor = self.pm_search_logs.aggregate(pipeline)
        return await cursor.to_list(length=limit)

    async def get_top_active_users(self, limit=10):
        pipeline = [
            {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
            {"$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "id",
                "as": "user_info"
            }},
            {"$unwind": {"path": "$user_info", "preserveNullAndEmptyArrays": True}}
        ]
        cursor = self.search_logs.aggregate(pipeline)
        return await cursor.to_list(length=limit)

    async def get_global_success_ratio(self):
        """
        Returns the percentage of searches that returned at least one result.
        """
        total_searches = await self.search_logs.count_documents({})
        if total_searches == 0:
            return 0
        
        successful_searches = await self.search_logs.count_documents({"results_count": {"$gt": 0}})
        return round((successful_searches / total_searches) * 100, 2)

    async def get_average_user_fulfillment(self):
        """
        Calculates average fulfillment ratio per user.
        Fulfillment = (Successful Searches / Total Searches) per user.
        Returns the average of these ratios across all users.
        """
        pipeline = [
            {
                "$group": {
                    "_id": "$user_id",
                    "total": {"$sum": 1},
                    "success": {
                        "$sum": {
                            "$cond": [{"$gt": ["$results_count", 0]}, 1, 0]
                        }
                    }
                }
            },
            {
                "$project": {
                    "ratio": {"$divide": ["$success", "$total"]}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_fulfillment": {"$avg": "$ratio"}
                }
            }
        ]
        cursor = self.search_logs.aggregate(pipeline)
        result = await cursor.to_list(length=1)
        
        if result:
            return round(result[0]['avg_fulfillment'] * 100, 2)
        return 0

stats_db = StatsDB(DATABASE_URI, DATABASE_NAME)
