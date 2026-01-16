from datetime import datetime, timedelta
import motor.motor_asyncio
import pytz
from info import DATABASE_URI, DATABASE_NAME, FILE_DB_URI, SEC_FILE_DB_URI, COLLECTION_NAME, MULTIPLE_DATABASE
from pymongo import MongoClient

IST = pytz.timezone('Asia/Kolkata')

class StatsDB:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.search_logs = self.db.search_logs
        self.pm_search_logs = self.db.pm_search_logs
        
        # File DB Connections for Stats
        self.file_client = MongoClient(FILE_DB_URI)
        self.file_db = self.file_client[DATABASE_NAME]
        self.file_col = self.file_db[COLLECTION_NAME]
        
        if MULTIPLE_DATABASE:
            self.sec_file_client = MongoClient(SEC_FILE_DB_URI)
            self.sec_file_db = self.sec_file_client[DATABASE_NAME]
            self.sec_file_col = self.sec_file_db[COLLECTION_NAME]

    async def add_search_log(self, query, user_id, results_count, source=None):
        log = {
            'query': query,
            'user_id': user_id,
            'results_count': results_count,
            'source': source or 'auto_filter',
            'timestamp': datetime.now(IST)
        }
        await self.search_logs.insert_one(log)

    async def add_pm_search_log(self, query, user_id):
        log = {
            'query': query,
            'user_id': user_id,
            'timestamp': datetime.now(IST)
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

    async def get_recent_pm_searches(self, page=1, limit=50):
        skip = (page - 1) * limit
        pipeline = [
            {"$sort": {"timestamp": -1}},
            {"$skip": skip},
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

    async def get_total_pm_searches_count(self):
        return await self.pm_search_logs.count_documents({})

    async def get_recent_all_searches(self, limit=100):
        pipeline = [
            {"$sort": {"timestamp": -1}},
            {"$limit": limit},
            {"$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "id",
                "as": "user_info"
            }},
            {"$unwind": {"path": "$user_info", "preserveNullAndEmptyArrays": True}}
        ]
        cursor = self.search_logs.aggregate(pipeline)
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

    async def get_no_result_ratio(self):
        """
        Global % of searches with 0 results.
        """
        total = await self.search_logs.count_documents({})
        if total == 0: return 0
        no_res = await self.search_logs.count_documents({"results_count": 0})
        return round((no_res / total) * 100, 2)

    async def get_no_results_per_day(self, days=7):
        pipeline = [
            {
                "$match": {
                    "results_count": 0,
                "$match": {
                    "results_count": 0,
                    "timestamp": {"$gte": datetime.now(IST) - timedelta(days=days)}
                }
                }
            },
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        return await cursor.to_list(length=days)

    async def get_today_success_ratio(self):
        today = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
        total = await self.search_logs.count_documents({"timestamp": {"$gte": today}})
        if total == 0: return 0
        success = await self.search_logs.count_documents({
            "timestamp": {"$gte": today},
            "results_count": {"$gt": 0}
        })
        return round((success / total) * 100, 2)

    async def get_weekly_success_ratio(self):
        week_ago = datetime.now(IST) - timedelta(days=7)
        total = await self.search_logs.count_documents({"timestamp": {"$gte": week_ago}})
        if total == 0: return 0
        success = await self.search_logs.count_documents({
            "timestamp": {"$gte": week_ago},
            "results_count": {"$gt": 0}
        })
        return round((success / total) * 100, 2)

    async def get_database_stats(self):
        stats = {}
        
        # Primary DB
        try:
            p_count = self.file_col.count_documents({})
            # dbStats returns size in bytes
            p_db_stats = self.file_db.command("dbStats")
            p_size = p_db_stats.get("dataSize", 0) / (1024 * 1024) # MB
            stats['primary'] = {"count": p_count, "size": round(p_size, 2)}
        except Exception as e:
            stats['primary'] = {"count": 0, "size": 0, "error": str(e)}

        # Secondary DB
        if MULTIPLE_DATABASE:
            try:
                s_count = self.sec_file_col.count_documents({})
                s_db_stats = self.sec_file_db.command("dbStats")
                s_size = s_db_stats.get("dataSize", 0) / (1024 * 1024) # MB
                stats['secondary'] = {"count": s_count, "size": round(s_size, 2)}
                stats['total_files'] = p_count + s_count
            except:
                stats['secondary'] = {"count": 0, "size": 0}
                stats['total_files'] = p_count
        else:
            stats['total_files'] = p_count
            
        return stats

stats_db = StatsDB(DATABASE_URI, DATABASE_NAME)
